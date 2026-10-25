"""
Download monthly portfolio disclosure files for Mirae Asset Mutual Fund (Mirae MF).

Source:
    Website: https://www.miraeassetmf.co.in/downloads/portfolio
    AJAX Catalog API: https://www.miraeassetmf.co.in/AjaxService/GetDownloadsData

Target Funds (16 funds):
    1.  mafcf  : Mirae Asset Flexi Cap Fund
    2.  mamaaf : Mirae Asset Multi Asset Allocation Fund
    3.  maff   : Mirae Asset Focused Fund
    4.  maonf  : Mirae Asset Overnight Fund
    5.  miiof  : Mirae Asset Large Cap Fund
    6.  miccf  : Mirae Asset Great Consumer Fund
    7.  maebf  : Mirae Asset Large & Midcap Fund
    8.  matsf  : Mirae Asset ELSS Tax Saver Fund
    9.  mamcf  : Mirae Asset Midcap Fund
    10. maesf  : Mirae Asset Equity Savings Fund
    11. mascf  : Mirae Asset Small Cap Fund
    12. mabaf  : Mirae Asset Balanced Advantage Fund
    13. mabff  : Mirae Asset Banking and Financial Services Fund
    14. mampf  : Mirae Asset Multicap Fund
    15. infra  : Mirae Asset Infrastructure Fund
    16. mahcf  : Mirae Asset Healthcare Fund

Target Period:
    October 2024 to September 2026 (or from inception for newer funds).

Stores raw files in:
    01_raw_files/Mirae_MF/<YYYY>/<MM>/<prefix>_<original_filename>.xlsx
"""

import os
import sys
import re
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "Mirae_MF"
RAW_DIR.mkdir(parents=True, exist_ok=True)

CATALOG_URL = "https://www.miraeassetmf.co.in/AjaxService/GetDownloadsData"
BASE_URL = "https://www.miraeassetmf.co.in"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.miraeassetmf.co.in/downloads/portfolio",
    "Content-Type": "application/json; charset=utf-8",
    "X-Requested-With": "XMLHttpRequest",
}

