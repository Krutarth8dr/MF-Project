"""
Download monthly portfolio disclosure files for NJ Mutual Fund (NJ MF).

Source:
    Website: https://downloads.njmutualfund.com/njmf_download.php?nme=127
    Base File URL: https://downloads.njmutualfund.com/viewfile.php?file=

Target Funds (3 funds):
    1. NJ Flexi Cap Fund (NJFCP)
    2. NJ Balanced Advantage Fund (NJBAF)
    3. NJ Value Fund (NJVAF)

Target Period:
    October 2024 to September 2026 (24 months or from fund inception).

Note:
    - Months Oct 2024 to Aug 2025 provide consolidated multi-scheme workbooks
      containing 'NJFCP' and 'NJBAF' sheets.
    - Months Sep 2025 to Sep 2026 provide scheme-specific individual workbooks.
    - NJ Value Fund was launched in August 2026.

Stores raw files in:
    01_raw_files/NJ_MF/<YYYY>/<MM>/<prefix>_<original_filename>.xlsx
"""

import os
import sys
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "NJ_MF"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PORTAL_URL = "https://downloads.njmutualfund.com/njmf_download.php?nme=127"
BASE_FILE_URL = "https://downloads.njmutualfund.com/viewfile.php?file="

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://downloads.njmutualfund.com/",
}

TARGET_CODES = ["NJFCP", "NJBAF", "NJVAF"]

MONTH_NAMES = {
    10: "october", 11: "november", 12: "december",
    1: "january", 2: "february", 3: "march",
    4: "april", 5: "may", 6: "june",
    7: "july", 8: "august", 9: "september"
}


def fetch_download_page():
    """Fetch the main downloads HTML page."""
    session = requests.Session()
    session.headers.update(HEADERS)
    resp = session.get(PORTAL_URL, timeout=30)
    resp.raise_for_status()
    return session, resp.text


def parse_page_links(html_text):
    """Parse all viewfile links from HTML."""
    soup = BeautifulSoup(html_text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if "viewfile.php" in href:
            text = a.text.strip()
            links.append((text, href))
    return links


def build_download_tasks(links):
    """Map the 24 months to their corresponding file download tasks."""
    tasks = []

    for y in [2024, 2025, 2026]:
        for m in range(1, 13):
            if (y, m) < (2024, 10) or (y, m) > (2026, 9):
                continue

            m_name = MONTH_NAMES[m]
            found_scheme_files = {}
            found_multi_file = None

            for text, href in links:
                h_lower = unquote(href).lower()
                t_lower = unquote(text).lower()

                # Check month match
                if m_name not in t_lower and m_name not in h_lower:
                    continue

                # Check year match in text or href
                m_year_in_text = str(y) in t_lower or (str(y)[2:] in t_lower and ("-" + str(y)[2:] in t_lower or " " + str(y)[2:] in t_lower))
                m_year_in_href = f"-{m_name}-{y}" in h_lower or f"_{m_name}_{y}" in h_lower or f"---{m_name}-{y}" in h_lower
                if not (m_year_in_text or m_year_in_href):
                    continue

                # Check if it's a specific scheme file
                for code in TARGET_CODES:
                    if code.lower() in h_lower or code.lower() in t_lower:
                        found_scheme_files[code] = href

                # Check if it's a consolidated multi-scheme file
                if "monthly-portfolio-disclosure" in h_lower or "in-mf-monthly-portfolio" in h_lower:
                    if not any(c.lower() in h_lower for c in ["njfcp", "njbaf", "njvaf", "njabf", "njelstch", "njoverfd", "njmof"]):
                        found_multi_file = href

            dest_dir = RAW_DIR / str(y) / f"{m:02d}"

            if found_scheme_files:
                for code, href in found_scheme_files.items():
                    filename = href.split("file=")[-1] if "file=" in href else href.split("/")[-1]
                    dest_file = dest_dir / f"{code}_{filename}"
                    full_url = "https://downloads.njmutualfund.com/" + href if href.startswith("viewfile") else href
                    tasks.append({
                        "type": "scheme",
                        "code": code,
                        "year": y,
                        "month": m,
                        "url": full_url,
                        "dest_file": dest_file
                    })
            elif found_multi_file:
                filename = found_multi_file.split("file=")[-1] if "file=" in found_multi_file else found_multi_file.split("/")[-1]
                dest_file = dest_dir / f"MULTI_{filename}"
                full_url = "https://downloads.njmutualfund.com/" + found_multi_file if found_multi_file.startswith("viewfile") else found_multi_file
                tasks.append({
                    "type": "multi",
                    "code": "MULTI",
                    "year": y,
                    "month": m,
                    "url": full_url,
                    "dest_file": dest_file
                })
            else:
                print(f"[WARN] No portfolio file identified for {y}-{m:02d} ({m_name.capitalize()})")

    return tasks


def download_single_file(session, task):
    """Download one portfolio workbook if not already present."""
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
    print("NJ Mutual Fund (NJ MF) - Monthly Portfolio Downloader")
    print("Target: 3 Funds | Period: Oct 2024 to Sep 2026")
    print(f"Target Directory: {RAW_DIR}")
    print("=" * 80)

    print("[1/3] Fetching NJ Mutual Fund download portal page...")
    session, html_text = fetch_download_page()
    links = parse_page_links(html_text)
    print(f"      Parsed {len(links)} portfolio download links from portal.")

    print("\n[2/3] Mapping files for target 24 months (Oct 2024 to Sep 2026)...")
    tasks = build_download_tasks(links)
    print(f"      Identified {len(tasks)} files to download.")

    by_type = {}
    for t in tasks:
        by_type.setdefault(t["code"], []).append(t)
    for k, flist in sorted(by_type.items()):
        print(f"      - {k:<8}: {len(flist):2d} files")

    print(f"\n[3/3] Starting parallel download with 6 workers...")
    counts = {"DOWNLOADED": 0, "EXISTS": 0, "FAILED": 0}

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(download_single_file, session, t): t for t in tasks}
        for i, fut in enumerate(as_completed(futures), 1):
            status, t = fut.result()
            if status in counts:
                counts[status] += 1
            else:
                counts["FAILED"] += 1
                print(f"      [WARN] {t['code']} {t['year']}-{t['month']:02d}: {status}")

            if i % 10 == 0 or i == len(tasks):
                print(f"      Progress: {i}/{len(tasks)} processed ({counts['DOWNLOADED']} downloaded, {counts['EXISTS']} cached, {counts['FAILED']} failed)")

    elapsed = time.time() - start_time
    print("-" * 80)
    print(f"Summary: Completed in {elapsed:.1f}s")
    print(f"  Downloaded : {counts['DOWNLOADED']}")
    print(f"  Cached     : {counts['EXISTS']}")
    print(f"  Failed     : {counts['FAILED']}")
    print("=" * 80)

    if counts["FAILED"] > 0 or len(tasks) < 39:
        if counts["FAILED"] > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
