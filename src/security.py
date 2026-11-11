"""Advanced security: PII, injection, unicode/encoded attacks, HTML escaping."""

from __future__ import annotations

import base64
import binascii
import html
import re
import unicodedata
from dataclasses import dataclass, field

from src.logger import get_logger

log = get_logger("security")

_PII_PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CREDIT_CARD": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "AADHAAR": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "PAN": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "IPV4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "PHONE": re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s\-]?)?\d{10}(?!\d)"),
}

_INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior)\s+instructions",
        r"forget\s+(everything|all\s+previous)",
        r"you\s+are\s+now\s+\w",
        r"act\s+as\s+(an?\s+)?unrestricted",
        r"jailbreak",
        r"system\s*prompt\s*(reveal|show|print)",
        r"repeat\s+(your\s+)?(system|initial)\s+prompt",
        r"<\s*script",
    ]
]

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
_BIDI_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069]")
_B64_RE = re.compile(r"\b(?:[A-Za-z0-9+/]{20,}={0,2})\b")


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    pii_found: dict[str, list[str]] = field(default_factory=dict)
    redacted_text: str = ""
    injection_hits: list[str] = field(default_factory=list)
    encoded_payloads: int = 0
    unicode_suspicious: bool = False


def detect_pii(text: str) -> dict[str, list[str]]:
    return {name: pat.findall(text) for name, pat in _PII_PATTERNS.items() if pat.search(text)}


def redact_pii(text: str, mask: str = "[REDACTED]") -> str:
    out = text
    for pat in _PII_PATTERNS.values():
        out = pat.sub(mask, out)
    return out


def detect_prompt_injection(text: str) -> list[str]:
    return [p.pattern for p in _INJECTION_PATTERNS if p.search(text)]


def detect_encoded_payloads(text: str) -> int:
    """Detect possible base64/hex encoded payloads."""
    count = 0
    for m in _B64_RE.findall(text):
        try:
            base64.b64decode(m, validate=True)
            count += 1
        except (binascii.Error, ValueError):
            pass
    return count


def normalize_unicode(text: str) -> str:
    """NFKC normalization to defeat homoglyph attacks."""
    return unicodedata.normalize("NFKC", text)


def strip_hidden_chars(text: str) -> tuple[str, bool]:
    """Remove zero-width and bidi characters."""
    suspicious = bool(_ZERO_WIDTH_RE.search(text) or _BIDI_RE.search(text))
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _BIDI_RE.sub("", text)
    return text, suspicious


def sanitize_input(text: str, max_len: int = 4000) -> str:
    text = _CONTROL_RE.sub("", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text[:max_len]


def escape_html(text: str) -> str:
    return html.escape(text, quote=True)


def scan(text: str) -> ScanResult:
    """Full security scan."""
    text = normalize_unicode(text)
    text, hidden = strip_hidden_chars(text)
    sanitized = sanitize_input(text)

    pii = detect_pii(sanitized)
    redacted = redact_pii(sanitized) if pii else sanitized
    injections = detect_prompt_injection(sanitized)
    encoded = detect_encoded_payloads(sanitized)

    suspicious_unicode = hidden or bool(re.search(r"[\u0400-\u04ff\u0370-\u03ff]", sanitized))
    if suspicious_unicode:
        log.warning("Suspicious unicode detected (possible homoglyph attack)")

    clean = not injections and not pii and encoded == 0
    if not clean:
        log.warning(
            f"Security: pii={list(pii.keys())} inject={len(injections)} encoded={encoded}"
        )

    return ScanResult(
        clean=clean,
        pii_found=pii,
        redacted_text=redacted,
        injection_hits=injections,
        encoded_payloads=encoded,
        unicode_suspicious=suspicious_unicode,
    )
