"""RAGAS evaluation of the RAG pipeline.

Metrics
-------
* **faithfulness** — every claim in the answer is supported by the context
* **answer_relevancy** — the answer directly addresses the question
* **context_precision** — retrieved chunks that are actually relevant are
  ranked above irrelevant ones
* **context_recall** — all relevant chunks were retrieved

Setup
-----
1. Curated test set of (question, ground_truth) pairs.
2. For each: run retrieve + safe_query → collect answer + contexts.
3. Feed to RAGAS with LangChain-wrapped LLM + embeddings (required for
   RAGAS 0.2 — bare OpenAI clients no longer work).

Usage
-----
::

    python -m src.rag.evaluate
    # writes evaluation_results.json in cwd

Not part of runtime
-------------------
Runs offline only — do not import this from the API. It makes 10-20 LLM
calls per evaluation, which is expensive if triggered per-request.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

from src.core.config import get_settings
from src.core.logger import get_logger
from src.rag.pipeline import build_rag_chain, safe_query
from src.rag.retriever import retrieve_and_rerank

log = get_logger("rag.evaluate")


# --------------------------------------------------------------------------- #
# Test set                                                                     #
# --------------------------------------------------------------------------- #

# Hand-curated: questions answerable from ``documents/company_policy.txt``.
# Extend as the corpus grows. Ground-truths should be **verbatim or near-
# verbatim** from the source — not paraphrases (RAGAS score is sensitive to
# drift).
EVAL_SET: dict[str, list[str]] = {
    "question": [
        "How long must customer data be retained?",
        "Who can access customer data?",
        "What should happen if a data breach is suspected?",
        "What encryption is required for customer data?",
        "How often must access be audited?",
    ],
    "ground_truth": [
        "Customer data must be retained for a minimum of 3 years and a maximum of 7 years.",
        "Access to customer data is restricted to authorized personnel only.",
        "Any suspected data breach must be reported to the security team within 24 hours.",
        "Customer data must be encrypted at rest and in transit.",
        "All access must be logged and audited quarterly.",
    ],
}


# --------------------------------------------------------------------------- #
# Runner                                                                       #
# --------------------------------------------------------------------------- #

def _build_evaluator_wrappers() -> tuple[LangchainLLMWrapper, LangchainEmbeddingsWrapper]:
    """Construct the LangChain-wrapped LLM/embedding used by RAGAS."""
    s = get_settings()
    api_key = s.openai_api_key.get_secret_value()

    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(model=s.openai_model, api_key=api_key, temperature=0)
    )
    evaluator_emb = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model=s.openai_embedding_model, api_key=api_key)
    )
    return evaluator_llm, evaluator_emb


def run_evaluation(output_path: str | Path | None = None) -> dict[str, float]:
    """Run RAGAS over the curated test set and persist the scores.

    Parameters
    ----------
    output_path : str | Path | None
        Where to write ``evaluation_results.json``. Defaults to ``cwd``.

    Returns
    -------
    dict[str, float]
        Per-metric scores in ``[0.0, 1.0]``.
    """
    log.info("Starting RAGAS evaluation")
    s = get_settings()
    chain = build_rag_chain()

    answers: list[str] = []
    contexts: list[list[str]] = []

    for i, question in enumerate(EVAL_SET["question"], start=1):
        log.info(f"[{i}/{len(EVAL_SET['question'])}] {question}")
        docs = retrieve_and_rerank(question)
        contexts.append([getattr(d, "page_content", str(d)) for d in docs])
        answers.append(safe_query(chain, question))

    dataset = Dataset.from_dict({
        "question": EVAL_SET["question"],
        "ground_truth": EVAL_SET["ground_truth"],
        "answer": answers,
        "contexts": contexts,
    })

    evaluator_llm, evaluator_emb = _build_evaluator_wrappers()

    log.info("Running RAGAS metrics...")
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=evaluator_llm,
        embeddings=evaluator_emb,
    )

    scores: dict[str, float] = {}
    for key, value in result.items():
        if isinstance(value, (int, float)):
            scores[key] = round(float(value), 4)

    log.success(f"RAGAS scores: {scores}")

    out = Path(output_path or "evaluation_results.json").resolve()
    out.write_text(json.dumps(scores, indent=2), encoding="utf-8")
    log.info(f"Saved evaluation results to {out}")
    return scores


# --------------------------------------------------------------------------- #
# CLI entry                                                                    #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    run_evaluation()
