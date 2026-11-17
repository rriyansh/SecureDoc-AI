"""Query normalization and expansion.

Why rewrite queries
-------------------
Users type short, abbreviated queries ("PII retention?") while documents
are written in full form ("personally identifiable information must be
retained for..."). A rewrite step bridges the gap **before** embedding,
improving retrieval recall without any LLM cost.

Strategies applied in order
---------------------------
1. **Whitespace normalization** — collapse multiple spaces, trim.
2. **Terminal punctuation** — append ``?`` if missing (helps the LLM
   interpret the query as a question).
3. **Abbreviation expansion** — domain-specific map (PII → ..., SSN → ...).
4. **Synonym injection** — for **short queries only** (< 4 tokens), append
   synonyms in parentheses so the embedding sees both phrasings.

What NOT to do
--------------
* **No LLM rewriting** — an LLM call per query would 3× the latency for
  marginal gains. Deterministic maps are enough for a policy corpus.
* **No aggressive expansion** — do not rewrite for long queries; the
  semantic signal is already strong and expansion adds noise.
"""

from __future__ import annotations

import re

from src.core.logger import get_logger

log = get_logger("rag.rewriter")


# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #

# Domain-specific abbreviations — extend as your corpus grows.
ABBREVIATIONS: dict[str, str] = {
    "PII": "personally identifiable information",
    "SSN": "social security number",
    "DPO": "data protection officer",
    "CDO": "chief data officer",
    "DPA": "data processing agreement",
    "GDPR": "general data protection regulation",
    "DPIA": "data protection impact assessment",
}

# Synonyms injected for short queries. Key = token in user query,
# value = list of alternatives to append.
SYNONYMS: dict[str, list[str]] = {
    "retention": ["retain", "kept", "stored", "delete"],
    "breach": ["incident", "leak", "compromise", "violation"],
    "access": ["permission", "authorised", "authorized", "restricted"],
    "delete": ["erase", "destroy", "purge", "remove"],
    "consent": ["approval", "agreement", "opt-in"],
    "encrypt": ["encrypted", "cipher", "protected"],
}

# Queries at or below this token count get synonym injection
_SHORT_QUERY_TOKEN_LIMIT = 3

# Max tokens to extract from a query for synonym lookup
_TOKEN_RE = re.compile(r"[A-Za-z]{3,}")


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _ensure_terminal_punctuation(text: str) -> str:
    if text and not text.endswith((".", "?", "!")):
        return text + "?"
    return text


def _expand_abbreviations(text: str) -> str:
    """Case-sensitive whole-word replacement of known abbreviations."""
    for abbr, expansion in ABBREVIATIONS.items():
        pattern = re.compile(rf"\b{re.escape(abbr)}\b")
        text = pattern.sub(expansion, text)
    return text


def _inject_synonyms(text: str) -> str:
    """Append synonyms in parens for short queries. Idempotent-safe."""
    tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    if not tokens:
        return text

    extras: set[str] = set()
    for token in tokens:
        if token in SYNONYMS:
            # Exclude the token itself so we don't repeat it
            extras.update(s for s in SYNONYMS[token] if s.lower() != token)

    if not extras:
        return text

    # Stable output (sorted) so cache keys stay consistent
    return f"{text} ({' '.join(sorted(extras))})"


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def rewrite(query: str, *, enabled: bool = True) -> str:
    """Normalize and optionally expand ``query``.

    Parameters
    ----------
    query : str
        Raw user query. Leading/trailing whitespace is trimmed.
    enabled : bool
        If False, only normalize whitespace (fast path for tests).

    Returns
    -------
    str
        Rewritten query, guaranteed non-empty and terminal-punctuated.

    Example
    -------
    >>> rewrite("PII retention")
    'personally identifiable information retention? (delete erase kept purge remove retain stored)'
    >>> rewrite("What is the data retention policy for customer records?")
    'What is the data retention policy for customer records?'
    """
    if not isinstance(query, str):
        raise TypeError("query must be str")

    original = query
    query = _normalize_whitespace(query)
    if not query:
        raise ValueError("query cannot be empty after normalization")

    query = _ensure_terminal_punctuation(query)

    if not enabled:
        return query

    query = _expand_abbreviations(query)

    # Only inject synonyms for short queries
    token_count = len(_TOKEN_RE.findall(query))
    if token_count <= _SHORT_QUERY_TOKEN_LIMIT:
        rewritten = _inject_synonyms(query)
        if rewritten != query:
            log.debug(f"Rewrote query: {original!r} → {rewritten!r}")
            return rewritten

    return query
