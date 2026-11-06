"""Interactive CLI for SecureDoc AI."""

import argparse
import sys

from src.logger import get_logger
from src.rag_pipeline import build_rag_chain

log = get_logger("cli")

BANNER = r"""
   _____                     _        _____   _____
  / ____|                   | |      |  __ \ |_   _|
 | (___   ___  ___ _   _  __| | ___  | |  | |  | |
  \___ \ / _ \/ __| | | |/ _` |/ _ \ | |  | |  | |
  ____) |  __/ (__| |_| | (_| |  __/ | |__| | _| |_
 |_____/ \___|\___|\__,_|\__,_|\___| |_____/ |_____|

  SecureDoc AI — Enterprise RAG with Guardrails
"""


def interactive() -> None:
    print(BANNER)
    print("Type your question, or 'exit' to quit.\n")
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
            answer = chain.invoke(q)
            print(f"\n💡 Answer:\n{answer}\n")
        except Exception as exc:
            log.exception("Query failed")
            print(f"\n⚠️  Error: {exc}\n")


def single_question(question: str) -> None:
    chain = build_rag_chain()
    print(chain.invoke(question))


def main() -> None:
    parser = argparse.ArgumentParser(description="SecureDoc AI CLI")
    parser.add_argument("-q", "--question", help="Answer a single question and exit")
    args = parser.parse_args()

    if args.question:
        single_question(args.question)
    else:
        interactive()


if __name__ == "__main__":
    main()
