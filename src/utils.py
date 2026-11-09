"""Shared utility helpers."""

import hashlib
import re
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from src.logger import get_logger

logger = get_logger(__name__)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def safe_get(data: Any, path: str, default: Any = None) -> Any:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    unique = uuid.uuid4().hex[:12]
    return f"{prefix}{unique}" if prefix else unique


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem usage."""
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)
    filename = filename.strip(". ")
    return filename[:255]


def parse_size(size_str: str) -> int:
    """Parse human-readable size string to bytes."""
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    size_str = size_str.strip().upper()
    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            try:
                return int(float(size_str[:-len(unit)]) * multiplier)
            except ValueError:
                pass
    try:
        return int(size_str)
    except ValueError:
        return 0


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}µs"
    elif seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


def mask_secrets(text: str, patterns: Optional[List[str]] = None) -> str:
    """Mask potential secrets in text."""
    if patterns is None:
        patterns = [
            r'(?i)(api[_-]?key|secret|token|password)["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
            r'(?i)(authorization|bearer)\s+([^\s]+)',
        ]

    result = text
    for pattern in patterns:
        result = re.sub(pattern, r'\1="[REDACTED]"', result)
    return result


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result