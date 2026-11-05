"""NexTrace Streamlit Research Dashboard (Stage 10).

Modern dark mission-control interface for autonomous evidence-based root cause diagnosis:
1. Interactive Single-Run Investigator across both `orders_app` and `inventory_app`,
   all 23 scenarios, E0–E5 conditions, budgets, and all 9 diagnostic methods.
2. Saved Comparative Experiment Viewer: loads artifacts/experiments/<experiment_id>/summary.json,
   displays leaderboard comparison, split analytics, and run traces.
3. About & Evaluation Protocol: comprehensive guide for hackathon and competition judges.
4. Cross-process LabExecutionLock status indicator and safe lock handling.
"""

from __future__ import annotations

import json
from typing import Any, Optional
import streamlit as st

from nextrace_lab.baseline import SUPPORTED_METHODS
from nextrace_lab.controller import FAULT_CATALOG
from nextrace_lab.experiment import ARTIFACTS_DIR, run_single_experiment
from nextrace_lab.lab_lock import LabLockBusyError, get_lock_status
from nextrace_lab.schemas import EvidenceCondition
from nextrace_lab.ui_components import (
    render_about_tab,
    render_candidate_scores_explorer,
    render_evidence_board,
    render_glossary_sidebar,
    render_hero,
    render_hypotheses_cards,
    render_investigation_timeline,
    render_kpi_cards,
    render_method_leaderboard,
    render_reliability_panel,
    render_scenario_info_card,
    render_takeaways,
    render_verdict_banner,
)
from nextrace_lab.ui_theme import apply_theme


def _list_saved_experiments() -> list[str]:
    """Return sorted list of saved experiment directory names containing summary.json."""
    if not ARTIFACTS_DIR.exists():
        return []
    dirs = [d.name for d in ARTIFACTS_DIR.iterdir() if d.is_dir() and (d / "summary.json").exists()]
    return sorted(dirs, reverse=True)


