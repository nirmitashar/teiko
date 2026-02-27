#!/usr/bin/env python3
"""Load cell-count CSV data into a normalized SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "teiko.db"
POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]


def get_input_csv() -> Path:
    """Resolve the expected CSV path with a robust fallback."""
    preferred = ROOT / "cell-count.csv"
    if preferred.exists():
        return preferred

    fallback = ROOT / "cell-count (2).csv"
    if fallback.exists():
        return fallback

    raise FileNotFoundError(
        "Input CSV not found. Expected 'cell-count.csv' (or 'cell-count (2).csv') in repo root."
    )


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        DROP TABLE IF EXISTS cell_count;
        DROP TABLE IF EXISTS sample;
        DROP TABLE IF EXISTS subject;
        DROP TABLE IF EXISTS project;

        CREATE TABLE project (
            project_id TEXT PRIMARY KEY
        );

        CREATE TABLE subject (
            subject_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            condition TEXT NOT NULL,
            age INTEGER NOT NULL,
            sex TEXT NOT NULL CHECK (sex IN ('M', 'F')),
            treatment TEXT NOT NULL,
            response TEXT CHECK (response IN ('yes', 'no') OR response IS NULL),
            FOREIGN KEY (project_id) REFERENCES project(project_id)
        );

        CREATE TABLE sample (
            sample_id TEXT PRIMARY KEY,
            subject_id TEXT NOT NULL,
            sample_type TEXT NOT NULL,
            time_from_treatment_start INTEGER NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subject(subject_id)
        );

        CREATE TABLE cell_count (
            sample_id TEXT NOT NULL,
            population TEXT NOT NULL CHECK (population IN ('b_cell', 'cd8_t_cell', 'cd4_t_cell', 'nk_cell', 'monocyte')),
            count INTEGER NOT NULL CHECK (count >= 0),
            PRIMARY KEY (sample_id, population),
            FOREIGN KEY (sample_id) REFERENCES sample(sample_id)
        );

        CREATE INDEX idx_subject_lookup ON subject(condition, treatment, response, sex);
        CREATE INDEX idx_sample_lookup ON sample(sample_type, time_from_treatment_start);
        CREATE INDEX idx_cell_population ON cell_count(population);
        """
    )


def load_data(conn: sqlite3.Connection, csv_path: Path) -> None:
    df = pd.read_csv(csv_path)

    required = {
        "project",
        "subject",
        "condition",
        "age",
        "sex",
        "treatment",
        "response",
        "sample",
        "sample_type",
        "time_from_treatment_start",
        *POPULATIONS,
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

    projects = (
        df[["project"]]
        .drop_duplicates()
        .rename(columns={"project": "project_id"})
        .sort_values("project_id")
    )
    projects.to_sql("project", conn, if_exists="append", index=False)

    subjects = (
        df[
            [
                "subject",
                "project",
                "condition",
                "age",
                "sex",
                "treatment",
                "response",
            ]
        ]
        .drop_duplicates(subset=["subject"])
        .rename(
            columns={
                "subject": "subject_id",
                "project": "project_id",
            }
        )
    )
    subjects["response"] = subjects["response"].where(subjects["response"].notna(), None)
    subjects.to_sql("subject", conn, if_exists="append", index=False)

    samples = (
        df[["sample", "subject", "sample_type", "time_from_treatment_start"]]
        .drop_duplicates(subset=["sample"])
        .rename(columns={"sample": "sample_id", "subject": "subject_id"})
    )
    samples.to_sql("sample", conn, if_exists="append", index=False)

    long_counts = (
        df[["sample", *POPULATIONS]]
        .melt(id_vars=["sample"], value_vars=POPULATIONS, var_name="population", value_name="count")
        .rename(columns={"sample": "sample_id"})
    )
    long_counts.to_sql("cell_count", conn, if_exists="append", index=False)


def main() -> None:
    csv_path = get_input_csv()
    with sqlite3.connect(DB_PATH) as conn:
        create_schema(conn)
        load_data(conn, csv_path)
        conn.commit()
    print(f"Database created at: {DB_PATH}")


if __name__ == "__main__":
    main()
