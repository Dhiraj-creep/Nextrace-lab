"""NexTrace Research Dashboard Theme & Custom CSS.

Provides mission-control dark observability styling, semantic badges,
timeline cards, KPI tiles, and responsive glassmorphism layouts.
"""

from __future__ import annotations

import streamlit as st

# Color Palette Constants
COLOR_BG_DARK = "#0B0F19"
COLOR_BG_CARD = "#111827"
COLOR_BG_ELEVATED = "#1E293B"
COLOR_BORDER = "rgba(255, 255, 255, 0.08)"
COLOR_BORDER_FOCUS = "#00E5FF"
COLOR_ACCENT = "#00E5FF"
COLOR_ACCENT_ALT = "#38BDF8"
COLOR_ACCENT_PURPLE = "#818CF8"

COLOR_SUCCESS = "#10B981"
COLOR_SUCCESS_BG = "rgba(16, 185, 129, 0.12)"
COLOR_SUCCESS_BORDER = "rgba(16, 185, 129, 0.3)"

COLOR_WARNING = "#F59E0B"
COLOR_WARNING_BG = "rgba(245, 158, 11, 0.12)"
COLOR_WARNING_BORDER = "rgba(245, 158, 11, 0.3)"

COLOR_DANGER = "#EF4444"
COLOR_DANGER_BG = "rgba(239, 68, 68, 0.12)"
COLOR_DANGER_BORDER = "rgba(239, 68, 68, 0.3)"

COLOR_MUTED = "#94A3B8"
COLOR_MUTED_BG = "rgba(148, 163, 184, 0.08)"


