"""sqlite-vec backed vector store for the RAG pipeline.

Two-table design:
  chunks     — regular table: text, metadata, heading
  vec_chunks — vec0 virtual table: 768-dim float embeddings (rowid = chunks.id)

The vec0 virtual table gives proper ANN search via the sqlite-vec extension.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

DB_PATH = Path(__file__).parent.parent.parent / "db" / "rag" / "vectors.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file  TEXT NOT NULL,
    chunk_index  INTEGER NOT NULL,
    heading      TEXT,
    text         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_file);
"""

_VEC_TABLE = "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[3072]);"


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.executescript(_SCHEMA)
    conn.execute(_VEC_TABLE)
    conn.commit()
    return conn


def add_chunks(chunks: list[dict], db_path: Path = DB_PATH) -> int:
    """Insert chunks into both tables.

    Each dict must have: source_file, chunk_index, heading (str|None), text, embedding (list[float]).
    Returns the number of chunks stored.
    """
    if not chunks:
        return 0
    with _connect(db_path) as conn:
        for chunk in chunks:
            cur = conn.execute(
                "INSERT INTO chunks(source_file, chunk_index, heading, text) VALUES (?,?,?,?)",
                (chunk["source_file"], chunk["chunk_index"], chunk.get("heading"), chunk["text"]),
            )
            row_id = cur.lastrowid
            conn.execute(
                "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                (row_id, sqlite_vec.serialize_float32(chunk["embedding"])),
            )
        conn.commit()
    return len(chunks)


def search(
    query_embedding: list[float],
    top_k: int = 3,
    db_path: Path = DB_PATH,
) -> list[dict]:
    """Return the top_k most similar chunks via ANN search on vec_chunks.

    Each result dict has: source_file, heading, text, distance.
    """
    with _connect(db_path) as conn:
        blob = sqlite_vec.serialize_float32(query_embedding)
        rows = conn.execute(
            """
            SELECT c.source_file, c.heading, c.text, v.distance
            FROM vec_chunks v
            JOIN chunks c ON c.id = v.rowid
            WHERE v.embedding MATCH ?
              AND k = ?
            ORDER BY v.distance
            """,
            (blob, top_k),
        ).fetchall()
    return [
        {"source_file": r[0], "heading": r[1], "text": r[2], "distance": r[3]}
        for r in rows
    ]


def clear_source(source_file: str, db_path: Path = DB_PATH) -> int:
    """Delete all chunks for *source_file* from both tables. Returns deleted count."""
    with _connect(db_path) as conn:
        ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM chunks WHERE source_file = ?", (source_file,)
            ).fetchall()
        ]
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM vec_chunks WHERE rowid IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM chunks WHERE id IN ({placeholders})", ids)
            conn.commit()
    return len(ids)


def list_sources(db_path: Path = DB_PATH) -> list[dict]:
    """Return a summary of all ingested sources."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT source_file, COUNT(*) FROM chunks GROUP BY source_file ORDER BY source_file"
        ).fetchall()
    return [{"source_file": r[0], "chunk_count": r[1]} for r in rows]
