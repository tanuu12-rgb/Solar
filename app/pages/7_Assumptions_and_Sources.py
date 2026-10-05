"""Page 7: Transparent Assumptions, Sources, and Data Provenance Audit.

Lists every physical, financial, and agronomic assumption in config/assumptions.yaml,
all regulatory rules in config/rules.yaml, cryptographic SHA-256 provenance of all 7 datasets,
and the architectural note on deterministic physics vs. machine learning.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from core.errors import MissingInputError
from app.state import (
    get_cached_assumptions,
    get_cached_rules,
    get_dataset_provenance,
    render_disclaimer_footer,
    save_scenario_inputs,
    get_illustrative_scenario_inputs,
)
from app.theme import (
    apply_theme,
    render_status_chip,
    render_urja_header,
)


def render_missing_input_card(error: object) -> None:
    key_name = getattr(error, "key", "Scenario Input")
    msg = getattr(error, "message", str(error)) or "This engineering stage requires specific feeder parameters that have not been configured yet."
    st.warning(
        f"⚠️ **Feeder Configuration Required:** `{key_name}`\n\n"
        f"{msg}\n\n"
        "Per **PROJECT_SPEC Section 0 Rule 1 & Rule 3 (Input Honesty)**, the system does not inject silent synthetic defaults. "
        "You can configure custom parameters on **Page 1: Inputs & Data**, or immediately load an illustrative case study for demonstration."
    )
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("✨ Load Illustrative Scenario (Bhatangali Demo)", type="primary", key=f"btn_load_demo_{key_name}"):
            save_scenario_inputs(get_illustrative_scenario_inputs())
            st.rerun()

st.set_page_config(
    page_title="ऊर्जाSetu - Assumptions & Provenance",
    page_icon="📚",
    layout="wide",
)

apply_theme()

render_urja_header(
    title="Assumptions & Cryptographic Provenance",
    subtitle="Audit all 72 engineering parameters, statutory rules, SHA-256 raw dataset hashes, and deterministic physics architecture.",
    badge_label="Audit & Provenance",
    icon="📚",
)

try:

    assumptions = get_cached_assumptions()
    rules = get_cached_rules()
    provenance_list = get_dataset_provenance()

    # Summary metrics
    a_col1, a_col2, a_col3, a_col4 = st.columns(4)
    with a_col1:
        st.metric("Assumptions in YAML", len(assumptions))
    with a_col2:
        st.metric("Statutory Rules in YAML", len(rules))
    with a_col3:
        st.metric("Raw Datasets Audited", len(provenance_list))
    with a_col4:
        st.metric("Missing Values", sum(1 for v in assumptions.values() if v.value is None))

    st.markdown(
        f"""
        **Provenance Status Legend:** &nbsp;
        {render_status_chip('sourced', 'SOURCED / ASSUMPTION')} &nbsp;
        {render_status_chip('user', 'USER-ENTERED')} &nbsp;
        {render_status_chip('illustrative', 'ILLUSTRATIVE SCENARIO')} &nbsp;
        {render_status_chip('check-only', 'CHECK-ONLY ARCHIVE')} &nbsp;
        {render_status_chip('missing', 'MISSING INPUT')}
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    tab_assump, tab_rules, tab_prov, tab_ml = st.tabs([
        "📝 Config Assumptions Audit",
        "⚖️ Regulatory Rules Audit",
        "🔒 Local Datasets Provenance",
        "🤖 Physics vs. ML Architecture Note",
    ])

    with tab_assump:
        st.subheader("Configuration Assumptions Audit (`config/assumptions.yaml`)")
        search_query = st.text_input("🔍 Search Assumptions by Key, Unit, or Source", "")

        assump_records = []
        for k, entry in sorted(assumptions.items()):
            if (
                search_query.lower() in k.lower()
                or search_query.lower() in entry.source.lower()
                or search_query.lower() in entry.notes.lower()
            ):
                assump_records.append({
                    "Parameter Key": k,
                    "Configured Value": str(entry.value) if entry.value is not None else "NULL",
                    "Unit": entry.unit,
                    "Type": entry.type.upper(),
                    "Cited Source": entry.source,
                    "Engineering Rationale / Notes": entry.notes,
                })

        st.write(f"Showing **{len(assump_records)}** of **{len(assumptions)}** assumptions:")
        st.dataframe(pd.DataFrame(assump_records), use_container_width=True, height=600)

    with tab_rules:
        st.subheader("Regulatory Screening Rules Audit (`config/rules.yaml`)")
        st.caption("Statutory feasibility constraints codified from MSEDCL circulars and PM-KUSUM guidelines.")

        rules_records = []
        for r in rules:
            rules_records.append({
                "Rule ID": r.id,
                "Description": r.description,
                "Parameter": r.parameter,
                "Operator": r.operator,
                "Threshold": str(r.threshold),
                "Unit": r.unit,
                "Severity": r.severity.upper(),
                "Originating Regulation": r.source,
                "Engineering Context": r.notes,
            })

        st.dataframe(pd.DataFrame(rules_records), use_container_width=True)

    with tab_prov:
        st.subheader("Local Raw Datasets Provenance & Cryptographic Integrity")
        st.caption("Verifies file existence, byte size, and SHA-256 cryptographic hashes for all 7 raw data assets.")

        prov_df = pd.DataFrame(provenance_list)
        prov_df.rename(
            columns={
                "dataset": "Dataset Name",
                "filename": "Raw Filename",
                "status": "Pipeline Status",
                "purpose": "Dataset Purpose & Scope",
                "size_kb": "Size (KB)",
                "sha256": "SHA-256 Integrity Hash",
            },
            inplace=True,
        )
        st.dataframe(prov_df, use_container_width=True)

    with tab_ml:
        st.subheader("Deterministic Engineering Physics vs. Machine Learning Architecture Note")
        st.markdown(
            """
            ### Why Deterministic Physics is Mandatory for DISCOM Decision Support
            In utility-scale agricultural feeder planning and statutory capital allocation under PM-KUSUM Component-C,
            decisions must be **legally defensible, auditable, and physically explainable**:

            1. **Regulatory Auditability:** Every rejection or approval decision produced by this system must reference
               an explicit engineering clause (e.g., MSEDCL Technical Circular No. 06.08.2024, CEA Grid Standards,
               or CERC Regulations). Black-box machine learning models cannot produce binding statutory explanations.
            2. **First-Principles Energy Conservation:** Solar generation is modeled with Hay-Davies transposition
               and Faiman cell temperature physics (`pvlib`), and battery state-of-charge is tracked with strict zero-tolerance
               conservation $\\Delta E = E_{\\text{in}} - E_{\\text{out}} - \\text{losses}$.
            3. **Agronomic Validity:** Irrigation demand is derived using FAO-56 dual crop coefficient formulas
               and Darcy-Weisbach friction head mechanics rather than historical billing proxies, which are severely
               distorted by unmetered flat-rate tariffs.

            ### Future Machine Learning Research Extensions
            While core statutory sizing relies on first-principles physics, machine learning offers high-value complementary extensions:
            - **Satellite NDVI Crop Stage Calibration:** Train computer vision models on Sentinel-2 multi-spectral imagery
              to automatically detect localized sowing dates and calibrate dynamic crop growth stages.
            - **Nowcasting Solar Irradiance:** Train temporal transformer or LSTM models on INSAT-3D satellite cloud imagery
              to generate 15-minute intra-day solar irradiance forecasts for active battery dispatch.
            - **Dynamic Pump Operating Point Inference:** Train physics-informed neural networks (PINNs) on feeder supervisory
              control and data acquisition (SCADA) telemetry to dynamically infer pump degradation and groundwater table drawdown.
            """
        )

    render_disclaimer_footer()

except MissingInputError as e:
    render_missing_input_card(e)
    render_disclaimer_footer()
