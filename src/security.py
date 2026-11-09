"""PII detection, prompt-injection heuristics, sanitisation."""

from __future__ import annotations

import re
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


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    pii_found: dict[str, list[str]] = field(default_factory=dict)
    redacted_text: str = ""
    injection_hits: list[str] = field(default_factory=list)


def detect_pii(text: str) -> dict[str, list[str]]:
    return {name: pat.findall(text) for name, pat in _PII_PATTERNS.items() if pat.search(text)}


def redact_pii(text: str, mask: str = "[REDACTED]") -> str:
    out = text
    for pat in _PII_PATTERNS.values():
        out = pat.sub(mask, out)
    return out


def detect_prompt_injection(text: str) -> list[str]:
    return [p.pattern for p in _INJECTION_PATTERNS if p.search(text)]


def sanitize_input(text: str, max_len: int = 4000) -> str:
    text = _CONTROL_RE.sub("", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text[:max_len]


def scan(text: str) -> ScanResult:
    sanitized = sanitize_input(text)
    pii = detect_pii(sanitized)
    redacted = redact_pii(sanitized) if pii else sanitized
    injections = detect_prompt_injection(sanitized)
    if pii:
        log.warning(f"PII detected: {list(pii.keys())}")
    if injections:
        log.warning(f"Injection heuristics fired: {len(injections)}")
    return ScanResult(
        clean=not injections and not pii,
        pii_found=pii,
        redacted_text=redacted,
        injection_hits=injections,
    )
