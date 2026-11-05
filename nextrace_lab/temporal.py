"""Shared Temporal Evidence Layer (Milestone Stage 1).

Represents and enforces:
1. Separate timestamps and intervals:
   - `event_time_utc`: when the underlying service event or probe occurred.
   - `collection_time_utc`: when the diagnostic interface collected the observation.
   - `observation_interval_start_utc` / `observation_interval_end_utc` / `observation_interval_sec`.
   - `evaluation_time_utc`: when the evidence gate / hypothesis manager evaluated the observation.
2. Monotonic time for elapsed durations, TTL freshness expiration (`is_stale`, `freshness_status`), and deadlines.
3. UTC timestamps for incident-window alignment with explicit, configurable `clock_skew_tolerance_sec`.
4. Supersession tracking (`is_superseded`, `superseded_by_evidence_id`) when a newer observation of the
   same check supersedes an older one.
5. Timestamp uncertainty detection (`timestamp_uncertain`, `timestamp_uncertainty_reason`) when events or
   probes lack valid UTC timestamps.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any, Optional

from nextrace_lab.logging_utils import parse_utc_iso, utc_now_iso
from nextrace_lab.schemas import (
    DiagnosticCheckResult,
    EvidenceStatus,
    IncidentContext,
)

DEFAULT_INCIDENT_LOOKBACK_SEC = 30.0
DEFAULT_INCIDENT_FORWARD_SEC = 15.0


def parse_event_timestamp_safely(raw_ts: Any) -> tuple[Optional[datetime], bool, Optional[str]]:
    """Parse an ISO-8601 UTC timestamp string safely.

    Returns `(datetime_utc, timestamp_uncertain, uncertainty_reason)`.
    """
    if raw_ts is None or not isinstance(raw_ts, str) or not raw_ts.strip():
        return None, True, "missing_timestamp"
    text = raw_ts.strip()
    if text in ("unknown", "invalid", "none", "null", "N/A"):
        return None, True, f"placeholder_timestamp:{text}"
    try:
        dt = parse_utc_iso(text)
        # Reject implausible years (e.g. 1970 epoch zero or far future) as uncertain
        if dt.year < 2020 or dt.year > 2100:
            return None, True, f"implausible_timestamp_year:{dt.year}"
        return dt, False, None
    except Exception as exc:
        return None, True, f"unparseable_timestamp:{type(exc).__name__}"


def compute_incident_window_bounds(
    incident: IncidentContext,
    *,
    default_lookback_sec: float = DEFAULT_INCIDENT_LOOKBACK_SEC,
    default_forward_sec: float = DEFAULT_INCIDENT_FORWARD_SEC,
) -> tuple[Optional[datetime], Optional[datetime], bool, Optional[str]]:
    """Return `(effective_start_utc, effective_end_utc, window_uncertain, reason)` including clock-skew tolerance.

    Incident-window boundary convention:
    - Base window is `[incident_window_start_utc, incident_window_end_utc]` if explicitly set on `IncidentContext`,
      or `[observed_at_utc - default_lookback_sec, observed_at_utc + default_forward_sec]` otherwise.
    - Effective window expands both boundaries by `clock_skew_tolerance_sec` (default 2.0s):
      `[base_start - skew, base_end + skew]`.
    """
    obs_dt, obs_uncertain, obs_reason = parse_event_timestamp_safely(incident.observed_at_utc)
    if obs_uncertain or obs_dt is None:
        return None, None, True, f"incident_observed_at_uncertain:{obs_reason}"

    skew = max(0.0, float(getattr(incident, "clock_skew_tolerance_sec", 2.0) or 0.0))

    if incident.incident_window_start_utc:
        s_dt, s_unc, s_reason = parse_event_timestamp_safely(incident.incident_window_start_utc)
        if s_unc or s_dt is None:
            return None, None, True, f"incident_window_start_uncertain:{s_reason}"
        base_start = s_dt
    else:
        base_start = obs_dt - timedelta(seconds=max(1.0, float(default_lookback_sec)))

    if incident.incident_window_end_utc:
        e_dt, e_unc, e_reason = parse_event_timestamp_safely(incident.incident_window_end_utc)
        if e_unc or e_dt is None:
            return None, None, True, f"incident_window_end_uncertain:{e_reason}"
        base_end = e_dt
    else:
        base_end = obs_dt + timedelta(seconds=max(1.0, float(default_forward_sec)))

    eff_start = base_start - timedelta(seconds=skew)
    eff_end = base_end + timedelta(seconds=skew)
    return eff_start, eff_end, False, None


def is_timestamp_in_incident_window(
    raw_ts: Any,
    incident: IncidentContext,
) -> tuple[bool, bool, Optional[str]]:
    """Check whether `raw_ts` falls inside the incident window `[start - skew, end + skew]`.

    Returns `(in_window, timestamp_uncertain, reason)`.
    """
    ev_dt, ev_unc, ev_reason = parse_event_timestamp_safely(raw_ts)
    if ev_unc or ev_dt is None:
        return False, True, ev_reason

    win_start, win_end, win_unc, win_reason = compute_incident_window_bounds(incident)
    if win_unc or win_start is None or win_end is None:
        return False, True, win_reason

    if win_start <= ev_dt <= win_end:
        return True, False, None
    if ev_dt < win_start:
        delta = round((win_start - ev_dt).total_seconds(), 2)
        return False, False, f"event_before_incident_window_by_{delta}s"
    delta = round((ev_dt - win_end).total_seconds(), 2)
    return False, False, f"event_after_incident_window_by_{delta}s"


def filter_log_entries_for_incident_window(
    entries: list[dict[str, Any]],
    incident: Optional[IncidentContext],
) -> dict[str, Any]:
    """Classify log entries into in-window, out-of-window (historical/later), and uncertain-timestamp buckets."""
    if incident is None:
        error_entries = [e for e in entries if e.get("level") == "ERROR"]
        cats = sorted({str(e.get("error_category")) for e in error_entries if e.get("error_category")})
        return {
            "in_window_entries": entries,
            "out_of_window_entries": [],
            "uncertain_timestamp_entries": [],
            "in_window_error_entries": error_entries,
            "out_of_window_error_entries": [],
            "uncertain_error_entries": [],
            "in_window_error_categories": cats,
            "out_of_window_error_categories": [],
            "uncertain_error_categories": [],
            "timestamp_uncertain": False,
            "timestamp_uncertainty_reason": None,
        }

    in_window: list[dict[str, Any]] = []
    out_of_window: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    uncertainty_reasons: list[str] = []

    for entry in entries:
        raw_ts = entry.get("timestamp_utc") or entry.get("timestamp")
        in_win, is_unc, reason = is_timestamp_in_incident_window(raw_ts, incident)
        if is_unc:
            uncertain.append(entry)
            if reason and reason not in uncertainty_reasons:
                uncertainty_reasons.append(reason)
        elif in_win:
            in_window.append(entry)
        else:
            out_of_window.append(entry)

    in_win_errors = [e for e in in_window if e.get("level") == "ERROR"]
    out_win_errors = [e for e in out_of_window if e.get("level") == "ERROR"]
    unc_errors = [e for e in uncertain if e.get("level") == "ERROR"]

    in_win_cats = sorted({str(e.get("error_category")) for e in in_win_errors if e.get("error_category")})
    out_win_cats = sorted({str(e.get("error_category")) for e in out_win_errors if e.get("error_category")})
    unc_cats = sorted({str(e.get("error_category")) for e in unc_errors if e.get("error_category")})

    has_uncertain_errors = len(unc_errors) > 0
    return {
        "in_window_entries": in_window,
        "out_of_window_entries": out_of_window,
        "uncertain_timestamp_entries": uncertain,
        "in_window_error_entries": in_win_errors,
        "out_of_window_error_entries": out_win_errors,
        "uncertain_error_entries": unc_errors,
        "in_window_error_categories": in_win_cats,
        "out_of_window_error_categories": out_win_cats,
        "uncertain_error_categories": unc_cats,
        "timestamp_uncertain": has_uncertain_errors,
        "timestamp_uncertainty_reason": "; ".join(uncertainty_reasons) if uncertainty_reasons else None,
    }


def canonical_check_key(check_name: str, params: dict[str, Any]) -> str:
    return f"{check_name}:{json.dumps(params or {}, sort_keys=True)}"


def refresh_temporal_evidence_state(
    history: list[DiagnosticCheckResult],
    acquired_monotonic: dict[str, float],
    now_monotonic: float,
    *,
    evaluation_time_utc: Optional[str] = None,
    incident: Optional[IncidentContext] = None,
) -> tuple[list[str], list[str]]:
    """Refresh freshness (`is_stale`, `freshness_status`), supersession (`is_superseded`), and incident-window alignment.

    Returns `(stale_evidence_ids, superseded_evidence_ids)`.
    """
    eval_utc = evaluation_time_utc or utc_now_iso()
    stale_ids: list[str] = []
    superseded_ids: list[str] = []

    # 1. Track latest AVAILABLE observation per canonical (check_name, params)
    latest_available_by_key: dict[str, DiagnosticCheckResult] = {}
    for rec in history:
        if rec.status == EvidenceStatus.AVAILABLE:
            key = canonical_check_key(rec.check_name, rec.params)
            latest_available_by_key[key] = rec

    # 2. Update each record's temporal fields
    for rec in history:
        rec.evaluation_time_utc = eval_utc
        if rec.status != EvidenceStatus.AVAILABLE:
            rec.freshness_status = "not_applicable"
            rec.is_superseded = False
            rec.superseded_by_evidence_id = None
            continue

        acq_m = acquired_monotonic.get(rec.evidence_id, now_monotonic)
        elapsed_m = max(0.0, now_monotonic - acq_m)
        if elapsed_m >= rec.freshness_ttl_sec or bool(rec.data.get("is_stale", False)):
            rec.is_stale = True
            rec.freshness_status = "stale"
        else:
            rec.is_stale = False
            rec.freshness_status = "fresh"

        if rec.is_stale:
            stale_ids.append(rec.evidence_id)

        key = canonical_check_key(rec.check_name, rec.params)
        latest_rec = latest_available_by_key.get(key)
        if latest_rec is not None and latest_rec.evidence_id != rec.evidence_id:
            rec.is_superseded = True
            rec.superseded_by_evidence_id = latest_rec.evidence_id
            superseded_ids.append(rec.evidence_id)
        else:
            rec.is_superseded = False
            rec.superseded_by_evidence_id = None

        # Verify event timestamp & incident-window alignment
        if rec.check_name == "get_recent_logs":
            # Log records carry per-entry window classification in `rec.data`
            if "in_window_error_categories" in rec.data:
                in_win_cnt = len(rec.data.get("in_window_entries", []))
                rec.in_incident_window = in_win_cnt > 0
                if rec.data.get("timestamp_uncertain"):
                    rec.timestamp_uncertain = True
                    rec.timestamp_uncertainty_reason = rec.data.get("timestamp_uncertainty_reason")
            elif incident is not None:
                in_win, is_unc, reason = is_timestamp_in_incident_window(rec.event_time_utc, incident)
                rec.in_incident_window = in_win
                if is_unc:
                    rec.timestamp_uncertain = True
                    rec.timestamp_uncertainty_reason = reason
        else:
            ev_dt, is_unc, reason = parse_event_timestamp_safely(rec.event_time_utc)
            if is_unc:
                rec.timestamp_uncertain = True
                rec.timestamp_uncertainty_reason = reason
                rec.in_incident_window = False
            elif incident is not None:
                in_win, win_unc, win_reason = is_timestamp_in_incident_window(rec.event_time_utc, incident)
                rec.in_incident_window = in_win
                if win_unc:
                    rec.timestamp_uncertain = True
                    rec.timestamp_uncertainty_reason = win_reason
            else:
                rec.in_incident_window = True

    return stale_ids, superseded_ids


def is_valid_for_current_state(rec: DiagnosticCheckResult) -> bool:
    """Return True iff `rec` is an available, fresh, non-superseded observation with a reliable timestamp."""
    if rec.status != EvidenceStatus.AVAILABLE:
        return False
    if rec.is_stale or rec.freshness_status == "stale":
        return False
    if rec.is_superseded:
        return False
    if rec.timestamp_uncertain:
        return False
    return True
