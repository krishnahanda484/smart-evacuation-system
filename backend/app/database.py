"""
SQLite persistence layer.

Design rationale: SQLite is embedded, requires no external service, and
handles the write-throughput of this research prototype (hundreds of
simulation runs) without contention.  It stores only layout metadata and
the serialised grid JSON; the live simulation state lives in memory.

Tables created here:
  layouts — user-created or cached sample layouts
  simulation_runs — populated by Module 3 (dataset generator)
  ml_models — populated by Module 4 (ML training)
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent.parent / "data" / "evacuation.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # better concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS layouts (
                id             TEXT    PRIMARY KEY,
                name           TEXT    NOT NULL,
                description    TEXT    NOT NULL DEFAULT '',
                width          INTEGER NOT NULL,
                height         INTEGER NOT NULL,
                resolution_cm  REAL    NOT NULL DEFAULT 30.0,
                exit_count     INTEGER NOT NULL DEFAULT 0,
                wall_count     INTEGER NOT NULL DEFAULT 0,
                obstacle_count INTEGER NOT NULL DEFAULT 0,
                free_count     INTEGER NOT NULL DEFAULT 0,
                physical_width_m  REAL NOT NULL DEFAULT 0.0,
                physical_height_m REAL NOT NULL DEFAULT 0.0,
                passable_area_m2  REAL NOT NULL DEFAULT 0.0,
                is_sample      INTEGER NOT NULL DEFAULT 0,
                grid_json      TEXT    NOT NULL,
                created_at     REAL    NOT NULL DEFAULT (unixepoch('now'))
            );

            -- Populated by Module 3
            CREATE TABLE IF NOT EXISTS simulation_runs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                layout_id      TEXT    REFERENCES layouts(id),
                population     INTEGER NOT NULL,
                adherence_rate REAL    NOT NULL,
                strategy       TEXT    NOT NULL DEFAULT 'greedy',
                total_steps    INTEGER,
                evacuation_time_s REAL,
                completed      INTEGER NOT NULL DEFAULT 0,
                run_metadata   TEXT,
                created_at     REAL    NOT NULL DEFAULT (unixepoch('now'))
            );

            -- Populated by Module 4
            CREATE TABLE IF NOT EXISTS ml_models (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                target         TEXT    NOT NULL,
                model_type     TEXT    NOT NULL,
                rmse           REAL,
                mae            REAL,
                r2             REAL,
                artifact_path  TEXT,
                is_best        INTEGER NOT NULL DEFAULT 0,
                trained_at     REAL    NOT NULL DEFAULT (unixepoch('now'))
            );
        """)
    conn.close()


# ---------------------------------------------------------------------------
# Layout CRUD
# ---------------------------------------------------------------------------

def insert_layout(layout_id: str, meta: Dict[str, Any], grid_json: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO layouts
              (id, name, description, width, height, resolution_cm,
               exit_count, wall_count, obstacle_count, free_count,
               physical_width_m, physical_height_m, passable_area_m2,
               is_sample, grid_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            layout_id,
            meta["name"],
            meta.get("description", ""),
            meta["width"],
            meta["height"],
            meta["resolution_cm"],
            meta["exit_count"],
            meta["wall_count"],
            meta["obstacle_count"],
            meta["free_count"],
            meta["physical_width_m"],
            meta["physical_height_m"],
            meta["passable_area_m2"],
            1 if meta.get("is_sample") else 0,
            grid_json,
        ))
    conn.close()


def get_layout_row(layout_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM layouts WHERE id = ?", (layout_id,)
    ).fetchone()
    conn.close()
    return row


def list_layout_rows() -> List[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM layouts ORDER BY is_sample DESC, created_at ASC"
    ).fetchall()
    conn.close()
    return rows


def layout_exists(layout_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM layouts WHERE id = ?", (layout_id,)
    ).fetchone()
    conn.close()
    return row is not None
