"""Input sanitization and injection defense.

Defense in depth
----------------
NeMo Guardrails (``config/rails/``) catches semantic injection attempts at
the LLM layer. This module catches **structural** attacks earlier and more
cheaply:

1. **Unicode normalization** (NFKC) — collapses ``ﬁ`` → ``fi`` and other
   compatibility forms that could smuggle forbidden words past filters.
2. **Zero-width / bidi stripping** — removes invisible chars used to split
   keywords (e.g. ``ig\u200bnore``) so pattern detection sees the real text.
3. **Control-character stripping** — removes NUL and other C0 controls.
4. **Prompt-injection heuristics** — 10 regex patterns covering the most
   common jailbreak/injection phrases.
5. **Encoded-payload detection** — flags base64 blobs long enough to hide
   instructions.
6. **Length clamping** — caps input at a configurable maximum to prevent
   resource exhaustion and prompt-stuffing.

The single ``scan()`` function runs all checks and returns a ``ScanResult``
that callers act on. Any positive detection → block (never try to "clean"
around it — that's exploitable).
"""

from __future__ import annotations

import base64
import binascii
import html
import re
import unicodedata
from dataclasses import dataclass, field

from src.core.logger import get_logger
from src.security import pii

log = get_logger("security.sanitize")


# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #

DEFAULT_MAX_LEN = 4000
DEFAULT_MAX_ENCODED = 0  # any detected encoded payload → block


# --------------------------------------------------------------------------- #
# Regexes                                                                      #
# --------------------------------------------------------------------------- #

# Common injection phrases. Case-insensitive. Ordered roughly by frequency.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(?:\w+\s+){0,3}(?:previous|prior|above)\s+(?:instructions?|prompts?|rules?)",
        r"disregard\s+(?:\w+\s+){0,3}(?:previous|prior|above)\s+(?:instructions?|prompts?|rules?)",
        r"forget\s+(?:everything|all\s+(?:previous|prior))",
        r"you\s+are\s+now\s+(?:a|an|the)?\s*\w+",
        r"act\s+as\s+(?:a|an|the)?\s*(?:unrestricted|unfiltered|jailbroken)",
        r"jailbreak",
        r"developer\s+mode",
        r"(?:reveal|show|print|repeat)\s+(?:your\s+)?(?:system|initial|hidden)\s+(?:prompt|instructions?)",
        r"<\|?(?:system|im_start|im_end)\|?>",  # chat-template injection
        r"<\s*script\b",
    ]
]

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\u2061\u2062\u2063\ufeff]")
_BIDI_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069]")
# Base64-ish blob: 20+ chars from base64 alphabet, optional padding.
# 20 chars ≈ 15 decoded bytes — enough to hide a short instruction.
_B64_RE = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")


# --------------------------------------------------------------------------- #
# Result                                                                       #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ScanResult:
    """Output of :func:`scan`."""

    clean: bool
    original: str
    sanitized: str
    redacted_text: str
    pii_found: dict[pii.PIIType, list[str]] = field(default_factory=dict)
    injection_hits: list[str] = field(default_factory=list)
    encoded_payloads: int = 0
    hidden_chars: bool = False
    was_truncated: bool = False

    def block_reason(self) -> str | None:
        """Human-readable reason for blocking, or None if clean."""
        if self.injection_hits:
            return "prompt_injection"
        if self.encoded_payloads:
            return "encoded_payload"
        if self.pii_found:
            return "pii"
        return None


# --------------------------------------------------------------------------- #
# Individual checks                                                            #
# --------------------------------------------------------------------------- #

def normalize_unicode(text: str) -> str:
    """Apply NFKC normalization to defeat homoglyph/compatibility attacks."""
    return unicodedata.normalize("NFKC", text)


def strip_hidden(text: str) -> tuple[str, bool]:
    """Remove zero-width and bidi control characters.

    Returns
    -------
    tuple[str, bool]
        ``(cleaned_text, had_hidden_chars)``.
    """
    had_any = bool(_ZERO_WIDTH_RE.search(text) or _BIDI_RE.search(text))
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _BIDI_RE.sub("", text)
    return text, had_any


def detect_injection(text: str) -> list[str]:
    """Return list of matched injection patterns (as the regex strings)."""
    return [p.pattern for p in _INJECTION_PATTERNS if p.search(text)]


def detect_encoded(text: str) -> int:
    """Count valid base64 blobs long enough to hide instructions."""
    count = 0
    for m in _B64_RE.findall(text):
        try:
            # validate=True rejects non-base64 content; add padding if missing
            padded = m + "=" * (-len(m) % 4)
            base64.b64decode(padded, validate=True)
            count += 1
        except (binascii.Error, ValueError):
            continue
    return count


def clamp(text: str, max_len: int = DEFAULT_MAX_LEN) -> tuple[str, bool]:
    """Strip control chars, collapse whitespace, and truncate.

    Returns
    -------
    tuple[str, bool]
        ``(clamped_text, was_truncated)``.
    """
    text = _CONTROL_RE.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()
    truncated = len(text) > max_len
    return (text[:max_len], truncated)


def escape_html(text: str) -> str:
    """Escape HTML metacharacters (for rendering untrusted text in HTML)."""
    return html.escape(text, quote=True)


# --------------------------------------------------------------------------- #
# Combined scan                                                                #
# --------------------------------------------------------------------------- #

def scan(
    text: str,
    *,
    max_len: int = DEFAULT_MAX_LEN,
    redact: bool = True,
    block_on_pii: bool = False,
) -> ScanResult:
    """Run every security check on ``text`` and return a structured result.

    Parameters
    ----------
    text : str
        Raw user input.
    max_len : int
        Maximum length after clamping.
    redact : bool
        If True, ``redacted_text`` has PII masked; else it equals ``sanitized``.
    block_on_pii : bool
        If True, presence of PII marks the result as not-clean. Default False
        — PII is redacted but doesn't block queries (users may legitimately
        ask "is a@b.com a valid email?"). Enforcement lives in the caller.
    """
    if not isinstance(text, str):
        raise TypeError("scan() requires str input")

    original = text

    # 1. Normalize Unicode
    text = normalize_unicode(text)

    # 2. Strip hidden chars
    text, hidden = strip_hidden(text)

    # 3. Clamp
    text, truncated = clamp(text, max_len=max_len)
    sanitized = text

    # 4. Detect PII
    pii_found = pii.detect_pii(sanitized)
    redacted_text = pii.redact_pii(sanitized) if redact else sanitized

    # 5. Detect injections
    injections = detect_injection(sanitized)

    # 6. Detect encoded payloads
    encoded = detect_encoded(sanitized)

    # Decision
    clean = (
        not injections
        and encoded == 0
        and (not block_on_pii or not pii_found)
    )

    if not clean:
        log.warning(
            f"Security scan blocked: "
            f"injections={len(injections)} encoded={encoded} "
            f"pii={list(pii_found.keys())} truncated={truncated} "
            f"hidden={hidden}"
        )

    return ScanResult(
        clean=clean,
        original=original,
        sanitized=sanitized,
        redacted_text=redacted_text,
        pii_found=pii_found,
        injection_hits=injections,
        encoded_payloads=encoded,
        hidden_chars=hidden,
        was_truncated=truncated,
    )
