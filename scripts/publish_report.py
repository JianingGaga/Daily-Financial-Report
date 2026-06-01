#!/usr/bin/env python3
"""Generate the daily report, push it to GitHub Pages, and print the URL."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES_URL = "https://jianinggaga.github.io/Daily-Financial-Report/"


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=dt.datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--time", default=dt.datetime.now().strftime("%H:%M"))
    args = parser.parse_args()

    generator = ROOT / "scripts" / "generate_report.py"
    generated = run([sys.executable, str(generator), "--date", args.date, "--time", args.time])
    if generated.stdout:
        print(generated.stdout.strip())
    if generated.stderr:
        print(generated.stderr.strip(), file=sys.stderr)

    status = run(["git", "status", "--short"])
    if not status.stdout.strip():
        print(f"no changes to publish; url={PAGES_URL}")
        return 0

    run(["git", "add", "index.html", f"reports/{args.date}.html", "scripts/generate_report.py", "scripts/publish_report.py"])
    message = f"Publish financial report {args.date}"
    run(["git", "commit", "-m", message])
    run(["git", "push", "origin", "main"])
    print(f"published url={PAGES_URL}")
    print(f"archive url={PAGES_URL}reports/{args.date}.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
