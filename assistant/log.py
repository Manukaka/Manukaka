"""App-wide logging: console + rotating file in data/logs/manu.log.

Import-time failures were previously invisible (`except Exception: pass`);
every swallowed exception now leaves a trace here.
"""
import logging
import logging.handlers

from . import config

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Idempotent root-logger setup. Safe to call from every entry point."""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            config.LOG_DIR / "manu.log", maxBytes=2_000_000, backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        root.warning("Could not open data/logs/manu.log; logging to console only.")


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
