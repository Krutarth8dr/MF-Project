"""
Download script for Canara MF (Canara Robeco Mutual Fund).
Discovers and downloads monthly portfolio Excel files for 14 target funds:
- LC: Canara Robeco Large Cap Fund
- IN: Canara Robeco Infrastructure Fund
- VF: Canara Robeco Value Fund
- SC: Canara Robeco Small Cap Fund
- MN: Canara Robeco Manufacturing Fund
- MF: Canara Robeco Multi Cap Fund
- MD: Canara Robeco Mid Cap Fund
- MA: Canara Robeco Multi Asset Allocation Fund
- BA: Canara Robeco Balanced Advantage Fund
- ET: Canara Robeco ELSS Tax Saver Fund
- EQ: Canara Robeco Large and Mid Cap Fund
- CF: Canara Robeco Consumption Fund
- DV: Canara Robeco Flexi Cap Fund
- BF: Canara Robeco Banking and Financial Services Fund

Period: October 2024 to September 2026 (or current)
Destination:
01_raw_files/Canara_MF/<YYYY>/<MM>/<CODE>_<filename>.xlsx
"""

import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, unquote

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "Canara_MF"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.canararobeco.com/documents/statutory-disclosures/scheme-dashboard/scheme-monthly-portfolio/",
}

TARGET_CODES = {
    "LC", "IN", "VF", "SC", "MN", "MF", "MD",
    "MA", "BA", "ET", "EQ", "CF", "DV", "BF"
}


def get_code_from_item(title, link):
    t = title.strip()
    m = re.match(r"^([A-Z]{2})\b", t, re.I)
    if m and m.group(1).upper() in TARGET_CODES:
        return m.group(1).upper()

    fname = link.split("/")[-1]
    m2 = re.match(r"^([a-zA-Z]{2})[-_]", fname)
    if m2 and m2.group(1).upper() in TARGET_CODES:
        return m2.group(1).upper()

    return None


def sanitize_filename(name):
    # Remove characters not safe in Windows filenames
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def discover_monthly_links(session, year, month):
    found = {}
    for page in [1, 2, 3]:
        url = (
            f"https://www.canararobeco.com/documents/statutory-disclosures/scheme-dashboard/scheme-monthly-portfolio/"
            f"?filteryear={year}&filtermonth={month}&pagination={page}"
        )
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a"):
                href = a.get("href", "")
                if ".xlsx" in href.lower() or ".xls" in href.lower():
                    code = get_code_from_item(a.text, href)
                    if code and code not in found:
                        found[code] = href
        except Exception as e:
            print(f"  [WARN] Page {page} discovery error ({year}-{month}): {e}")
            time.sleep(1)
    return found


def download_file(session, url, target_path):
    if target_path.exists() and target_path.stat().st_size > 5000:
        return True, "EXISTS"

    target_path.parent.mkdir(parents=True, exist_ok=True)
    # Fix URL encoding if URL has unescaped Unicode characters (e.g. en-dash)
    encoded_url = quote(unquote(url), safe="/:?=&@#")

    for attempt in range(1, 4):
        try:
            resp = session.get(encoded_url, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(target_path, "wb") as f:
                    f.write(resp.content)
                return True, f"DOWNLOADED ({len(resp.content):,} bytes)"
            else:
                time.sleep(1.5)
        except Exception as e:
            time.sleep(1.5)
            if attempt == 3:
                return False, f"FAILED: {e}"

    return False, "FAILED (status/size)"


def main():
    print("=" * 80)
    print("CANARA MF - MONTHLY PORTFOLIO DOWNLOADER (14 TARGET FUNDS)")
    print(f"Destination: {RAW_FOLDER}")
    print("=" * 80)

    # Build months list: Oct 2024 to Sep 2026
    months = []
    for m in ["10", "11", "12"]:
        months.append(("2024", m))
    for m in [f"{i:02d}" for i in range(1, 13)]:
        months.append(("2025", m))
    for m in [f"{i:02d}" for i in range(1, 10)]:
        months.append(("2026", m))

    session = requests.Session()
    session.headers.update(HEADERS)

    total_downloads = 0
    total_skipped = 0
    total_failed = 0

    for yr, mo in months:
        print(f"\n--- Discovering {yr}-{mo} ---")
        links = discover_monthly_links(session, yr, mo)
        print(f"  Found {len(links)}/14 funds")

        month_folder = RAW_FOLDER / yr / mo

        for code, link in links.items():
            raw_fname = unquote(link.split("/")[-1])
            clean_fname = sanitize_filename(f"{code}_{raw_fname}")
            if not clean_fname.lower().endswith((".xlsx", ".xls")):
                clean_fname += ".xlsx"
            target_path = month_folder / clean_fname

            success, msg = download_file(session, link, target_path)
            if success:
                if "EXISTS" in msg:
                    total_skipped += 1
                else:
                    total_downloads += 1
                    print(f"    [{code}] {clean_fname[:40]}: {msg}")
            else:
                total_failed += 1
                print(f"    [FAIL {code}] {link}: {msg}")

    print("\n" + "=" * 80)
    print(f"DOWNLOAD COMPLETE: {total_downloads} downloaded, {total_skipped} already existed, {total_failed} failed")
    print("=" * 80)


if __name__ == "__main__":
    main()
