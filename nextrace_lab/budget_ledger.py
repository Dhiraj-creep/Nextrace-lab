"""Shared Suite-Wide AI Budget Ledger & Monotonic Deadline Enforcement (Stages 1A & 1B).

Stage 1A — SuiteAIBudgetLedger:
- Enforces per-run and per-suite model call limits, token ceilings, and estimated USD ceilings.
- Performs pre-dispatch reservation using a 1.25x safety margin on estimated input tokens plus
  configured `max_output_tokens`.
- Passes `max_output_tokens` to provider requests so completion tokens cannot exceed reserved output budget.
- Reconciles actual token/USD consumption only when a completed provider response returns reliable usage.
- NEVER releases reserved budget when a dispatched network/provider call fails or times out and
  server-side token consumption is uncertain; records `uncertain_consumption` explicitly.

Stage 1B — DeadlineTracker:
- Propagates remaining monotonic wall-clock budget to HTTP checks, TCP/DB checks, AI model requests,
  retry backoff waits, and subprocess executions.
- Supports an injectable `clock_fn` (default `time.monotonic`) for deterministic unit testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import threading
import time
from typing import Any, Callable, Optional


class DeadlineExceededError(TimeoutError):
    """Raised when the run's monotonic wall-clock deadline has been reached or exceeded."""


class BudgetReservationError(RuntimeError):
    """Raised when a pre-dispatch AI budget reservation exceeds run or suite limits."""

    def __init__(self, reason: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


class DeadlineTracker:
    """Monotonic wall-clock deadline tracker propagated across all check, model, and retry calls."""

    def __init__(
        self,
        max_wall_clock_sec: float = 20.0,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_wall_clock_sec = max(0.1, float(max_wall_clock_sec))
        self.clock_fn = clock_fn
        self.started_monotonic = self.clock_fn()
        self.deadline_monotonic = self.started_monotonic + self.max_wall_clock_sec

    def elapsed_sec(self) -> float:
        return max(0.0, self.clock_fn() - self.started_monotonic)

    def remaining_sec(self) -> float:
        return max(0.0, self.deadline_monotonic - self.clock_fn())

    def is_expired(self) -> bool:
        return self.clock_fn() >= self.deadline_monotonic

    def check_not_expired(self, context: str = "operation") -> float:
        rem = self.remaining_sec()
        if rem <= 0.0:
            raise DeadlineExceededError(
                f"Monotonic wall-clock deadline ({self.max_wall_clock_sec:.2f}s) exceeded before {context}."
            )
        return rem

    def effective_timeout(self, requested_timeout_sec: float, *, context: str = "call") -> float:
        """Return min(requested_timeout_sec, remaining_sec()) or raise DeadlineExceededError if expired."""
        rem = self.check_not_expired(context=context)
        return max(0.01, min(float(requested_timeout_sec), rem))

    def can_sleep_for_retry(self, backoff_sec: float, min_remaining_after_sleep_sec: float = 0.05) -> bool:
        """Return True only if sleeping `backoff_sec` still leaves time before the monotonic deadline."""
        return self.remaining_sec() >= (float(backoff_sec) + float(min_remaining_after_sleep_sec))


# Explicit per-million-token pricing table (USD) for pre-dispatch reservation and reconciliation
MODEL_PRICING_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    # (input_usd_per_1m, output_usd_per_1m)
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "mock-deterministic": (0.0, 0.0),
}

OVERRIDE_DEFAULT_PRICING_PER_1M_TOKENS: tuple[float, float] = (0.50, 2.00)


def resolve_model_pricing(
    model_name: str,
    *,
    custom_pricing: Optional[dict[str, tuple[float, float]]] = None,
    allow_unknown_pricing_override: bool = False,
) -> tuple[float, float]:
    """Resolve explicit (input_usd_per_1m, output_usd_per_1m) pricing for `model_name`.

    Raises `BudgetReservationError('unknown_model_pricing')` if `model_name` has no explicit
    pricing entry and `allow_unknown_pricing_override` is False.
    """
    lowered = (model_name or "").strip().lower()
    merged = dict(MODEL_PRICING_PER_1M_TOKENS)
    if custom_pricing:
        for k, v in custom_pricing.items():
            merged[k.lower()] = v

    if lowered in merged:
        return merged[lowered]
    for candidate, rates in merged.items():
        if candidate in lowered:
            return rates

    if allow_unknown_pricing_override:
        return OVERRIDE_DEFAULT_PRICING_PER_1M_TOKENS

    raise BudgetReservationError(
        f"unknown_model_pricing: model '{model_name}' has no explicit entry in MODEL_PRICING_PER_1M_TOKENS",
        details={"model_name": model_name, "reason": "unknown_model_pricing"},
    )


def estimate_usd_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    *,
    custom_pricing: Optional[dict[str, tuple[float, float]]] = None,
    allow_unknown_pricing_override: bool = False,
) -> float:
    """Compute estimated USD cost for given input and output token counts."""
    in_rate, out_rate = resolve_model_pricing(
        model_name,
        custom_pricing=custom_pricing,
        allow_unknown_pricing_override=allow_unknown_pricing_override,
    )
    return round((max(0, input_tokens) * in_rate + max(0, output_tokens) * out_rate) / 1_000_000.0, 8)