TARGET_FUNDS = {
    "mafcf": "Mirae Asset Flexi Cap Fund",
    "mamaaf": "Mirae Asset Multi Asset Allocation Fund",
    "maff": "Mirae Asset Focused Fund",
    "maonf": "Mirae Asset Overnight Fund",
    "miiof": "Mirae Asset Large Cap Fund",
    "miccf": "Mirae Asset Great Consumer Fund",
    "maebf": "Mirae Asset Large & Midcap Fund",
    "matsf": "Mirae Asset ELSS Tax Saver Fund",
    "mamcf": "Mirae Asset Midcap Fund",
    "maesf": "Mirae Asset Equity Savings Fund",
    "mascf": "Mirae Asset Small Cap Fund",
    "mabaf": "Mirae Asset Balanced Advantage Fund",
    "mabff": "Mirae Asset Banking and Financial Services Fund",
    "mampf": "Mirae Asset Multicap Fund",
    "infra": "Mirae Asset Infrastructure Fund",
    "mahcf": "Mirae Asset Healthcare Fund",
}

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def fetch_catalog():
    """Fetch the full portfolio downloads catalog from Mirae Asset's Ajax endpoint."""
    print("[1/3] Fetching portfolio catalog from Mirae Asset API...")
    payload = {
        "request": {
            "modulename": "portfolio_tab1",
            "pgno": 1,
            "pgsize": 4500,
        }
    }
    try:
        resp = requests.post(CATALOG_URL, headers=HEADERS, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        raw_items = data.get("Data", [])
        if not raw_items:
            raw_items = data.get("d", [])
        if isinstance(raw_items, str):
            raw_items = json.loads(raw_items)
        print(f"      Retrieved {len(raw_items)} catalog entries from API.")
        return raw_items
    except Exception as e:
        print(f"      [WARN] API request failed: {e}. Checking local cache...")
        cache_path = Path(__file__).resolve().parents[3] / ".gemini" / "antigravity" / "brain"
        # Find any mirae_all_downloads.json in scratch
        candidates = list(PROJECT_ROOT.parent.rglob("mirae_all_downloads.json"))
        if candidates and candidates[0].exists():
            print(f"      Using cached catalog from {candidates[0]}")
            with open(candidates[0], "r", encoding="utf-8") as f:
                return json.load(f)
        raise RuntimeError("Could not retrieve catalog from API or local cache.")


def parse_catalog_entries(items):
    """Filter catalog entries for target funds between Oct 2024 and Sep 2026."""
    tasks = []
    seen_destinations = set()

    for it in items:
        url = it.get("URL", "")
        if not url:
            continue
        clean_url = url.split("?")[0]
        fn = clean_url.split("/")[-1].lower()
        if not fn.endswith((".xlsx", ".xls")):
            continue

        for prefix, fund_name in TARGET_FUNDS.items():
            matched_prefix = False
            if prefix == "miccf" and "miicf_feb2025" in fn:
                matched_prefix = True
            elif fn.startswith(prefix + "_") or fn.startswith(prefix + "-"):
                matched_prefix = True

            if not matched_prefix:
                continue

            m = re.search(r"([a-z]+)[-_]?(\d{4})\.xlsx?$", fn)
            if not m:
                continue

            m_str, y_str = m.group(1), m.group(2)
            month = MONTH_MAP.get(m_str)
            year = int(y_str)

            if not month or not ((2024, 10) <= (year, month) <= (2026, 9)):
                continue

            full_url = BASE_URL + clean_url if clean_url.startswith("/") else clean_url
            dest_dir = RAW_DIR / str(year) / f"{month:02d}"
            dest_file = dest_dir / f"{prefix}_{fn}"

            if str(dest_file) in seen_destinations:
                continue
            seen_destinations.add(str(dest_file))

            tasks.append({
                "prefix": prefix,
                "fund_name": fund_name,
                "year": year,
                "month": month,
                "url": full_url,
                "dest_file": dest_file,
            })

    return tasks


def download_single_file(session, task):
    """Download one portfolio file if not already existing with valid size."""
    dest_file = task["dest_file"]
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    if dest_file.exists() and dest_file.stat().st_size > 1024:
        return "EXISTS", task

    url = task["url"]
    for attempt in range(1, 4):
        try:
            r = session.get(url, timeout=45)
            if r.status_code == 200 and len(r.content) > 1024:
                dest_file.write_bytes(r.content)
                return "DOWNLOADED", task
            elif r.status_code == 404:
                return f"HTTP_{r.status_code}", task
        except Exception as e:
            if attempt == 3:
                return f"ERR: {e}", task
            time.sleep(1.0 * attempt)

    return "FAILED", task


def main():
    print("=" * 80)
    print("Mirae Asset Mutual Fund (Mirae MF) - Monthly Portfolio Downloader")
    print(f"Target: 16 Funds | Period: Oct 2024 to Sep 2026")
    print(f"Target Directory: {RAW_DIR}")
    print("=" * 80)

    items = fetch_catalog()
    tasks = parse_catalog_entries(items)

    print(f"[2/3] Identified {len(tasks)} target monthly files across {len(TARGET_FUNDS)} funds.")

    # Breakdown by fund
    by_fund = {}
    for t in tasks:
        by_fund.setdefault(t["fund_name"], []).append(t)
    for fname, flist in sorted(by_fund.items()):
        print(f"      - {fname:<45}: {len(flist):2d} files")

    print(f"[3/3] Starting parallel download with 10 workers...")
    counts = {"DOWNLOADED": 0, "EXISTS": 0, "FAILED": 0}

    session = requests.Session()
    session.headers.update({
        "User-Agent": HEADERS["User-Agent"],
        "Referer": HEADERS["Referer"],
    })

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(download_single_file, session, t): t for t in tasks}
        for i, fut in enumerate(as_completed(futures), 1):
            status, t = fut.result()
            if status in counts:
                counts[status] += 1
            else:
                counts["FAILED"] += 1
                print(f"      [WARN] {t['prefix']} {t['year']}-{t['month']:02d}: {status}")

            if i % 50 == 0 or i == len(tasks):
                print(f"      Progress: {i}/{len(tasks)} processed ({counts['DOWNLOADED']} downloaded, {counts['EXISTS']} cached, {counts['FAILED']} failed)")

    elapsed = time.time() - start_time
    print("-" * 80)
    print(f"Summary: Completed in {elapsed:.1f}s")
    print(f"  Downloaded : {counts['DOWNLOADED']}")
    print(f"  Cached     : {counts['EXISTS']}")
    print(f"  Failed     : {counts['FAILED']}")
    print("=" * 80)

    if counts["FAILED"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
