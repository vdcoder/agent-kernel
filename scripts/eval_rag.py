"""RAG retrieval quality evaluation.

Measures recall@k: for each test query, checks whether the expected source
file(s) appear in the top-k retrieved chunks.

Usage:
    python scripts/eval_rag.py           # default top_k=3
    python scripts/eval_rag.py --top-k 5
    python scripts/eval_rag.py --verbose
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from app.rag import store
from src.config import Config
from src.llm import LLMClient


# ---------------------------------------------------------------------------
# Golden dataset
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    query: str
    expected_sources: list[str]   # source_file values that MUST appear in results
    description: str = ""


GOLDEN: list[TestCase] = [
    TestCase(
        query="How early should I come back to the ship from Grand Cayman?",
        expected_sources=["exp_grand_cayman_tender.md"],
        description="Tender port return timing",
    ),
    TestCase(
        query="I hate waiting in lines. When should I board the tender?",
        expected_sources=["exp_grand_cayman_tender.md"],
        description="Tender wait aversion → same source",
    ),
    TestCase(
        query="Best dinner time for a family with young kids",
        expected_sources=["exp_dining_young_children.md"],
        description="Family dining recommendation",
    ),
    TestCase(
        query="My children are 5 and 8, when should we eat dinner?",
        expected_sources=["exp_dining_young_children.md"],
        description="Children age phrasing variant",
    ),
    TestCase(
        query="How do I get a spa appointment on a sea day?",
        expected_sources=["exp_spa_sea_days.md"],
        description="Spa booking on busy days",
    ),
    TestCase(
        query="All the spa slots were booked. What should I do?",
        expected_sources=["exp_spa_sea_days.md"],
        description="Spa fully booked alternative",
    ),
    TestCase(
        query="I am worried about getting seasick on my first cruise",
        expected_sources=["exp_motion_sickness.md"],
        description="Seasickness prevention",
    ),
    TestCase(
        query="What can I do if I start feeling nauseous on the ship?",
        expected_sources=["exp_motion_sickness.md"],
        description="Nausea symptom phrasing variant",
    ),
    TestCase(
        query="Should I buy WiFi before or after I board?",
        expected_sources=["exp_embarkation_wifi.md"],
        description="WiFi purchase timing",
    ),
    TestCase(
        query="Is the premium internet package worth it?",
        expected_sources=["exp_embarkation_wifi.md"],
        description="WiFi package selection",
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_eval(top_k: int, verbose: bool) -> None:
    cfg = Config.load(_ROOT / "config.toml")
    llm = LLMClient(cfg)

    sources = store.list_sources()
    if not sources:
        print("[FAIL] Vector store is empty — run the ingest script first.")
        sys.exit(1)

    print(f"Vector store: {sum(s['chunk_count'] for s in sources)} chunks "
          f"across {len(sources)} source(s)")
    print(f"Eval config : top_k={top_k}, {len(GOLDEN)} test cases\n")
    print(f"{'#':<4} {'Result':<6} {'Description'}")
    print("─" * 60)

    hits = 0
    for i, tc in enumerate(GOLDEN, 1):
        try:
            q_emb = llm.embed(tc.query)
            results = store.search(q_emb, top_k=top_k)
        except Exception as exc:
            print(f"{i:<4} {'ERROR':<6} {tc.description}  ← {exc}")
            continue

        retrieved = {r["source_file"] for r in results}
        hit = all(src in retrieved for src in tc.expected_sources)
        if hit:
            hits += 1

        marker = "PASS" if hit else "FAIL"
        print(f"{i:<4} {marker:<6} {tc.description}")

        if verbose:
            print(f"       Query    : {tc.query}")
            print(f"       Expected : {tc.expected_sources}")
            print(f"       Got      : {sorted(retrieved)}")
            if not hit:
                missing = set(tc.expected_sources) - retrieved
                print(f"       Missing  : {sorted(missing)}")
            print()

    total = len(GOLDEN)
    recall = hits / total * 100
    print("─" * 60)
    print(f"Recall@{top_k}: {hits}/{total}  ({recall:.0f}%)")

    if recall < 80:
        print("\nSuggestions for low recall:")
        print("  • Re-ingest with --force to refresh stale embeddings")
        print("  • Increase top_k to cast a wider net")
        print("  • Enrich the experience files with more varied phrasing")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Number of chunks to retrieve per query (default: 3)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show query, expected, and retrieved sources for each case")
    args = parser.parse_args()
    run_eval(top_k=args.top_k, verbose=args.verbose)
