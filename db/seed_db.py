"""
seed_db.py — Creates cruise.db from the three CSV files in this directory.

Usage (from repo root):
    python db/seed_db.py
"""

import csv
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent
DB_PATH = DB_DIR / "cruise.db"

DDL = """
CREATE TABLE IF NOT EXISTS guest_profiles (
    Guest_ID             TEXT PRIMARY KEY,
    First_Name           TEXT,
    Last_Name            TEXT,
    Cabin_Number         TEXT,
    Cabin_Category       TEXT,
    Deck                 INTEGER,
    Loyalty_Tier         TEXT,
    Loyalty_Points       INTEGER,
    Party_Size           INTEGER,
    Embark_Date          TEXT,
    Debark_Date          TEXT,
    Dietary_Restrictions TEXT,
    Special_Occasions    TEXT,
    Beverage_Package     TEXT,
    Past_Cruises         INTEGER
);

CREATE TABLE IF NOT EXISTS folio_transactions (
    Transaction_ID   TEXT PRIMARY KEY,
    Guest_ID         TEXT,
    Cabin_Number     TEXT,
    Transaction_Date TEXT,
    Transaction_Time TEXT,
    Category         TEXT,
    Description      TEXT,
    Venue            TEXT,
    Quantity         INTEGER,
    Unit_Price       REAL,
    Amount           REAL,
    Service_Charge   REAL,
    Total            REAL,
    Status           TEXT,
    Reference_ID     TEXT,
    Posted_By        TEXT,
    Notes            TEXT,
    FOREIGN KEY (Guest_ID) REFERENCES guest_profiles (Guest_ID)
);

CREATE TABLE IF NOT EXISTS dining_reservations (
    Reservation_ID        TEXT PRIMARY KEY,
    Guest_ID              TEXT,
    Guest_Name            TEXT,
    Cabin_Number          TEXT,
    Venue_ID              TEXT,
    Venue_Name            TEXT,
    Reservation_Date      TEXT,
    Reservation_Time      TEXT,
    Party_Size            INTEGER,
    Special_Requests      TEXT,
    Dietary_Notes         TEXT,
    Status                TEXT,
    Confirmation_Number   TEXT,
    Created_At            TEXT,
    Modified_At           TEXT,
    Cancelled_At          TEXT,
    Cancellation_Reason   TEXT,
    FOREIGN KEY (Guest_ID) REFERENCES guest_profiles (Guest_ID)
);
"""

# Maps CSV column name → Python type coercion for non-TEXT fields
COLUMN_TYPES: dict[str, dict[str, type]] = {
    "guest_profiles": {
        "Deck": int,
        "Loyalty_Points": int,
        "Party_Size": int,
        "Past_Cruises": int,
    },
    "folio_transactions": {
        "Quantity": int,
        "Unit_Price": float,
        "Amount": float,
        "Service_Charge": float,
        "Total": float,
    },
    "dining_reservations": {
        "Party_Size": int,
    },
}


def _coerce(value: str, col: str, types: dict[str, type]) -> object:
    """Return value cast to the right Python type; empty string → None."""
    if value == "":
        return None
    t = types.get(col)
    if t is not None:
        return t(value)
    return value


def load_csv(conn: sqlite3.Connection, table: str, csv_path: Path) -> int:
    types = COLUMN_TYPES.get(table, {})
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [
            {col: _coerce(val, col, types) for col, val in row.items()}
            for row in reader
        ]
    if not rows:
        print(f"  {table}: 0 rows (empty file)")
        return 0

    placeholders = ", ".join("?" for _ in rows[0])
    columns = ", ".join(rows[0].keys())
    sql = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
    conn.executemany(sql, [list(r.values()) for r in rows])
    return len(rows)


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed existing {DB_PATH.name}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(DDL)
    conn.commit()
    print(f"Created {DB_PATH}")

    tables = [
        ("guest_profiles",      DB_DIR / "guest_profiles.csv"),
        ("folio_transactions",  DB_DIR / "folio_transactions.csv"),
        ("dining_reservations", DB_DIR / "dining_reservations.csv"),
    ]

    for table, csv_path in tables:
        if not csv_path.exists():
            print(f"  WARNING: {csv_path.name} not found, skipping {table}")
            continue
        n = load_csv(conn, table, csv_path)
        conn.commit()
        print(f"  {table}: {n:,} rows loaded")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
