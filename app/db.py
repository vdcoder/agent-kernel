"""Thin SQLite helpers for the cruise demo database (db/cruise.db)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Resolved at import time so it works regardless of cwd.
_DB_PATH = Path(__file__).parent.parent / "db" / "cruise.db"


def _connect(db_path: Path = _DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_guest(guest_id: str, db_path: Path = _DB_PATH) -> dict | None:
    """Return the guest_profiles row for *guest_id*, or None if not found."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM guest_profiles WHERE Guest_ID = ?", (guest_id,)
        ).fetchone()
    return dict(row) if row else None