@st.cache_data
def _load_experiment_payload(selected_exp: str) -> dict[str, Any]:
    """Cache and load saved experiment summary payload."""
    summary_file = ARTIFACTS_DIR / selected_exp / "summary.json"
    with open(summary_file, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    st.set_page_config(
        page_title="NexTrace Lab — Autonomous Root Cause Diagnosis",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Inject dark mission-control styling
    apply_theme()

    # Sidebar: Lab Execution Lock & Control Panel
    with st.sidebar:
        st.markdown("### 🎛️ Control Panel")

        st.subheader("Lab Execution Lock")
        lock_info = get_lock_status()
        if lock_info.get("locked"):
            st.error(
                f"🔒 **LOCKED by PID `{lock_info.get('pid')}`**\n\n"
                f"Op: `{lock_info.get('operation')}`\n\n"
                f"Age: `{lock_info.get('age_sec')}s`"
            )
        else:
            st.success("🟢 **Lab Lock: Unlocked & Ready**")

        st.subheader("Execution Runtime")
        runtime_mode = st.selectbox(
            "Runtime Environment",
            options=["local", "docker", "auto"],
            index=0,
            help="Default 'local' is fast, standalone, and optimal for presentations. 'docker' connects to live PostgreSQL 16 & Redis 7 containers.",
        )

        st.subheader("Presentation Mode")
        demo_mode = st.toggle(
            "🎯 Showcase Demo Preset",
            value=True,
            help="Preselects the recommended live judge showcase scenario (Redis Cache Outage under E0 with scored_adaptive_v2).",
        )

        # Glossary & Quick Guide expander
        render_glossary_sidebar()

        st.markdown("---")
        st.caption("NexTrace Prototype v0.4.0 • Aavishkar Research")

    # Render Hero Header
    render_hero(runtime_mode=runtime_mode, lock_info=lock_info)

    # Primary Navigation Tabs
    tab_live, tab_saved, tab_about = st.tabs([
        "🔬 Interactive Single-Run Investigator",
        "📊 Saved Experiment Suites & Analytics",
        "📖 About & Research Overview"
    ])

    # ---------------- TAB 1: LIVE INVESTIGATOR ----------------
    with tab_live:
        scenario_list = list(FAULT_CATALOG.keys())
        default_scen = "inv_fault_cache_unavailable" if demo_mode and "inv_fault_cache_unavailable" in scenario_list else scenario_list[0]
        default_scen_idx = scenario_list.index(default_scen) if default_scen in scenario_list else 0

        st.markdown("### 🛠️ Configure Controlled Investigation")

        # Two-row clean layout with helpful tooltips
        row1_col1, row1_col2, row1_col3 = st.columns([2, 1, 1])
        with row1_col1:
            scenario = st.selectbox(
                "Failure Scenario (orders_app & inventory_app)",
                options=scenario_list,
                index=default_scen_idx,
                help="Select from 23 controlled scenarios spanning 6 splits across Orders and Inventory topologies.",
            )
        with row1_col2:
            condition = st.selectbox(
                "Evidence Condition",
                options=["E0", "E1", "E2", "E3", "E4", "E5"],
                index=0,
                help="E0: Full observability. E1: Missing logs. E2: Missing DB config. E3: Missing logs + config. E4: Missing metrics. E5: Stale metrics.",
            )
        with row1_col3:
            budget = st.slider(
                "Diagnostic Budget (cost units)",
                min_value=2,
                max_value=12,
                value=8,
                step=1,
                help="Maximum cost units the selector is allowed to consume before forced termination.",
            )

        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            method_options = list(SUPPORTED_METHODS)
            default_m_idx = method_options.index("scored_adaptive_v2") if "scored_adaptive_v2" in method_options else 0
            method = st.selectbox(
                "Diagnostic Method",
                options=method_options,
                index=default_m_idx,
                help="scored_adaptive_v2 picks checks maximizing Distinguishing Power / Cost. Also supports checklists, rule-based, and AI methods.",
            )
        with row2_col2:
            stopping_mode = st.selectbox(
                "Stopping Policy Mode",
                options=["default", "first_supported_cause", "investigate_additional_causes", "fixed_no_early_stop"],
                index=0,
                help="first_supported_cause stops at first verified fault. investigate_additional_causes continues to uncover masked or multi-faults.",
            )

        ai_provider = "mock-deterministic"
        if "ai_" in method:
            ai_provider = st.selectbox(
                "AI Provider Adapter",
                options=["mock-deterministic", "gemini", "openai"],
                index=0,
                help="mock-deterministic is an offline test adapter labeled as non-real-AI for reproducibility.",
            )

        # Show styled scenario card
        scen_meta = FAULT_CATALOG[scenario]
        render_scenario_info_card(scenario, scen_meta)

        # Execution Action
        run_btn = st.button("🚀 Execute Scenario & Diagnose", type="primary")

        if run_btn:
            try:
                eff_stopping = None if stopping_mode == "default" else stopping_mode
                spinner_msg = (
                    f"Executing `{scenario}` under `{condition}` with `{method}` "
                    f"(runtime={runtime_mode}, budget={budget})..."
                )
                with st.spinner(spinner_msg):
                    report, score = run_single_experiment(
                        scenario=scenario,  # type: ignore[arg-type]
                        evidence_condition=EvidenceCondition(condition),
                        budget_limit=budget,
                        method_name=method,
                        runtime=runtime_mode,
                        ai_provider=ai_provider,  # type: ignore[arg-type]
                        stopping_policy_mode=eff_stopping,
                    )

                # 1. Verdict Banner
                render_verdict_banner(report, score)

                # 2. Top KPI Cards
                render_kpi_cards(report, score)

                # 3. Investigation Narrative Timeline
                st.markdown("#### 📜 Investigation Narrative (Step-by-Step Decision Log)")
                render_investigation_timeline(report.decision_log)

                # 4. Candidate Score Explorer (Plotly Horizontal Bar Chart)
                render_candidate_scores_explorer(report.decision_log)

                # 5. Final Hypothesis State Board
                render_hypotheses_cards(report.final_hypotheses)

                # 6. Evidence Board
                render_evidence_board(report.evidence_records)

                # 7. Conflicts (if any)
                if report.conflicts_detected:
                    st.warning("⚠️ Conflicting Observations Detected During Investigation:")
                    st.dataframe([c.model_dump() for c in report.conflicts_detected], use_container_width=True)

                # 8. Reliability & Trust Panel
                render_reliability_panel(report)

                # 9. Raw Data & JSON Export
                with st.expander("📦 Raw Diagnostic Artifacts & JSON Export"):
                    col_dl1, col_dl2 = st.columns([1, 4])
                    with col_dl1:
                        st.download_button(
                            label="⬇️ Download Report JSON",
                            data=json.dumps(report.model_dump(), indent=2),
                            file_name=f"nextrace_report_{report.run_id}.json",
                            mime="application/json",
                        )
                    with col_dl2:
                        st.caption(f"Run ID: `{report.run_id}` | Method Version: `{report.method_version}` | Gate Version: `{report.evidence_gate_version}`")

                    st.markdown("**Raw Decision Log:**")
                    st.dataframe([d.model_dump() for d in report.decision_log], use_container_width=True)

                    st.markdown("**Raw Evidence Records:**")
                    st.dataframe([r.model_dump() for r in report.evidence_records], use_container_width=True)

                    st.markdown("**Raw Hypothesis States:**")
                    st.dataframe([h.model_dump() for h in report.final_hypotheses], use_container_width=True)

            except LabLockBusyError as exc:
                st.error(f"🛑 **Lab Execution Lock Busy**: {exc}\n\nAnother test or diagnostic process is currently executing. Wait a moment and try again.")
            except Exception as exc:
                st.error(f"❌ **Investigation Error**: {exc}")

    # ---------------- TAB 2: SAVED EXPERIMENTS ----------------
    with tab_saved:
        st.markdown("### 📊 Empirical Evaluation & Comparative Analytics")
        exp_ids = _list_saved_experiments()

        if not exp_ids:
            st.warning("No saved experiment suites found in `artifacts/experiments/`. Run `python -m nextrace_lab run-experiments` to generate suites.")
        else:
            col_sel1, col_sel2 = st.columns([2, 1])
            with col_sel1:
                selected_exp = st.selectbox("Select Experiment Suite", options=exp_ids, index=0)
            with col_sel2:
                st.caption(f"Total Suites Saved: **{len(exp_ids)}**")

            payload = _load_experiment_payload(selected_exp)
            manifest = payload.get("manifest", {})
            summary = manifest.get("summary", {})
            scores = payload.get("scores", [])

            # Header Metadata Card
            st.markdown(
                f"""
                <div class="nxt-scenario-box">
                    <div class="nxt-scenario-header">
                        <span class="nxt-scenario-name">📁 Suite: <code>{manifest.get('experiment_id', selected_exp)}</code></span>
                        <div>
                            <span class="nxt-badge">Created: {manifest.get('created_at_utc', 'N/A')}</span>
                            <span class="nxt-badge nxt-badge-cyan">Runtime: {manifest.get('runtime_mode', 'N/A')} ({manifest.get('backend_name', 'N/A')})</span>
                        </div>
                    </div>
                    <div style="font-size:12px;color:#94A3B8;margin-top:6px;">
                        <strong>Stopping Mode:</strong> <code>{manifest.get('stopping_policy_mode', 'default')}</code> | 
                        <strong>Seed:</strong> <code>{manifest.get('random_seed', 'N/A')}</code> | 
                        <strong>Counterbalanced:</strong> <code>{manifest.get('counterbalance_methods', False)}</code>
                    </div>
                    <div style="margin-top:8px;">
                        <span style="font-size:11px;color:#94A3B8;">Source Content Manifest Digest (SHA-256):</span><br>
                        <code style="font-size:11px;color:#38BDF8;word-break:break-all;">{manifest.get('content_manifest_digest_sha256', 'Verified')}</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Auto-computed takeaways
            render_takeaways(summary, manifest)

            # Method Leaderboard with Plotly Chart & Table
            by_method = summary.get("by_method", {})
            if by_method:
                render_method_leaderboard(by_method)

            # Split Performance
            by_split = summary.get("by_split", {})
            if by_split:
                st.markdown("#### 📂 Performance by Scenario Split")
                st.dataframe([{"Split": sp, **stats} for sp, stats in by_split.items()], use_container_width=True)

            # AI Budget Ledger (if present)
            if manifest.get("suite_ai_budget_ledger"):
                with st.expander("🤖 Suite AI Budget Ledger Snapshot"):
                    st.json(manifest["suite_ai_budget_ledger"])

            # Scored runs table
            st.markdown("#### 📋 All Scored Individual Runs in Suite")
            if scores:
                st.dataframe(scores, use_container_width=True)
            else:
                st.info("No individual scored run records stored in this suite.")

    # ---------------- TAB 3: ABOUT & JUDGE GUIDE ----------------
    with tab_about:
        render_about_tab()


if __name__ == "__main__":
    main()
