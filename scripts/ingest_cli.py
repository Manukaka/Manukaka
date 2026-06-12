"""Run the full ingestion pipeline from a terminal (no GUI needed).

Usage:  python scripts/ingest_cli.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant.ingestion import runner  # noqa: E402

if __name__ == "__main__":
    runner.run_ingest(print)
