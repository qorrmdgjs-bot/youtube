"""Structured logging setup using structlog."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def setup_logging(log_dir: str = "logs", level: int = logging.INFO) -> None:
    """Configure structlog with JSON output to file and readable console output."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # File handler - JSON format
    file_handler = logging.FileHandler(log_path / "pipeline.log", encoding="utf-8")
    file_handler.setLevel(level)

    # Console handler - readable format
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)

    logging.basicConfig(
        format="%(message)s",
        handlers=[file_handler, console_handler],
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named logger instance."""
    return structlog.get_logger(name)
