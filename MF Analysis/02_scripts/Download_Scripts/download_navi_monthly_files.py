"""
Download monthly portfolio disclosure files for Navi Mutual Fund (Navi MF).

Source:
    Website: https://navi.com/mutual-fund/downloads/portfolio
    REST API: https://navi.com/wp-json/nv/v1/documents

Target Funds (3 funds):
    1. Navi Flexi Cap Fund
    2. Navi Large & Midcap Fund
    3. Navi Aggressive Hybrid Fund

Target Period:
    October 2024 to September 2026 (24 months).

Stores raw files in:
    01_raw_files/Navi_MF/<YYYY>/<MM>/<prefix>_<original_filename>.xlsx
"""

import os
import sys
import re
import html
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
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "Navi_MF"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PAGE_URL = "https://navi.com/mutual-fund/downloads/portfolio"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://navi.com/mutual-fund/downloads/portfolio",
}

# Target fund mapping: (prefix, standard_fund_name, search_regexes)
TARGET_FUNDS = [
    ("flexicap", "Navi Flexi Cap Fund", [r"flexi\s*cap"]),
    ("large_midcap", "Navi Large & Midcap Fund", [r"large.*mid\s*cap"]),
    ("aggressive_hybrid", "Navi Aggressive Hybrid Fund", [r"aggressive\s*hybrid"]),
]

# 24 Months configuration: (Year, Month_Number, Month_Name, Financial_Year)
MONTHS_CONFIG = [
    # FY 2024-2025
    (2024, 10, "October", "2024-2025"),
    (2024, 11, "November", "2024-2025"),
    (2024, 12, "December", "2024-2025"),
    (2025, 1, "January", "2024-2025"),
    (2025, 2, "February", "2024-2025"),
    (2025, 3, "March", "2024-2025"),
    # FY 2025-2026
    (2025, 4, "April", "2025-2026"),
    (2025, 5, "May", "2025-2026"),
    (2025, 6, "June", "2025-2026"),
    (2025, 7, "July", "2025-2026"),
    (2025, 8, "August", "2025-2026"),
    (2025, 9, "September", "2025-2026"),
    (2025, 10, "October", "2025-2026"),
    (2025, 11, "November", "2025-2026"),
    (2025, 12, "December", "2025-2026"),
    (2026, 1, "January", "2025-2026"),
    (2026, 2, "February", "2025-2026"),
    (2026, 3, "March", "2025-2026"),
    # FY 2026-2027
    (2026, 4, "April", "2026-2027"),
    (2026, 5, "May", "2026-2027"),
    (2026, 6, "June", "2026-2027"),
    (2026, 7, "July", "2026-2027"),
    (2026, 8, "August", "2026-2027"),
    (2026, 9, "September", "2026-2027"),
]


def get_session_and_nonce():
    """Fetch the main portfolio downloads page to extract the current REST nonce."""
    session = requests.Session()
    session.headers.update(HEADERS)
    resp = session.get(PAGE_URL, timeout=30)
    resp.raise_for_status()

    m = re.search(r"var\s+navi_property\s*=\s*(\{.*?\});", resp.text)
    if not m:
        raise RuntimeError("Could not find navi_property javascript object in page.")

    prop = json.loads(m.group(1))
    nonce = prop.get("nonce")
    rest_url = prop.get("rest_url", "https://navi.com/wp-json/")

    return session, nonce, rest_url


def query_month_documents(session, rest_url, nonce, year, month_num, month_name, fy):
    """Query Navi's document REST API for a specific month."""
    api_url = rest_url + "nv/v1/documents"
    headers = {
        "WP-NONCE": nonce,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }
    payload = {
        "financial_year": fy,
        "value": month_name,
        "category": "884",
        "type": "Monthly",
        "order": "DESC",
    }

    try:
        r = session.post(api_url, headers=headers, data=payload, timeout=30)
        if r.status_code == 200:
            res = r.json()
            return res.get("data", [])
    except Exception as e:
        print(f"  [WARN] Failed to query {year}-{month_num:02d} ({fy} {month_name}): {e}")

    return []


