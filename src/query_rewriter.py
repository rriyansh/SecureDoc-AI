"""Query normalization and expansion."""

from __future__ import annotations

import re

from src.logger import get_logger

log = get_logger("query_rewriter")

SYNONYMS = {
    "retention": ["retain", "kept", "stored"],
    "breach": ["incident", "leak", "compromise"],
    "access": ["authorised", "authorized", "permission"],
    "delete": ["erase", "destroy", "purge"],
}

_ABBREV = {
    r"\bPII\b": "personally identifiable information",
    r"\bSSN\b": "social security number",
    r"\bDPO\b": "data protection officer",
    r"\bCDO\b": "chief data officer",
}


def normalise(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text.endswith(("?", ".", "!")):
        text += "?"
    return text


def expand_abbreviations(text: str) -> str:
    for pat, exp in _ABBREV.items():
        text = re.sub(pat, exp, text, flags=re.IGNORECASE)
    return text


def rewrite(query: str, enabled: bool = True) -> str:
    q = normalise(query)
    if not enabled:
        return q
    q = expand_abbreviations(q)
    if len(q.split()) <= 3:
        tokens = re.findall(r"[a-zA-Z]+", q.lower())
        extra: list[str] = []
        for t in tokens:
            if t in SYNONYMS:
                extra.extend(s for s in SYNONYMS[t] if s != t)
        if extra:
            q = f"{q} ({' '.join(sorted(set(extra)))})"
            log.debug(f"Rewritten: {q}")
    return q
