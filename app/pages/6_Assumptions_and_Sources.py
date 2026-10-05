"""Page 6: Transparent Assumptions, Sources, and Data Provenance Audit.

Lists every physical, financial, and policy assumption in config/assumptions.yaml,
all regulatory feasibility rules in config/rules.yaml, and cryptographic hashes of all local datasets.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is in sys.path for robust imports from core
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
)

st.set_page_config(page_title="Assumptions & Sources - Feeder Solar DSS", page_icon="📚", layout="wide")

try:
    st.title("📚 Page 6: Transparent Assumptions, Rules & Data Provenance Audit")
    st.markdown(
        """
        Enforces **PROJECT_SPEC Section 0 Rule 2 & Rule 4**:
        *No hidden numbers.* Every physical, financial, agronomic, or regulatory parameter lives in configuration
        with an explicit unit, cited source, and engineering justification.
        """
    )

    assumptions = get_cached_assumptions()
    rules = get_cached_rules()
    provenance_list = get_dataset_provenance()

    # Summary metrics
    a_col1, a_col2, a_col3 = st.columns(3)
    with a_col1:
        st.metric("Total Parameters in assumptions.yaml", len(assumptions))
    with a_col2:
        st.metric("Total Rules in rules.yaml", len(rules))
    with a_col3:
        st.metric("Local Datasets Loaded", len(provenance_list))

    st.markdown("---")

    tab_assump, tab_rules, tab_prov = st.tabs(["📝 Config Assumptions Audit", "⚖️ Regulatory Rules Audit", "🔒 Local Datasets Provenance"])

    with tab_assump:
        st.subheader("Configuration Assumptions Audit (`config/assumptions.yaml`)")
        search_query = st.text_input("🔍 Search Assumptions by Key, Unit, or Source", "")

        assump_records = []
        for k, entry in sorted(assumptions.items()):
            if search_query.lower() in k.lower() or search_query.lower() in entry.source.lower() or search_query.lower() in entry.notes.lower():
                assump_records.append({
                    "Key": k,
                    "Value": str(entry.value),
                    "Unit": entry.unit,
                    "Type": entry.type.upper(),
                    "Cited Source": entry.source,
                    "Engineering Notes / Justification": entry.notes,
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
        st.subheader("Local Raw Datasets Provenance & Integrity Audit")
        st.caption("Verifies file existence, sizes, and SHA-256 cryptographic hashes for end-to-end data provenance.")

        prov_df = pd.DataFrame(provenance_list)
        prov_df.rename(
            columns={
                "dataset": "Dataset Name",
                "filename": "Raw Filename",
                "size_kb": "Size (KB)",
                "sha256": "SHA-256 Integrity Hash",
            },
            inplace=True,
        )
        st.dataframe(prov_df, use_container_width=True)

    render_disclaimer_footer()

except MissingInputError as e:
    st.error(f"Missing required configuration key: {e.key}")
    render_disclaimer_footer()