def estimate_prompt_tokens(text: str) -> int:
    """Heuristic token count estimate (~3.5 chars per token, minimum 16 tokens)."""
    if not text:
        return 16
    return max(16, math.ceil(len(text) / 3.5))


@dataclass
class ReservationTicket:
    """Represents a pre-dispatch budget reservation for a single model call."""

    ticket_id: str
    run_id: str
    model_name: str
    estimated_raw_input_tokens: int
    reserved_input_tokens: int  # includes 1.25x safety margin
    reserved_output_tokens: int  # equals max_output_tokens passed to provider
    reserved_total_tokens: int
    reserved_usd: float
    status: str = "reserved"  # reserved | reconciled | uncertain_unreleased
    actual_input_tokens: Optional[int] = None
    actual_output_tokens: Optional[int] = None
    actual_total_tokens: Optional[int] = None
    actual_usd: Optional[float] = None
    failure_reason: Optional[str] = None


@dataclass
class _RunLedgerState:
    run_id: str
    calls_reserved: int = 0
    calls_completed: int = 0
    calls_uncertain: int = 0
    tokens_committed: int = 0  # reconciled actuals + active reservations + uncertain unreleased reservations
    usd_committed: float = 0.0
    uncertain_tokens: int = 0
    uncertain_usd: float = 0.0


