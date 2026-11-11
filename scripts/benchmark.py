"""Simple load benchmark (sequential)."""

from __future__ import annotations

import os
import statistics
import time

import httpx


def main() -> None:
    base = os.getenv("SECUREDOC_URL", "http://localhost:8000")
    key = os.getenv("SECUREDOC_API_KEY", "")
    if not key:
        print("Set SECUREDOC_API_KEY env var.")
        return

    n = int(os.getenv("BENCH_N", "20"))
    latencies: list[float] = []
    with httpx.Client(timeout=30) as c:
        for _ in range(n):
            start = time.perf_counter()
            r = c.post(
                f"{base}/api/v1/query",
                headers={"X-API-Key": key},
                json={"question": "How long is data retained?"},
            )
            elapsed = (time.perf_counter() - start) * 1000
            if r.status_code == 200:
                latencies.append(elapsed)
            else:
                print(f"status={r.status_code} body={r.text[:100]}")

    if latencies:
        print(f"n={len(latencies)} mean={statistics.mean(latencies):.1f}ms "
              f"p50={statistics.median(latencies):.1f}ms "
              f"p95={sorted(latencies)[int(len(latencies) * 0.95) - 1]:.1f}ms")


if __name__ == "__main__":
    main()