CUSTOM_CSS = """
<style>
/* ---------------- Font Stack & Base Resets ---------------- */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", Helvetica, Arial, sans-serif;
    color: #F3F4F6;
    letter-spacing: -0.01em;
}

code, pre, .mono-text {
    font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
}

/* Hide default streamlit padding and header decoration */
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 96% !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

/* ---------------- Hero Header Container ---------------- */
.nxt-hero {
    background: linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(15, 23, 42, 0.85) 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 20px;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
    position: relative;
    overflow: hidden;
}

.nxt-hero::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #00E5FF 0%, #3B82F6 50%, #8B5CF6 100%);
}

.nxt-hero-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 8px;
}

.nxt-brand {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: #FFFFFF;
    display: inline-flex;
    align-items: center;
    gap: 10px;
}

.nxt-brand-glow {
    color: #00E5FF;
    text-shadow: 0 0 16px rgba(0, 229, 255, 0.4);
}

.nxt-tagline {
    font-size: 14px;
    color: #94A3B8;
    margin-top: 4px;
    font-weight: 400;
}

.nxt-badges-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.nxt-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #E2E8F0;
}

.nxt-badge-green {
    background: rgba(16, 185, 129, 0.15);
    border-color: rgba(16, 185, 129, 0.4);
    color: #34D399;
}

.nxt-badge-amber {
    background: rgba(245, 158, 11, 0.15);
    border-color: rgba(245, 158, 11, 0.4);
    color: #FBBF24;
}

.nxt-badge-cyan {
    background: rgba(0, 229, 255, 0.15);
    border-color: rgba(0, 229, 255, 0.4);
    color: #00E5FF;
}

.nxt-pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: currentColor;
    box-shadow: 0 0 8px currentColor;
    display: inline-block;
}

/* ---------------- Workflow Strip ---------------- */
.nxt-workflow-strip {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-top: 18px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
}

@media (max-width: 900px) {
    .nxt-workflow-strip {
        grid-template-columns: repeat(2, 1fr);
    }
}

.nxt-workflow-step {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.nxt-step-num {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    background: #00E5FF;
    color: #0B0F19;
    font-size: 11px;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.nxt-step-text {
    font-size: 12px;
    font-weight: 600;
    color: #E2E8F0;
}

.nxt-step-sub {
    font-size: 11px;
    color: #64748B;
    display: block;
}

/* ---------------- Scenario Info Card ---------------- */
.nxt-scenario-box {
    background: #111827;
    border: 1px solid rgba(0, 229, 255, 0.2);
    border-left: 4px solid #00E5FF;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 20px;
}

.nxt-scenario-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 6px;
}

.nxt-scenario-name {
    font-size: 15px;
    font-weight: 700;
    color: #FFFFFF;
}

.nxt-scenario-desc {
    font-size: 13px;
    color: #94A3B8;
    line-height: 1.5;
}

.nxt-chip-list {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 10px;
}

.nxt-chip {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.06);
    color: #CBD5E1;
    font-family: "JetBrains Mono", monospace;
}

/* ---------------- Verdict Banner ---------------- */
.nxt-verdict {
    border-radius: 12px;
    padding: 18px 24px;
    margin-bottom: 22px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
    box-shadow: 0 4px 20px -5px rgba(0, 0, 0, 0.4);
}

.nxt-verdict-success {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(6, 78, 59, 0.25) 100%);
    border: 1px solid rgba(16, 185, 129, 0.4);
    border-left: 6px solid #10B981;
}

.nxt-verdict-warning {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(120, 53, 15, 0.25) 100%);
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-left: 6px solid #F59E0B;
}

.nxt-verdict-danger {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(127, 29, 29, 0.25) 100%);
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-left: 6px solid #EF4444;
}

.nxt-verdict-title {
    font-size: 18px;
    font-weight: 800;
    color: #FFFFFF;
    display: flex;
    align-items: center;
    gap: 8px;
}

.nxt-verdict-sub {
    font-size: 13px;
    color: #CBD5E1;
    margin-top: 4px;
}

/* ---------------- KPI Metric Cards ---------------- */
.nxt-kpi-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 12px;
    margin-bottom: 24px;
}

@media (max-width: 1200px) {
    .nxt-kpi-grid {
        grid-template-columns: repeat(3, 1fr);
    }
}
@media (max-width: 700px) {
    .nxt-kpi-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

.nxt-kpi-card {
    background: #111827;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.15s ease, border-color 0.15s ease;
}

.nxt-kpi-card:hover {
    border-color: rgba(0, 229, 255, 0.3);
    transform: translateY(-2px);
}

.nxt-kpi-label {
    font-size: 11px;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}

.nxt-kpi-value {
    font-size: 20px;
    font-weight: 800;
    color: #FFFFFF;
    word-break: break-word;
}

.nxt-kpi-footer {
    font-size: 11px;
    color: #64748B;
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* Progress bar inside KPI */
.nxt-prog-bar {
    width: 100%;
    height: 6px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 8px;
}

.nxt-prog-fill {
    height: 100%;
    border-radius: 4px;
    background: linear-gradient(90deg, #00E5FF, #3B82F6);
}

/* ---------------- Investigation Timeline ---------------- */
.nxt-timeline {
    position: relative;
    padding-left: 28px;
    margin: 20px 0;
}

.nxt-timeline::before {
    content: "";
    position: absolute;
    left: 11px;
    top: 8px;
    bottom: 8px;
    width: 2px;
    background: rgba(255, 255, 255, 0.12);
}

.nxt-timeline-item {
    position: relative;
    margin-bottom: 16px;
}

.nxt-timeline-node {
    position: absolute;
    left: -28px;
    top: 14px;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #111827;
    border: 2px solid #00E5FF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 800;
    color: #00E5FF;
    z-index: 2;
}

.nxt-timeline-card {
    background: #111827;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 16px 20px;
    transition: border-color 0.15s ease;
}

.nxt-timeline-card:hover {
    border-color: rgba(255, 255, 255, 0.18);
}

.nxt-timeline-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 8px;
}

.nxt-timeline-title {
    font-size: 14px;
    font-weight: 700;
    color: #FFFFFF;
    display: flex;
    align-items: center;
    gap: 8px;
}

.nxt-timeline-rationale {
    font-size: 13px;
    color: #94A3B8;
    line-height: 1.5;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 8px;
    padding: 10px 14px;
    margin-top: 10px;
    border-left: 3px solid #3B82F6;
}

/* ---------------- Hypothesis Cards ---------------- */
.nxt-hypo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
    margin: 16px 0;
}

.nxt-hypo-card {
    background: #111827;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.nxt-hypo-card-supported {
    border-color: rgba(16, 185, 129, 0.4);
    box-shadow: 0 4px 16px -4px rgba(16, 185, 129, 0.15);
}

.nxt-hypo-card-refuted {
    border-color: rgba(239, 68, 68, 0.3);
    opacity: 0.85;
}

.nxt-hypo-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
}

.nxt-hypo-title {
    font-size: 14px;
    font-weight: 700;
    color: #FFFFFF;
}

.nxt-confidence-label {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: #94A3B8;
    margin-top: 12px;
    margin-bottom: 4px;
}

/* ---------------- Evidence Board ---------------- */
.nxt-evidence-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 14px;
    margin: 16px 0;
}

.nxt-evidence-card {
    background: #111827;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.nxt-ev-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.nxt-ev-title {
    font-size: 13px;
    font-weight: 700;
    color: #FFFFFF;
}

.nxt-ev-summary {
    font-size: 12px;
    color: #94A3B8;
    line-height: 1.4;
    margin-bottom: 12px;
}

.nxt-ev-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11px;
    color: #64748B;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 8px;
    margin-top: auto;
}

/* ---------------- Trust & Reliability Box ---------------- */
.nxt-trust-box {
    background: #0F172A;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 18px 22px;
    margin-top: 20px;
}

.nxt-trust-title {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #38BDF8;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.nxt-trust-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
}

@media (max-width: 800px) {
    .nxt-trust-grid {
        grid-template-columns: 1fr;
    }
}

.nxt-trust-item {
    font-size: 12px;
    color: #CBD5E1;
    line-height: 1.5;
}

.nxt-trust-item strong {
    color: #F8FAFC;
}

/* ---------------- Takeaways Card ---------------- */
.nxt-takeaways-card {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-left: 4px solid #38BDF8;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 20px;
}

.nxt-takeaways-title {
    font-size: 15px;
    font-weight: 700;
    color: #38BDF8;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.nxt-takeaways-body {
    font-size: 13px;
    color: #E2E8F0;
    line-height: 1.6;
}

/* Override Streamlit Button Styling */
div.stButton > button:first-child {
    background: linear-gradient(135deg, #00E5FF 0%, #0099FF 100%) !important;
    color: #0B0F19 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 10px 24px !important;
    box-shadow: 0 4px 14px rgba(0, 229, 255, 0.3) !important;
    transition: all 0.2s ease !important;
}

div.stButton > button:first-child:hover {
    box-shadow: 0 6px 20px rgba(0, 229, 255, 0.5) !important;
    transform: translateY(-1px) !important;
}

/* Custom Tabs Styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 14px;
    color: #94A3B8;
}

.stTabs [aria-selected="true"] {
    background-color: rgba(255, 255, 255, 0.05) !important;
    color: #00E5FF !important;
    border-bottom: 2px solid #00E5FF !important;
}
</style>
"""


def apply_theme() -> None:
    """Inject the dark mission-control stylesheet."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