@dataclass
class SuiteAIBudgetLedger:
    """Shared suite-wide and per-run AI budget ledger with pre-dispatch reservation (Stage 1A)."""

    max_calls_per_run: int = 6
    max_calls_per_suite: int = 200
    max_tokens_per_run: int = 24_000
    max_tokens_per_suite: int = 500_000
    max_usd_per_run: float = 0.15
    max_usd_per_suite: float = 2.00
    max_output_tokens: int = 512
    input_safety_margin: float = 1.25
    allow_unknown_pricing_override: bool = False
    custom_model_pricing: dict[str, tuple[float, float]] = field(default_factory=dict)

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _suite_calls_reserved: int = field(default=0, init=False)
    _suite_calls_completed: int = field(default=0, init=False)
    _suite_calls_uncertain: int = field(default=0, init=False)
    _suite_tokens_committed: int = field(default=0, init=False)
    _suite_usd_committed: float = field(default=0.0, init=False)
    _suite_uncertain_tokens: int = field(default=0, init=False)
    _suite_uncertain_usd: float = field(default=0.0, init=False)
    _runs: dict[str, _RunLedgerState] = field(default_factory=dict, init=False)
    _tickets: dict[str, ReservationTicket] = field(default_factory=dict, init=False)
    _ticket_seq: int = field(default=0, init=False)

    def _get_run_state(self, run_id: str) -> _RunLedgerState:
        if run_id not in self._runs:
            self._runs[run_id] = _RunLedgerState(run_id=run_id)
        return self._runs[run_id]

    def reserve_before_dispatch(
        self,
        *,
        run_id: str,
        model_name: str,
        prompt_text: str = "",
        estimated_input_tokens: Optional[int] = None,
        requested_max_output_tokens: Optional[int] = None,
    ) -> ReservationTicket:
        """Reserve worst-case call, token (1.25x input + max_output_tokens), and USD budget BEFORE network dispatch."""
        with self._lock:
            run_state = self._get_run_state(run_id)
            raw_in = (
                int(estimated_input_tokens)
                if estimated_input_tokens is not None
                else estimate_prompt_tokens(prompt_text)
            )
            reserved_in = int(math.ceil(max(1, raw_in) * self.input_safety_margin))
            capped_out = min(
                int(requested_max_output_tokens or self.max_output_tokens),
                int(self.max_output_tokens),
            )
            reserved_total = reserved_in + capped_out
            usd_cap_active = (self.max_usd_per_run > 0.0) or (self.max_usd_per_suite > 0.0)
            reserved_usd = estimate_usd_cost(
                model_name,
                reserved_in,
                capped_out,
                custom_pricing=self.custom_model_pricing,
                allow_unknown_pricing_override=(self.allow_unknown_pricing_override or not usd_cap_active),
            )

            # Check per-run call limit
            if run_state.calls_reserved + 1 > self.max_calls_per_run:
                raise BudgetReservationError(
                    f"per_run_call_limit_exceeded ({run_state.calls_reserved + 1} > {self.max_calls_per_run})",
                    details={"scope": "run", "limit": "calls", "run_id": run_id},
                )
            # Check per-suite call limit
            if self._suite_calls_reserved + 1 > self.max_calls_per_suite:
                raise BudgetReservationError(
                    f"per_suite_call_limit_exceeded ({self._suite_calls_reserved + 1} > {self.max_calls_per_suite})",
                    details={"scope": "suite", "limit": "calls", "run_id": run_id},
                )
            # Check per-run token ceiling
            if run_state.tokens_committed + reserved_total > self.max_tokens_per_run:
                raise BudgetReservationError(
                    f"per_run_token_limit_exceeded ({run_state.tokens_committed + reserved_total} > {self.max_tokens_per_run})",
                    details={"scope": "run", "limit": "tokens", "run_id": run_id, "reserved_tokens": reserved_total},
                )
            # Check per-suite token ceiling
            if self._suite_tokens_committed + reserved_total > self.max_tokens_per_suite:
                raise BudgetReservationError(
                    f"per_suite_token_limit_exceeded ({self._suite_tokens_committed + reserved_total} > {self.max_tokens_per_suite})",
                    details={"scope": "suite", "limit": "tokens", "run_id": run_id, "reserved_tokens": reserved_total},
                )
            # Check per-run USD ceiling
            if run_state.usd_committed + reserved_usd > self.max_usd_per_run + 1e-12:
                raise BudgetReservationError(
                    f"per_run_usd_limit_exceeded (${run_state.usd_committed + reserved_usd:.6f} > ${self.max_usd_per_run:.6f})",
                    details={"scope": "run", "limit": "usd", "run_id": run_id, "reserved_usd": reserved_usd},
                )
            # Check per-suite USD ceiling
            if self._suite_usd_committed + reserved_usd > self.max_usd_per_suite + 1e-12:
                raise BudgetReservationError(
                    f"per_suite_usd_limit_exceeded (${self._suite_usd_committed + reserved_usd:.6f} > ${self.max_usd_per_suite:.6f})",
                    details={"scope": "suite", "limit": "usd", "run_id": run_id, "reserved_usd": reserved_usd},
                )

            self._ticket_seq += 1
            ticket_id = f"rsv-{self._ticket_seq:05d}"
            ticket = ReservationTicket(
                ticket_id=ticket_id,
                run_id=run_id,
                model_name=model_name,
                estimated_raw_input_tokens=raw_in,
                reserved_input_tokens=reserved_in,
                reserved_output_tokens=capped_out,
                reserved_total_tokens=reserved_total,
                reserved_usd=reserved_usd,
                status="reserved",
            )
            self._tickets[ticket_id] = ticket

            run_state.calls_reserved += 1
            run_state.tokens_committed += reserved_total
            run_state.usd_committed = round(run_state.usd_committed + reserved_usd, 8)

            self._suite_calls_reserved += 1
            self._suite_tokens_committed += reserved_total
            self._suite_usd_committed = round(self._suite_usd_committed + reserved_usd, 8)

            return ticket

    def reconcile_completed_call(
        self,
        ticket: ReservationTicket,
        *,
        actual_input_tokens: Optional[int],
        actual_output_tokens: Optional[int],
    ) -> ReservationTicket:
        """Reconcile a completed model call when reliable token counts are returned.

        If provider response omits reliable token usage, keep the conservative reservation intact.
        """
        with self._lock:
            stored = self._tickets.get(ticket.ticket_id, ticket)
            if stored.status != "reserved":
                return stored

            run_state = self._get_run_state(stored.run_id)
            if actual_input_tokens is None or actual_output_tokens is None or actual_input_tokens < 0 or actual_output_tokens < 0:
                # Token counts not reliably returned; retain conservative reservation and record uncertainty
                return self._mark_uncertain_locked(stored, reason="missing_provider_usage_metadata")

            actual_in = int(actual_input_tokens)
            # Enforce output token cap accounting
            actual_out = int(actual_output_tokens)
            actual_total = actual_in + actual_out
            usd_cap_active = (self.max_usd_per_run > 0.0) or (self.max_usd_per_suite > 0.0)
            actual_usd = estimate_usd_cost(
                stored.model_name,
                actual_in,
                actual_out,
                custom_pricing=self.custom_model_pricing,
                allow_unknown_pricing_override=(self.allow_unknown_pricing_override or not usd_cap_active),
            )

            token_delta = actual_total - stored.reserved_total_tokens
            usd_delta = actual_usd - stored.reserved_usd

            run_state.calls_completed += 1
            run_state.tokens_committed = max(0, run_state.tokens_committed + token_delta)
            run_state.usd_committed = round(max(0.0, run_state.usd_committed + usd_delta), 8)

            self._suite_calls_completed += 1
            self._suite_tokens_committed = max(0, self._suite_tokens_committed + token_delta)
            self._suite_usd_committed = round(max(0.0, self._suite_usd_committed + usd_delta), 8)

            stored.actual_input_tokens = actual_in
            stored.actual_output_tokens = actual_out
            stored.actual_total_tokens = actual_total
            stored.actual_usd = actual_usd
            stored.status = "reconciled"
            return stored

    def record_failed_dispatched_call(
        self,
        ticket: ReservationTicket,
        *,
        reason: str,
    ) -> ReservationTicket:
        """Record a call that failed AFTER network dispatch (timeout, HTTP 5xx, parse error, etc.).

        CRITICAL (Stage 1A): Does NOT release the reserved tokens or USD because server-side model
        execution may have already occurred and billed tokens.
        """
        with self._lock:
            stored = self._tickets.get(ticket.ticket_id, ticket)
            if stored.status != "reserved":
                return stored
            return self._mark_uncertain_locked(stored, reason=reason)

    def _mark_uncertain_locked(self, stored: ReservationTicket, reason: str) -> ReservationTicket:
        run_state = self._get_run_state(stored.run_id)
        run_state.calls_uncertain += 1
        run_state.uncertain_tokens += stored.reserved_total_tokens
        run_state.uncertain_usd = round(run_state.uncertain_usd + stored.reserved_usd, 8)

        self._suite_calls_uncertain += 1
        self._suite_uncertain_tokens += stored.reserved_total_tokens
        self._suite_uncertain_usd = round(self._suite_uncertain_usd + stored.reserved_usd, 8)

        stored.status = "uncertain_unreleased"
        stored.failure_reason = reason
        return stored

    def get_run_snapshot(self, run_id: str) -> dict[str, Any]:
        """Return a serializable snapshot of the run's AI budget ledger state."""
        with self._lock:
            run_state = self._get_run_state(run_id)
            return {
                "run_id": run_id,
                "calls_reserved": run_state.calls_reserved,
                "calls_completed": run_state.calls_completed,
                "calls_uncertain_unreleased": run_state.calls_uncertain,
                "tokens_committed": run_state.tokens_committed,
                "usd_committed": round(run_state.usd_committed, 8),
                "uncertain_consumption": {
                    "uncertain_calls": run_state.calls_uncertain,
                    "uncertain_tokens_reserved": run_state.uncertain_tokens,
                    "uncertain_usd_reserved": round(run_state.uncertain_usd, 8),
                },
                "limits": {
                    "max_calls_per_run": self.max_calls_per_run,
                    "max_tokens_per_run": self.max_tokens_per_run,
                    "max_usd_per_run": self.max_usd_per_run,
                    "max_output_tokens": self.max_output_tokens,
                    "input_safety_margin": self.input_safety_margin,
                },
            }

    def get_suite_snapshot(self) -> dict[str, Any]:
        """Return a serializable snapshot of the suite-wide AI budget ledger state."""
        with self._lock:
            return {
                "suite_calls_reserved": self._suite_calls_reserved,
                "suite_calls_completed": self._suite_calls_completed,
                "suite_calls_uncertain_unreleased": self._suite_calls_uncertain,
                "suite_tokens_committed": self._suite_tokens_committed,
                "suite_usd_committed": round(self._suite_usd_committed, 8),
                "uncertain_consumption": {
                    "uncertain_calls": self._suite_calls_uncertain,
                    "uncertain_tokens_reserved": self._suite_uncertain_tokens,
                    "uncertain_usd_reserved": round(self._suite_uncertain_usd, 8),
                },
                "limits": {
                    "max_calls_per_suite": self.max_calls_per_suite,
                    "max_tokens_per_suite": self.max_tokens_per_suite,
                    "max_usd_per_suite": self.max_usd_per_suite,
                    "max_calls_per_run": self.max_calls_per_run,
                    "max_tokens_per_run": self.max_tokens_per_run,
                    "max_usd_per_run": self.max_usd_per_run,
                    "max_output_tokens": self.max_output_tokens,
                    "input_safety_margin": self.input_safety_margin,
                },
            }
