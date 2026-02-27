#!/usr/bin/env python3
"""Interactive dashboard for Teiko assignment results."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "teiko.db"
OUT_DIR = ROOT / "outputs"


PART2_SQL = """
WITH totals AS (
    SELECT sample_id, SUM(count) AS total_count
    FROM cell_count
    GROUP BY sample_id
)
SELECT
    cc.sample_id AS sample,
    t.total_count,
    cc.population,
    cc.count,
    (cc.count * 100.0 / t.total_count) AS percentage
FROM cell_count cc
JOIN totals t ON cc.sample_id = t.sample_id
ORDER BY cc.sample_id, cc.population;
"""


PART3_SQL = """
WITH totals AS (
    SELECT sample_id, SUM(count) AS total_count
    FROM cell_count
    GROUP BY sample_id
)
SELECT
    p.project_id AS project,
    s.subject_id AS subject,
    sm.sample_id AS sample,
    cc.population,
    cc.count,
    (cc.count * 100.0 / t.total_count) AS percentage,
    s.response
FROM sample sm
JOIN subject s ON sm.subject_id = s.subject_id
JOIN project p ON s.project_id = p.project_id
JOIN cell_count cc ON sm.sample_id = cc.sample_id
JOIN totals t ON sm.sample_id = t.sample_id
WHERE
    s.condition = 'melanoma'
    AND s.treatment = 'miraclib'
    AND sm.sample_type = 'PBMC'
    AND s.response IN ('yes', 'no')
ORDER BY cc.population, s.response, sm.sample_id;
"""


@st.cache_data
def query_df(sql: str) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn)


def load_part4_summary() -> dict:
    path = OUT_DIR / "part4_summary.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def main() -> None:
    st.set_page_config(page_title="Teiko Immune Analysis Dashboard", layout="wide")
    st.title("Teiko Technical Assignment Dashboard")
    st.caption(
        "Clinical trial immune-cell analysis for miraclib."
    )

    if not DB_PATH.exists():
        st.error("Database not found. Run `python load_data.py` first.")
        st.stop()

    st.header("Part 2: Per-sample Relative Frequencies")
    part2 = query_df(PART2_SQL)
    sample_filter = st.selectbox("Filter by sample", options=["All"] + sorted(part2["sample"].unique().tolist()))
    if sample_filter != "All":
        part2_view = part2[part2["sample"] == sample_filter].copy()
    else:
        part2_view = part2
    st.dataframe(part2_view, use_container_width=True)

    st.header("Part 3: Responder vs Non-Responder (Melanoma, Miraclib, PBMC)")
    part3 = query_df(PART3_SQL)
    populations = sorted(part3["population"].unique().tolist())
    selected_pops = st.multiselect(
        "Populations to display",
        options=populations,
        default=populations,
    )
    part3_view = part3[part3["population"].isin(selected_pops)]
    fig = px.box(
        part3_view,
        x="population",
        y="percentage",
        color="response",
        points="all",
        title="Relative frequencies by response group",
        labels={"percentage": "Relative Frequency (%)", "population": "Population", "response": "Response"},
    )
    st.plotly_chart(fig, use_container_width=True)

    stats_path = OUT_DIR / "part3_population_significance.csv"
    if stats_path.exists():
        stats = pd.read_csv(stats_path)
        st.subheader("Significance Results")
        st.dataframe(stats, use_container_width=True)
        significant = stats[stats["significant_at_0_05_fdr"] == True]["population"].tolist()  # noqa: E712
        st.markdown(
            "**Significant populations (FDR < 0.05):** "
            + (", ".join(significant) if significant else "None")
        )
    else:
        st.info("Run `python run_analysis.py` to generate significance results.")

    st.header("Part 4: Baseline Subset Analysis")
    part4 = load_part4_summary()
    if not part4:
        st.info("Run `python run_analysis.py` to generate Part 4 summary outputs.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Samples per Project")
        st.dataframe(pd.DataFrame(part4.get("samples_per_project", [])), use_container_width=True)
    with col2:
        st.subheader("Subjects by Response")
        st.dataframe(pd.DataFrame(part4.get("subjects_by_response", [])), use_container_width=True)
    with col3:
        st.subheader("Subjects by Sex")
        st.dataframe(pd.DataFrame(part4.get("subjects_by_sex", [])), use_container_width=True)

    avg_val = part4.get("melanoma_male_responder_avg_b_cell_time0")
    st.metric(
        "Melanoma males: average B cells for responders at time=0",
        f"{avg_val:.2f}" if avg_val is not None else "N/A",
    )


if __name__ == "__main__":
    main()
