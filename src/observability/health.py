"""Dependency health checks.

Powers ``GET /health/deps`` — a single-call view of every external dependency
the API relies on. Used by:

* Kubernetes readiness probes (only mark ready when healthy)
* Operators (``curl /health/deps | jq``)
* Uptime monitors (expect 200 + ``healthy: true``)

Design
------
* Every probe has a hard **timeout** — a hung dependency must not hang the
  health endpoint.
* Probes are **read-only** — no writes, no migrations.
* Probes are **independent** — one failing does not prevent the others
  from being reported (so operators can see *all* failures, not just the
  first).

Response shape
--------------
::

    {
      "healthy": false,
      "checks": [
        {"name": "postgres",   "healthy": true,  "latency_ms": 2.1},
        {"name": "cache",      "healthy": true,  "backend": "memory"},
        {"name": "vectorstore","healthy": false, "error": "index missing"},
        {"name": "config",     "healthy": true}
      ]
    }
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from src.core.config import get_settings
from src.core.logger import get_logger

log = get_logger("observability.health")

# Per-probe timeout — total /health/deps budget is 4 × this in worst case
_PROBE_TIMEOUT_SECONDS = 2.0


# --------------------------------------------------------------------------- #
# Individual probes                                                            #
# --------------------------------------------------------------------------- #

async def check_db() -> dict[str, Any]:
    """Probe the PostgreSQL connection."""
    start = time.monotonic()
    try:
        from src.db.session import healthcheck as db_health

        result = await asyncio.wait_for(db_health(), timeout=_PROBE_TIMEOUT_SECONDS)
        elapsed_ms = (time.monotonic() - start) * 1000
        return {**result, "latency_ms": round(elapsed_ms, 1)}
    except asyncio.TimeoutError:
        return {"name": "postgres", "healthy": False, "error": "timeout"}
    except Exception as exc:
        log.warning(f"DB healthcheck exception: {exc}")
        return {
            "name": "postgres",
            "healthy": False,
            "error": type(exc).__name__,
        }


async def check_cache() -> dict[str, Any]:
    """Probe the cache backend (memory or redis)."""
    start = time.monotonic()
    try:
        from src.cache.factory import healthcheck as cache_health

        result = await asyncio.wait_for(cache_health(), timeout=_PROBE_TIMEOUT_SECONDS)
        elapsed_ms = (time.monotonic() - start) * 1000
        return {**result, "latency_ms": round(elapsed_ms, 1)}
    except asyncio.TimeoutError:
        return {"name": "cache", "healthy": False, "error": "timeout"}
    except Exception as exc:
        log.warning(f"Cache healthcheck exception: {exc}")
        return {"name": "cache", "healthy": False, "error": type(exc).__name__}


def check_vectorstore() -> dict[str, Any]:
    """Probe the FAISS index — present, non-empty, has a manifest."""
    s = get_settings()
    index_path: Path = s.vectorstore_path / "index.faiss"
    manifest_path: Path = s.vectorstore_path / "manifest.json"

    if not index_path.exists():
        return {
            "name": "vectorstore",
            "healthy": False,
            "error": "index.faiss missing — run `make ingest`",
            "path": str(index_path),
        }
    try:
        size = index_path.stat().st_size
    except OSError as exc:
        return {
            "name": "vectorstore",
            "healthy": False,
            "error": f"stat failed: {exc}",
        }

    if size == 0:
        return {
            "name": "vectorstore",
            "healthy": False,
            "error": "index.faiss is empty — re-ingest",
        }

    return {
        "name": "vectorstore",
        "healthy": True,
        "size_bytes": size,
        "has_manifest": manifest_path.exists(),
    }


def check_config() -> dict[str, Any]:
    """Probe the NeMo Guardrails configuration directory."""
    s = get_settings()
    config_file = s.config_path / "config.yml"
    if not config_file.exists():
        return {
            "name": "config",
            "healthy": False,
            "error": "config.yml missing",
            "path": str(config_file),
        }
    rails_dir = s.config_path / "rails"
    if not rails_dir.exists() or not any(rails_dir.glob("*.co")):
        return {
            "name": "config",
            "healthy": False,
            "error": "no .co rail files found",
        }
    return {
        "name": "config",
        "healthy": True,
        "path": str(s.config_path),
    }


# --------------------------------------------------------------------------- #
# Aggregate                                                                    #
# --------------------------------------------------------------------------- #

async def aggregate() -> dict[str, Any]:
    """Run all probes (in parallel) and return a combined report.

    Probes run concurrently — total latency is max(probe), not sum(probe).
    """
    start = time.monotonic()

    db_result, cache_result = await asyncio.gather(
        check_db(), check_cache(), return_exceptions=False
    )
    # Sync probes — cheap, no await
    vector_result = check_vectorstore()
    config_result = check_config()

    checks = [db_result, cache_result, vector_result, config_result]
    healthy = all(c.get("healthy", False) for c in checks)
    elapsed_ms = (time.monotonic() - start) * 1000

    if not healthy:
        failed = [c["name"] for c in checks if not c.get("healthy")]
        log.warning(f"/health/deps: unhealthy dependencies: {failed}")

    return {
        "healthy": healthy,
        "checks": checks,
        "total_latency_ms": round(elapsed_ms, 1),
    }
