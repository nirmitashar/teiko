#!/usr/bin/env python3
"""Run Parts 2-4 analysis outputs from the SQLite database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "teiko.db"
OUT_DIR = ROOT / "outputs"


PART2_SQL = """
WITH totals AS (
    SELECT
        sample_id,
        SUM(count) AS total_count
    FROM cell_count
    GROUP BY sample_id
)
SELECT
    cc.sample_id AS sample,
    t.total_count,
    cc.population,
    cc.count,
    ROUND((cc.count * 100.0 / t.total_count), 4) AS percentage
FROM cell_count cc
JOIN totals t ON cc.sample_id = t.sample_id
ORDER BY cc.sample_id, cc.population;
"""


PART3_SQL = """
WITH totals AS (
    SELECT
        sample_id,
        SUM(count) AS total_count
    FROM cell_count
    GROUP BY sample_id
)
SELECT
    p.project_id AS project,
    s.subject_id AS subject,
    sm.sample_id AS sample,
    sm.time_from_treatment_start,
    cc.population,
    cc.count,
    t.total_count,
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


PART4_BASELINE_SQL = """
SELECT
    p.project_id AS project,
    s.subject_id AS subject,
    s.response,
    s.sex,
    sm.sample_id AS sample,
    sm.time_from_treatment_start,
    sm.sample_type,
    s.condition,
    s.treatment,
    MAX(CASE WHEN cc.population = 'b_cell' THEN cc.count END) AS b_cell
FROM sample sm
JOIN subject s ON sm.subject_id = s.subject_id
JOIN project p ON s.project_id = p.project_id
JOIN cell_count cc ON sm.sample_id = cc.sample_id
WHERE
    s.condition = 'melanoma'
    AND s.treatment = 'miraclib'
    AND sm.sample_type = 'PBMC'
    AND sm.time_from_treatment_start = 0
GROUP BY
    p.project_id, s.subject_id, s.response, s.sex,
    sm.sample_id, sm.time_from_treatment_start, sm.sample_type, s.condition, s.treatment
ORDER BY project, subject, sample;
"""


def ensure_db_exists() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run `python load_data.py` first."
        )


def build_part2(conn: sqlite3.Connection) -> pd.DataFrame:
    summary = pd.read_sql_query(PART2_SQL, conn)
    summary.to_csv(OUT_DIR / "part2_sample_population_frequencies.csv", index=False)
    return summary


def build_part3(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_sql_query(PART3_SQL, conn)
    df.to_csv(OUT_DIR / "part3_melanoma_miraclib_pbmc_percentages.csv", index=False)

    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(12, 6))
    ax = sns.boxplot(data=df, x="population", y="percentage", hue="response")
    ax.set_title("Melanoma PBMC Relative Frequencies: Miraclib Responders vs Non-Responders")
    ax.set_xlabel("Population")
    ax.set_ylabel("Relative Frequency (%)")
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "part3_responder_vs_nonresponder_boxplot.png", dpi=200)
    plt.close()

    rows = []
    for population, g in df.groupby("population"):
        responders = g[g["response"] == "yes"]["percentage"]
        nonresponders = g[g["response"] == "no"]["percentage"]
        stat, pval = mannwhitneyu(responders, nonresponders, alternative="two-sided")
        rows.append(
            {
                "population": population,
                "n_responders": int(responders.size),
                "n_nonresponders": int(nonresponders.size),
                "responders_median_pct": round(float(responders.median()), 4),
                "nonresponders_median_pct": round(float(nonresponders.median()), 4),
                "mannwhitney_u": float(stat),
                "p_value": float(pval),
            }
        )

    stats = pd.DataFrame(rows).sort_values("p_value").reset_index(drop=True)
    reject, p_adj, _, _ = multipletests(stats["p_value"].values, alpha=0.05, method="fdr_bh")
    stats["p_value_fdr_bh"] = p_adj
    stats["significant_at_0_05_fdr"] = reject
    stats.to_csv(OUT_DIR / "part3_population_significance.csv", index=False)
    return df, stats


def build_part4(conn: sqlite3.Connection) -> dict:
    baseline = pd.read_sql_query(PART4_BASELINE_SQL, conn)
    baseline.to_csv(OUT_DIR / "part4_baseline_melanoma_miraclib_pbmc_samples.csv", index=False)

    by_project = (
        baseline.groupby("project")["sample"]
        .nunique()
        .rename("n_samples")
        .reset_index()
        .sort_values("project")
    )
    by_project.to_csv(OUT_DIR / "part4_samples_per_project.csv", index=False)

    by_response = (
        baseline[["subject", "response"]]
        .drop_duplicates()
        .groupby("response")["subject"]
        .nunique()
        .rename("n_subjects")
        .reset_index()
        .sort_values("response")
    )
    by_response.to_csv(OUT_DIR / "part4_subjects_by_response.csv", index=False)

    by_sex = (
        baseline[["subject", "sex"]]
        .drop_duplicates()
        .groupby("sex")["subject"]
        .nunique()
        .rename("n_subjects")
        .reset_index()
        .sort_values("sex")
    )
    by_sex.to_csv(OUT_DIR / "part4_subjects_by_sex.csv", index=False)

    male_resp = baseline[(baseline["sex"] == "M") & (baseline["response"] == "yes")]
    avg_b_cell = round(float(male_resp["b_cell"].mean()), 2) if not male_resp.empty else None

    summary = {
        "subset_filter": {
            "condition": "melanoma",
            "treatment": "miraclib",
            "sample_type": "PBMC",
            "time_from_treatment_start": 0,
        },
        "samples_per_project": by_project.to_dict(orient="records"),
        "subjects_by_response": by_response.to_dict(orient="records"),
        "subjects_by_sex": by_sex.to_dict(orient="records"),
        "melanoma_male_responder_avg_b_cell_time0": avg_b_cell,
    }
    (OUT_DIR / "part4_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    ensure_db_exists()
    OUT_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        _ = build_part2(conn)
        _, stats = build_part3(conn)
        part4 = build_part4(conn)

    sig = stats[stats["significant_at_0_05_fdr"]]["population"].tolist()
    print("Part 3 significant populations (FDR < 0.05):", ", ".join(sig) if sig else "None")
    print(
        "Part 4 melanoma male responder average B cells at time=0:",
        f"{part4['melanoma_male_responder_avg_b_cell_time0']:.2f}"
        if part4["melanoma_male_responder_avg_b_cell_time0"] is not None
        else "N/A",
    )


if __name__ == "__main__":
    main()
