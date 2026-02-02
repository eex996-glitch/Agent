#!/usr/bin/env python3
"""
Structured Logging Configuration
Uses loguru for consistent, rotated logging throughout the application
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from loguru import logger
from typing import Optional


def setup_logging(
    log_dir: str = None,
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    rotation: str = "10 MB",
    retention: str = "7 days",
    app_name: str = "FuturesTradingAgent"
) -> None:
    """
    Configure loguru for the application

    Args:
        log_dir: Directory for log files (default: ./logs)
        console_level: Minimum level for console output
        file_level: Minimum level for file output
        rotation: When to rotate log files
        retention: How long to keep old logs
        app_name: Application name for log identification
    """
    # Remove default handler
    logger.remove()

    # Determine log directory
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "logs" / "app_logs"
    else:
        log_dir = Path(log_dir)

    log_dir.mkdir(parents=True, exist_ok=True)

    # Console handler with colored output
    console_format = (
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stderr,
        format=console_format,
        level=console_level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )

    # File handler for all logs
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )

    logger.add(
        log_dir / f"{app_name.lower()}_{{time:YYYY-MM-DD}}.log",
        format=file_format,
        level=file_level,
        rotation=rotation,
        retention=retention,
        compression="gz",
        backtrace=True,
        diagnose=True
    )

    # Separate error log
    logger.add(
        log_dir / f"{app_name.lower()}_errors_{{time:YYYY-MM-DD}}.log",
        format=file_format,
        level="ERROR",
        rotation=rotation,
        retention=retention,
        compression="gz",
        backtrace=True,
        diagnose=True
    )

    # Trade-specific log
    logger.add(
        log_dir / f"trades_{{time:YYYY-MM-DD}}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
        level="INFO",
        filter=lambda record: record["extra"].get("trade_log", False),
        rotation="1 day",
        retention="30 days"
    )

    logger.info(f"{app_name} logging initialized")


def get_trade_logger():
    """Get a logger specifically for trade events"""
    return logger.bind(trade_log=True)


class LogContext:
    """Context manager for logging with additional context"""

    def __init__(self, **context):
        self.context = context
        self._token = None

    def __enter__(self):
        self._token = logger.contextualize(**self.context)
        return logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            self._token.__exit__(exc_type, exc_val, exc_tb)


def log_execution_time(func):
    """Decorator to log function execution time"""
    from functools import wraps
    import time

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.debug(f"{func.__name__} completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error(f"{func.__name__} failed after {elapsed:.3f}s: {e}")
            raise

    return wrapper


def log_trade(
    action: str,
    symbol: str,
    direction: str,
    quantity: int,
    price: float,
    **extra
) -> None:
    """Log a trade event with structured data"""
    trade_logger = get_trade_logger()

    trade_info = {
        "action": action,
        "symbol": symbol,
        "direction": direction,
        "quantity": quantity,
        "price": price,
        **extra
    }

    msg = f"TRADE | {action} | {direction.upper()} {quantity} {symbol} @ ${price:.2f}"

    if extra:
        extra_str = " | ".join(f"{k}={v}" for k, v in extra.items())
        msg += f" | {extra_str}"

    trade_logger.info(msg)


# Initialize with defaults when imported
if not logger._core.handlers:
    setup_logging()
