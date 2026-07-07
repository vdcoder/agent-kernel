"""Ingest a text/markdown file (or directory of files) into the RAG vector store.

Usage:
    # Single file
    python app/rag/ingest.py db/rag/my_document.md

    # All .md/.txt files in a directory
    python app/rag/ingest.py db/rag/

    # Re-ingest (clears existing chunks first)
    python app/rag/ingest.py db/rag/my_document.md --force

    # Custom config
    python app/rag/ingest.py db/rag/my_document.md --config config.toml
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Make src/ importable when running as a script from the project root.
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from app.rag import store
from src.config import Config
from src.llm import LLMClient

CHUNK_SIZE    = 500   # target characters per chunk
CHUNK_OVERLAP = 80    # overlap between consecutive chunks
EMBED_BATCH   = 20    # embeddings per API call


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _last_heading(text: str) -> str | None:
    """Return the last ## (or #) heading found in *text*, or None."""
    matches = list(re.finditer(r"^#{1,3}\s+(.+)$", text, re.MULTILINE))
    return matches[-1].group(1).strip() if matches else None


def chunk_text(text: str) -> list[tuple[int, str, str | None]]:
    """Split *text* into overlapping chunks.

    Returns list of (chunk_index, chunk_text, heading_above_chunk).
    Breaks preferentially at paragraph boundaries (double newlines).
    """
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[tuple[int, str, str | None]] = []
    buffer      = ""
    buffer_pos  = 0   # character offset of buffer start in original text
    text_so_far = ""
    idx         = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph would overflow, flush the buffer first.
        if buffer and len(buffer) + len(para) + 2 > CHUNK_SIZE:
            heading = _last_heading(text_so_far[:buffer_pos])
            chunks.append((idx, buffer.strip(), heading))
            idx += 1
            # Keep overlap: take the tail of the current buffer.
            overlap_start = max(0, len(buffer) - CHUNK_OVERLAP)
            buffer = buffer[overlap_start:].strip()

        buffer      += ("\n\n" if buffer else "") + para
        buffer_pos   = len(text_so_far)
        text_so_far += para + "\n\n"

    if buffer.strip():
        heading = _last_heading(text_so_far[:buffer_pos])
        chunks.append((idx, buffer.strip(), heading))

    return chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_batch(texts: list[str], llm: LLMClient) -> list[list[float]]:
    return [llm.embed(t) for t in texts]   # one call each; batch via list if API supports it


def embed_batched(texts: list[str], llm: LLMClient) -> list[list[float]]:
    """Embed *texts* in batches of EMBED_BATCH, printing progress."""
    results: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start : start + EMBED_BATCH]
        results.extend(embed_batch(batch, llm))
        print(f"    embedded {min(start + EMBED_BATCH, len(texts))}/{len(texts)}")
    return results


# ---------------------------------------------------------------------------
# Ingest one file
# ---------------------------------------------------------------------------

def ingest_file(path: Path, llm: LLMClient, force: bool = False) -> None:
    source_name = path.name

    if force:
        removed = store.clear_source(source_name)
        if removed:
            print(f"  Cleared {removed} existing chunks for {source_name}")

    text   = path.read_text(encoding="utf-8")
    chunks = chunk_text(text)
    print(f"  {source_name}: {len(chunks)} chunks")

    if not chunks:
        print("  (nothing to embed)")
        return

    texts      = [c[1] for c in chunks]
    embeddings = embed_batched(texts, llm)

    records = [
        {
            "source_file":  source_name,
            "chunk_index":  idx,
            "heading":      heading,
            "text":         chunk_text_,
            "embedding":    emb,
        }
        for (idx, chunk_text_, heading), emb in zip(chunks, embeddings)
    ]

    n = store.add_chunks(records)
    print(f"  Stored {n} chunks for {source_name}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into the RAG vector store")
    parser.add_argument("path", help="File (.md/.txt) or directory to ingest")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    parser.add_argument("--force", action="store_true",
                        help="Re-ingest: clear existing chunks before adding")
    args = parser.parse_args()

    config = Config.load(args.config)
    llm    = LLMClient(config)

    target = Path(args.path)
    if target.is_dir():
        files = sorted(target.glob("*.md")) + sorted(target.glob("*.txt"))
        files = sorted(set(files))
        if not files:
            print(f"No .md or .txt files found in {target}")
            return
        print(f"Ingesting {len(files)} file(s) from {target}")
        for f in files:
            ingest_file(f, llm, force=args.force)
    elif target.is_file():
        ingest_file(target, llm, force=args.force)
    else:
        print(f"ERROR: {target} does not exist")
        sys.exit(1)

    print("\nDone. Sources in store:")
    for s in store.list_sources():
        print(f"  {s['source_file']}: {s['chunk_count']} chunks")


if __name__ == "__main__":
    main()
