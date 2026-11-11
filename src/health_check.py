"""Dependency health probes."""

from __future__ import annotations

from pathlib import Path

from src.config import get_settings


def check_vectorstore() -> dict[str, object]:
    s = get_settings()
    p = s.vectorstore_path / "index.faiss"
    return {
        "name": "vectorstore",
        "healthy": p.exists() and p.stat().st_size > 0,
        "detail": str(p),
    }


def check_docstore() -> dict[str, object]:
    s = get_settings()
    return {
        "name": "docstore",
        "healthy": s.docstore_path.exists() and any(s.docstore_path.iterdir()),
        "detail": str(s.docstore_path),
    }


def check_config() -> dict[str, object]:
    s = get_settings()
    ok = s.config_path.exists() and (s.config_path / "config.yml").exists()
    return {"name": "config", "healthy": ok, "detail": str(s.config_path)}


def check_audit() -> dict[str, object]:
    s = get_settings()
    return {
        "name": "audit",
        "healthy": s.audit_path.exists() or s.audit_path.mkdir(parents=True, exist_ok=True) or True,
        "detail": str(s.audit_path),
    }


def aggregate() -> dict[str, object]:
    checks = [check_vectorstore(), check_docstore(), check_config(), check_audit()]
    healthy = all(c["healthy"] for c in checks)
    return {"healthy": healthy, "checks": checks}