def match_target_document(docs, fund_prefix, fund_name, regex_patterns):
    """Find the document matching one of the target fund patterns."""
    for d in docs:
        title = d.get("title", "")
        clean_title = html.unescape(title).lower()
        if any(re.search(pat, clean_title) for pat in regex_patterns):
            url = d.get("url")
            if isinstance(url, list) and url:
                url = url[0].get("link") if isinstance(url[0], dict) else url[0]
            if url and isinstance(url, str):
                return {"title": title, "url": html.unescape(url)}
    return None


def download_file(session, task):
    """Download single portfolio file with retry logic."""
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
    print("Navi Mutual Fund (Navi MF) - Monthly Portfolio Downloader")
    print("Target: 3 Funds | Period: Oct 2024 to Sep 2026 (24 months)")
    print(f"Target Directory: {RAW_DIR}")
    print("=" * 80)

    print("[1/3] Connecting to Navi MF portal and extracting REST nonce...")
    session, nonce, rest_url = get_session_and_nonce()
    print(f"      Nonce acquired: {nonce} | REST Endpoint: {rest_url}")

    print("\n[2/3] Querying monthly catalogs for 24 months...")
    tasks = []
    missing_records = []

    for year, month_num, month_name, fy in MONTHS_CONFIG:
        docs = query_month_documents(session, rest_url, nonce, year, month_num, month_name, fy)
        for prefix, fund_name, patterns in TARGET_FUNDS:
            match = match_target_document(docs, prefix, fund_name, patterns)
            if match:
                url = match["url"]
                # Create safe clean filename
                # Extract filename part from url
                url_fn = url.split("?")[0].split("/")[-1]
                url_fn = re.sub(r"[^\w\-.]", "_", url_fn)
                if not url_fn.lower().endswith((".xlsx", ".xls")):
                    url_fn += ".xlsx"

                dest_file = RAW_DIR / str(year) / f"{month_num:02d}" / f"{prefix}_{url_fn}"

                tasks.append({
                    "prefix": prefix,
                    "fund_name": fund_name,
                    "year": year,
                    "month": month_num,
                    "url": url,
                    "dest_file": dest_file,
                })
            else:
                missing_records.append((year, month_num, fund_name))

    print(f"      Identified {len(tasks)} target monthly files across 3 funds.")
    if missing_records:
        print(f"      [WARN] {len(missing_records)} files were not matched:")
        for y, m, fn in missing_records:
            print(f"        - {y}-{m:02d}: {fn}")

    # Summary by fund
    by_fund = {}
    for t in tasks:
        by_fund.setdefault(t["fund_name"], []).append(t)
    for fname, flist in sorted(by_fund.items()):
        print(f"      - {fname:<30}: {len(flist):2d} files")

    print(f"\n[3/3] Starting parallel download with 6 workers...")
    counts = {"DOWNLOADED": 0, "EXISTS": 0, "FAILED": 0}

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(download_file, session, t): t for t in tasks}
        for i, fut in enumerate(as_completed(futures), 1):
            status, t = fut.result()
            if status in counts:
                counts[status] += 1
            else:
                counts["FAILED"] += 1
                print(f"      [WARN] {t['prefix']} {t['year']}-{t['month']:02d}: {status}")

            if i % 15 == 0 or i == len(tasks):
                print(f"      Progress: {i}/{len(tasks)} processed ({counts['DOWNLOADED']} downloaded, {counts['EXISTS']} cached, {counts['FAILED']} failed)")

    elapsed = time.time() - start_time
    print("-" * 80)
    print(f"Summary: Completed in {elapsed:.1f}s")
    print(f"  Downloaded : {counts['DOWNLOADED']}")
    print(f"  Cached     : {counts['EXISTS']}")
    print(f"  Failed     : {counts['FAILED']}")
    print("=" * 80)

    if counts["FAILED"] > 0 or len(tasks) < 72:
        if counts["FAILED"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
