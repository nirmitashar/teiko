# Teiko Technical Assignment - Immune Cell Analysis

This repository implements all requested parts of the assignment:

- **Part 1:** SQLite relational schema + CSV loader (`load_data.py`)
- **Part 2:** Per-sample relative frequency summary table
- **Part 3:** Responder vs non-responder statistical analysis + boxplot
- **Part 4:** Baseline subset analysis queries and summary outputs
- **Dashboard:** Interactive Streamlit app (`app.py`)

## Dashboard link

When running locally/Codespaces:

- `http://localhost:8501`

## Quick start

### 1) Install dependencies

```bash
make setup
```

This creates a local virtual environment at `.venv/` and installs all required packages there.

### 2) Run the full pipeline

```bash
make pipeline
```

This command:

1. Creates `teiko.db`
2. Loads all rows from the input CSV
3. Generates all required analysis outputs in `outputs/`

### 3) Start the dashboard

```bash
make dashboard
```

---

## Input data

The project expects `cell-count.csv` in repository root.

For local robustness, the loader also accepts `cell-count (2).csv` if present (same schema).

Columns used:

- Metadata: `project`, `subject`, `condition`, `age`, `sex`, `treatment`, `response`, `sample`, `sample_type`, `time_from_treatment_start`
- Cell populations: `b_cell`, `cd8_t_cell`, `cd4_t_cell`, `nk_cell`, `monocyte`

---

## Database schema (Part 1)

The database (`teiko.db`) is normalized into four tables:

1. **`project`**
   - `project_id` (PK)

2. **`subject`**
   - `subject_id` (PK)
   - `project_id` (FK -> `project`)
   - `condition`, `age`, `sex`, `treatment`, `response`

3. **`sample`**
   - `sample_id` (PK)
   - `subject_id` (FK -> `subject`)
   - `sample_type`, `time_from_treatment_start`

4. **`cell_count`**
   - Composite PK: (`sample_id`, `population`)
   - `population` in (`b_cell`, `cd8_t_cell`, `cd4_t_cell`, `nk_cell`, `monocyte`)
   - `count` (non-negative integer)

### Why this schema?

- Keeps subject-level attributes separate from sample-level attributes.
- Stores cell counts in **long format** (`population`, `count`) instead of hardcoding one column per cell type in analytics tables.
- Easier to extend for new populations or treatments without redesigning analytics code.
- Supports scalable query patterns via indexes:
  - subject filters (`condition`, `treatment`, `response`, `sex`)
  - sample filters (`sample_type`, `time_from_treatment_start`)
  - population-level analytics (`population`)

### How this scales to larger studies

For hundreds of projects and thousands of samples:

- The same normalized model avoids duplication and update anomalies.
- Additional dimensions (site, assay batch, visit windows) can be modeled as related tables without denormalizing core entities.
- Materialized summary tables can be added for heavy dashboards while preserving raw normalized records as source-of-truth.
- For advanced analytics workloads, this schema ports cleanly to PostgreSQL/DuckDB with minimal SQL changes.

---

## Analysis outputs (Parts 2-4)

`make pipeline` writes:

- `outputs/part2_sample_population_frequencies.csv`
  - Columns: `sample`, `total_count`, `population`, `count`, `percentage`

- `outputs/part3_melanoma_miraclib_pbmc_percentages.csv`
  - Filter: melanoma + miraclib + PBMC + responders/non-responders

- `outputs/part3_responder_vs_nonresponder_boxplot.png`
  - Boxplot by population and response group

- `outputs/part3_population_significance.csv`
  - Mann-Whitney U test per population
  - FDR correction (Benjamini-Hochberg), significance at 0.05

- `outputs/part4_baseline_melanoma_miraclib_pbmc_samples.csv`
  - Baseline (`time_from_treatment_start = 0`) subset

- `outputs/part4_samples_per_project.csv`
- `outputs/part4_subjects_by_response.csv`
- `outputs/part4_subjects_by_sex.csv`
- `outputs/part4_summary.json`
  - Includes: melanoma male responder average B-cell count at baseline (2 decimals)

---

## Code structure

- `load_data.py`
  - Creates schema and loads CSV into SQLite

- `run_analysis.py`
  - Executes Parts 2-4 SQL/analysis workflow
  - Produces summary tables, stats results, and plot

- `app.py`
  - Interactive Streamlit dashboard:
    - Part 2 table explorer
    - Part 3 response comparison boxplot + significance table
    - Part 4 baseline subset summaries and required baseline B-cell metric

- `requirements.txt`
  - Python dependencies

- `Makefile`
  - Required targets: `setup`, `pipeline`, `dashboard`

---

## Notes on assignment wording vs file headers

The prompt references fields such as `sample_id`, `indication`, and `gender`.
In the provided CSV these correspond to:

- `sample_id` -> `sample`
- `indication` -> `condition`
- `gender` -> `sex`

The implementation follows the actual CSV headers and exposes the same concepts in outputs and dashboard.
