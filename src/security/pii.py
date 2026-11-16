"""PII detection and redaction.

Scope
-----
Regex-based detection of structured PII in free text. This is **not** a
substitute for a dedicated PII ML model (e.g. Presidio), but it's fast,
deterministic, zero-dependency, and catches the high-value cases:

* Emails
* US SSNs
* Credit card numbers (Luhn-checkable — see note)
* Indian Aadhaar (12 digits, optional spaces)
* Indian PAN (5 letters + 4 digits + 1 letter)
* IPv4 addresses
* Phone numbers (10+ digits, optional country code)

Non-goals
---------
* Names, addresses, dates (too much false-positive risk with regex)
* Free-form numeric IDs (would redact order numbers, timestamps)

Luhn check note
---------------
Credit-card regex matches the *shape* but does not run Luhn (many non-card
numbers match 13–19 digits). Running Luhn would reject legitimate test
cards and increase false negatives. Callers who need strictness should
apply Luhn downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class PIIType(str, Enum):
    """Canonical PII type identifiers — used as label values in metrics."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    AADHAAR = "aadhaar"
    PAN = "pan"
    IPV4 = "ipv4"
    IBAN = "iban"


# --------------------------------------------------------------------------- #
# Patterns                                                                     #
# --------------------------------------------------------------------------- #

# Ordered dict — insertion order determines redaction order (some patterns
# are substrings of others, e.g. PHONE contains digits that might also match
# CREDIT_CARD; redacting by-name lets us detect each independently).
_PATTERNS: dict[PIIType, re.Pattern[str]] = {
    PIIType.EMAIL: re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    PIIType.SSN: re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # Aadhaar: 12 digits with optional single spaces
    PIIType.AADHAAR: re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    # PAN (India): ABCDE1234F
    PIIType.PAN: re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    # Credit card: 13–19 digits, optional spaces/dashes between groups
    PIIType.CREDIT_CARD: re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    # IPv4: four octets, validated at match time (post-filter below)
    PIIType.IPV4: re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    # IBAN: 2-letter country + 2 digits + 10–30 alphanumerics
    PIIType.IBAN: re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"),
    # Phone: 10+ digits, optional +country prefix. Must run AFTER credit_card
    # or it will eat credit card digits.
    PIIType.PHONE: re.compile(
        r"(?<!\d)(?:\+\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4}(?!\d)"
    ),
}


# --------------------------------------------------------------------------- #
# Result type                                                                  #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PIIMatch:
    """One occurrence of PII in the source text."""

    type: PIIType
    value: str
    start: int
    end: int


# --------------------------------------------------------------------------- #
# Detection                                                                    #
# --------------------------------------------------------------------------- #

def _validate_ipv4(value: str) -> bool:
    """Reject strings that look like IPv4 but have octets > 255."""
    parts = value.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def _validate_credit_card(value: str) -> bool:
    """Basic sanity: reject dates like '12-34-5678' that matched shape."""
    digits = re.sub(r"\D", "", value)
    return 13 <= len(digits) <= 19


def _find_matches(text: str) -> list[PIIMatch]:
    """Return every PII match with position (for precise redaction)."""
    matches: list[PIIMatch] = []
    consumed: list[tuple[int, int]] = []  # ranges we've already claimed

    def _overlaps(start: int, end: int) -> bool:
        return any(start < e and end > s for s, e in consumed)

    # Process patterns in order of specificity
    for pii_type, pattern in _PATTERNS.items():
        for m in pattern.finditer(text):
            start, end = m.start(), m.end()
            value = m.group(0)

            # Skip if already claimed by a more specific pattern
            if _overlaps(start, end):
                continue

            # Per-type post-filter
            if pii_type is PIIType.IPV4 and not _validate_ipv4(value):
                continue
            if pii_type is PIIType.CREDIT_CARD and not _validate_credit_card(value):
                continue

            matches.append(PIIMatch(type=pii_type, value=value, start=start, end=end))
            consumed.append((start, end))

    matches.sort(key=lambda m: m.start)
    return matches


def detect_pii(text: str) -> dict[PIIType, list[str]]:
    """Return a mapping of PII type → list of matched values.

    Values are returned verbatim — caller decides whether to log them
    (usually NOT — log the type + count, not the values).

    Example
    -------
    >>> detect_pii("contact a@b.com or +91-9876543210")
    {<PIIType.EMAIL: 'email'>: ['a@b.com'], <PIIType.PHONE: 'phone'>: ['+91-9876543210']}
    """
    if not text:
        return {}

    result: dict[PIIType, list[str]] = {}
    for match in _find_matches(text):
        result.setdefault(match.type, []).append(match.value)
    return result


# --------------------------------------------------------------------------- #
# Redaction                                                                    #
# --------------------------------------------------------------------------- #

def redact_pii(text: str, mask: str = "[REDACTED]") -> str:
    """Replace all PII occurrences with a mask token.

    The mask is applied **by position** (not by string replace) so overlapping
    matches don't corrupt the output. Positions come from the same regex pass
    as detection — consistent detection and redaction.

    Example
    -------
    >>> redact_pii("email me at a@b.com")
    'email me at [REDACTED]'
    """
    if not text:
        return text

    matches = _find_matches(text)
    if not matches:
        return text

    # Build the redacted text by slicing between matches
    out_parts: list[str] = []
    cursor = 0
    for m in matches:
        out_parts.append(text[cursor : m.start])
        out_parts.append(mask)
        cursor = m.end
    out_parts.append(text[cursor:])
    return "".join(out_parts)


def redact_with_types(text: str, mask: str = "[REDACTED]") -> tuple[str, dict[PIIType, int]]:
    """Redact and return per-type counts (for metrics).

    Returns
    -------
    tuple[str, dict[PIIType, int]]
        ``(redacted_text, {type: count})``.
    """
    if not text:
        return text, {}

    matches = _find_matches(text)
    if not matches:
        return text, {}

    counts: dict[PIIType, int] = {}
    out_parts: list[str] = []
    cursor = 0
    for m in matches:
        out_parts.append(text[cursor : m.start])
        out_parts.append(mask)
        cursor = m.end
        counts[m.type] = counts.get(m.type, 0) + 1
    out_parts.append(text[cursor:])
    return "".join(out_parts), counts
