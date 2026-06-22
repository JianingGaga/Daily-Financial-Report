#!/usr/bin/env python3
"""Generate the daily report, push it to GitHub Pages, and print the URL."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGES_URL = "https://jianinggaga.github.io/Daily-Financial-Report/"
SINA_REFERER = {"Referer": "https://finance.sina.com.cn"}


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True, capture_output=True)


def is_a_share_trading_day(date_text: str) -> tuple[bool, str]:
    report_date = dt.date.fromisoformat(date_text)
    if report_date.weekday() >= 5:
        return False, f"{date_text} is weekend"

    url = "https://hq.sinajs.cn/list=sh000001"
    req = urllib.request.Request(url, headers=SINA_REFERER)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("gb18030", errors="replace")
    except Exception as exc:
        return False, f"could not verify trading day: {exc}"

    match = re.search(r'hq_str_sh000001="([^"]*)"', raw)
    if not match:
        return False, "could not parse SHCOMP quote"

    fields = match.group(1).split(",")
    quote_date = fields[30] if len(fields) > 30 else ""
    quote_time = fields[31] if len(fields) > 31 else ""
    volume = float(fields[8] or 0) if len(fields) > 8 else 0
    if quote_date == date_text and volume > 0:
        return True, f"SHCOMP quote date={quote_date} time={quote_time} volume={volume:.0f}"
    return False, f"latest SHCOMP quote date={quote_date or '-'} time={quote_time or '-'} volume={volume:.0f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=dt.datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--time", default=dt.datetime.now().strftime("%H:%M"))
    parser.add_argument("--skip-non-trading-day", action="store_true")
    args = parser.parse_args()

    if args.skip_non_trading_day:
        trading_day, reason = is_a_share_trading_day(args.date)
        if not trading_day:
            print(f"SKIPPED_NON_TRADING_DAY: {reason}")
            return 0
        print(f"trading day confirmed: {reason}")

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
