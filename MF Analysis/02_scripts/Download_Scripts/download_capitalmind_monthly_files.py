"""
Download script for Capital Mind MF (Capitalmind Mutual Fund).
Discovers and downloads monthly portfolio Excel files for 2 target funds:
- CMFLEXI: Capitalmind Flexi Cap Fund
- CMMAAF: Capitalmind Multi Asset Allocation Fund

Source:
https://capitalmindmf.com/statutory-disclosures.html
Destination:
01_raw_files/Capital_Mind_MF/<YYYY>/<MM>/<CODE>_<filename>.xlsx
"""

import datetime
import io
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import openpyxl
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "Capital_Mind_MF"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

DISCLOSURES_URL = "https://capitalmindmf.com/statutory-disclosures.html"
BASE_URL = "https://capitalmindmf.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://capitalmindmf.com/statutory-disclosures.html",
}

MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}


def parse_year_month_from_text_or_url(text, url):
    s = f"{text} {url}".lower()
    # Search for year: 2024, 2025, 2026
    m_yr = re.search(r"202[456]", s)
    yr = m_yr.group(0) if m_yr else None

    # Search for month name
    mo = None
    for name, num in MONTH_MAP.items():
        if re.search(r"\b" + name + r"\b", s):
            mo = num
            break

    return yr, mo


def main():
    print("=" * 80)
    print("CAPITAL MIND MF - MONTHLY PORTFOLIO DOWNLOADER (2 TARGET FUNDS)")
    print(f"Destination: {RAW_FOLDER}")
    print("=" * 80)

    session = requests.Session()
    session.headers.update(HEADERS)

    print("Fetching disclosures page...")
    resp = session.get(DISCLOSURES_URL, timeout=20)
    if resp.status_code != 200:
        print(f"[ERROR] Failed to fetch disclosures page: HTTP {resp.status_code}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    target_links = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if not (href.lower().endswith(".xlsx") or href.lower().endswith(".xls")):
            continue
        h_lower = href.lower()
        if any(x in h_lower for x in ["cmliq", "cmarb", "dashboard", "average", "aum"]):
            continue

        full_url = urljoin(BASE_URL, href)

        if "cmmaaf" in h_lower:
            code = "CMMAAF"
            target_links.append((code, full_url, href))
        elif "cmflexi" in h_lower or "capitalmind_monthly_portfolio_disclosure" in h_lower:
            code = "CMFLEXI"
            target_links.append((code, full_url, href))

    # Deduplicate links
    seen = set()
    unique_links = []
    for code, full_url, href in target_links:
        if full_url not in seen:
            seen.add(full_url)
            unique_links.append((code, full_url, href))

    print(f"Discovered {len(unique_links)} target portfolio files.")

    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    for code, full_url, href in unique_links:
        fname = href.split("/")[-1]
        yr, mo = parse_year_month_from_text_or_url("", fname)

        if not (yr and mo):
            # Fallback: fetch header / date
            try:
                r_probe = session.get(full_url, timeout=20)
                if r_probe.status_code == 200:
                    wb = openpyxl.load_workbook(io.BytesIO(r_probe.content), data_only=True)
                    ws = wb.active
                    for row in list(ws.iter_rows(values_only=True))[:6]:
                        r_str = " ".join(str(c or "") for c in row)
                        m_dt = re.search(r"([A-Za-z]+)\s+\d{1,2},?\s*(202[456])", r_str)
                        if m_dt:
                            m_name, yr_found = m_dt.group(1).lower(), m_dt.group(2)
                            if m_name in MONTH_MAP:
                                yr, mo = yr_found, MONTH_MAP[m_name]
                                break
                    wb.close()
            except Exception:
                pass

        if not (yr and mo):
            yr, mo = "2026", "09"

        target_dir = RAW_FOLDER / yr / mo
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{code}_{fname}"

        if target_path.exists() and target_path.stat().st_size > 1000:
            total_skipped += 1
            print(f"  [EXISTS] {yr}/{mo}/{code}_{fname[:35]}")
            continue

        try:
            r = session.get(full_url, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(target_path, "wb") as f:
                    f.write(r.content)
                total_downloaded += 1
                print(f"  [OK] Saved {yr}/{mo}/{code}_{fname[:35]} ({len(r.content):,} bytes)")
            else:
                total_failed += 1
                print(f"  [FAIL] {full_url} (status: {r.status_code}, size: {len(r.content)})")
        except Exception as e:
            total_failed += 1
            print(f"  [ERROR] {full_url}: {e}")

    print("\n" + "=" * 80)
    print(f"DOWNLOAD COMPLETE: {total_downloaded} downloaded, {total_skipped} skipped, {total_failed} failed.")
    print("=" * 80)


if __name__ == "__main__":
    main()
