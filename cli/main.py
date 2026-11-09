"""Interactive and single-shot CLI."""

import argparse
import sys

from src.logger import get_logger
from src.rag_pipeline import build_rag_chain, safe_query

log = get_logger("cli")

BANNER = r"""
  ____                     _       _____   _____
 / ___|  ___  ___ _   _  __| | ___ |  __ \ |_   _|
 \___ \ / _ \/ __| | | |/ _` |/ _ \| |  | |  | |
  ___) |  __/ (__| |_| | (_| |  __/| |__| |  | |
 |____/ \___|\___|\__,_|\__,_|\___||_____/  |_____|
  SecureDoc AI v2 — Secure Enterprise RAG
"""


def _interactive() -> None:
    print(BANNER)
    print("Type your question, or 'exit'.\n")
    chain = build_rag_chain()
    while True:
        try:
            q = input("❓ Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            sys.exit(0)
        if q.lower() in {"exit", "quit", "q"}:
            print("Goodbye.")
            break
        if not q:
            continue
        try:
            print(f"\n💡 {safe_query(chain, q)}\n")
        except Exception as exc:
            log.exception("Query failed")
            print(f"\n⚠️  {exc}\n")


def _single(question: str) -> None:
    print(safe_query(build_rag_chain(), question))


def main() -> None:
    parser = argparse.ArgumentParser(description="SecureDoc AI CLI")
    parser.add_argument("-q", "--question")
    args = parser.parse_args()
    (_single if args.question else _interactive)(*( [args.question] if args.question else [] ))


if __name__ == "__main__":
    main()
