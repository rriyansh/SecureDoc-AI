"""Structured logging configuration using loguru."""

import sys
from pathlib import Path

from loguru import logger

from src.config import get_settings

_configured = False


def setup_logger() -> None:
    """Configure loguru for file + console output (idempotent)."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
    logger.add(
        log_dir / "securedoc_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="14 days",
        level=settings.log_level,
        enqueue=True,
        backtrace=True,
        diagnose=settings.environment != "production",
    )
    _configured = True


def get_logger(name: str = "securedoc"):
    """Return a bound logger."""
    setup_logger()
    return logger.bind(module=name)
