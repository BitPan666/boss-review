#!/usr/bin/env python3
"""Compatibility entry point for running the packaged renderer from the repo."""
from pathlib import Path
from runpy import run_path

if __name__ == "__main__":
    run_path(str(Path(__file__).resolve().parents[1] / "skills/boss-review/scripts/render_report.py"),
             run_name="__main__")
