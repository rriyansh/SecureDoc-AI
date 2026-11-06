"""Application logging setup."""

import logging
import sys


def get_logger(name: str = "secure-doc-ai") -> logging.Logger:
    """Return a configured logger instance."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = os_log_level()
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def os_log_level() -> int:
    import os

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)
