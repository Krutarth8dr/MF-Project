"""
Motilal Oswal Mutual Fund - Monthly Portfolio Downloader
Downloads monthly portfolio workbooks (Scheme Portfolio Details) from October 2024 to August 2026 (23 months).
Files are saved to: 01_raw_files/MOTILAL/<YYYY>/<MM>/
"""

import os
import sys
import json
import urllib.parse
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "MOTILAL"
BASE_URL = "https://www.motilaloswalmf.com"
SEARCH_API_URL = f"{BASE_URL}/content/aem-cloud-dept-backend-motilal-oswal/api/search-documents.json"
DROPDOWN_API_URL = f"{BASE_URL}/content/aem-cloud-dept-backend-motilal-oswal/api/downloads-dropdown-options.json?type=mf"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 23 Target Months: October 2024 to August 2026
TARGET_MONTHS = [
    # 2024
    ("2024-10", ["october 2024", "oct 2024", "oct-24", "10-2024", "31-10-2024", "31102024", "october-2024"]),
    ("2024-11", ["november 2024", "nov 2024", "nov-24", "11-2024", "30-11-2024", "30112024", "november-2024"]),
    ("2024-12", ["december 2024", "dec 2024", "dec-24", "12-2024", "31-12-2024", "31122024", "december-2024"]),
    # 2025
    ("2025-01", ["january 2025", "jan 2025", "jan-25", "01-2025", "31-01-2025", "31012025", "january-2025"]),
    ("2025-02", ["february 2025", "feb 2025", "feb-25", "02-2025", "28-02-2025", "28022025", "february-2025"]),
    ("2025-03", ["march 2025", "mar 2025", "mar-25", "03-2025", "31-03-2025", "31032025", "march-2025"]),
    ("2025-04", ["april 2025", "apr 2025", "apr-25", "04-2025", "30-04-2025", "30042025", "april-2025"]),
    ("2025-05", ["may 2025", "may-2025"]),
    ("2025-06", ["june 2025", "jun 2025", "jun-25", "06-2025", "30-06-2025", "30062025", "june-2025"]),
    ("2025-07", ["july 2025", "jul 2025", "jul-25", "07-2025", "31-07-2025", "31072025", "july-2025"]),
    ("2025-08", ["august 2025", "aug 2025", "aug-25", "08-2025", "31-08-2025", "31082025", "aug-2025"]),
    ("2025-09", ["september 2025", "sep 2025", "sep-25", "09-2025", "30-09-2025", "30092025", "september-2025"]),
    ("2025-10", ["october 2025", "oct 2025", "oct-25", "10-2025", "31-10-2025", "31102025", "october-2025"]),
    ("2025-11", ["november 2025", "nov 2025", "nov-25", "11-2025", "30-11-2025", "30112025", "november-2025"]),
    ("2025-12", ["december 2025", "dec 2025", "dec-25", "12-2025", "31-12-2025", "31122025", "december-2025"]),
    # 2026
    ("2026-01", ["january 2026", "jan 2026", "jan-26", "01-2026", "31-01-2026", "31012026", "january-2026"]),
    ("2026-02", ["february 2026", "feb 2026", "feb-26", "02-2026", "28-02-2026", "28022026", "february-26"]),
    ("2026-03", ["march 2026", "mar 2026", "mar-26", "03-2026", "31-03-2026", "31032026", "31.03.2026"]),
    ("2026-04", ["april 2026", "apr 2026", "apr-26", "04-2026", "30-04-2026", "30042026", "30 april 2026"]),
    ("2026-05", ["31-05-2026", "may 2026"]),
    ("2026-06", ["june 2026", "jun 2026", "jun-26", "06-2026", "30-06-2026", "30062026"]),
    ("2026-07", ["31-07-2026", "july 2026"]),
    ("2026-08", ["august 2026", "aug 2026", "aug-26", "08-2026", "31-08-2026", "31082026"])
]

# Explicit static fallback mapping verified from Motilal API
STATIC_FILE_MAP = {
    "2024-10": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2024/nov/6f698-month-end-portfolio-october-2024.xls",
    "2024-11": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2024/dec/c9f2c-month-end-portfolio-november-2024.xls",
    "2024-12": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/jan/b4801-month-end-portfolio-december-2024.xls",
    "2025-01": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/feb/b1185-month-end-portfolio-january-2025.xlsx",
    "2025-02": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/mar/5a466-month-end-portfolio-february-2025.xlsx",
    "2025-03": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/apr/3a234-month-end-portfolio-march-2025.xls",
    "2025-04": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/may/32d91-month-end-portfolio-april-2025.xlsx",
    "2025-05": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/jun/27945-month-end-portfolio-may-2025.xlsx",
    "2025-06": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/jul/bc9a7-month-end-portfolio-june-2025.xlsx",
    "2025-07": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/aug/09555-scheme-portfolio-details-july-2025.xlsx",
    "2025-08": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/sep/deebc-scheme-portfolio-details-aug-2025.xlsx",
    "2025-09": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/oct/6abd7-scheme-portfolio-details-october-2025.xlsx",
    "2025-10": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/nov/9ec4e-scheme-portfolio-details-october-2025.xlsx",
    "2025-11": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2025/dec/966d5-scheme-portfolio-details-november-2025.xlsx",
    "2025-12": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/jan/db566-scheme-portfolio-details-december-2025.xlsx",
    "2026-01": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/feb/b5209-scheme-portfolio-details-january-2026-2-.xlsx",
    "2026-02": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/mar/8c1a9-scheme-portfolio-details-february-26.xlsx",
    "2026-03": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/apr/IN_MF_MOTILAL_FACTSHEET_31.03.2026_Final.xlsx",
    "2026-04": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/may/Motilal Portfolio 30 April 2026 - Final.xlsx",
    "2026-05": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/jun/Scheme Portfolio Details 31-05-2026.xlsx",
    "2026-06": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/jul/Scheme Portfolio Details June 20261.xlsx",
    "2026-07": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/aug/Monthly Portfolio 31-07-2026-Final.xlsx",
    "2026-08": "/content/dam/motilal-mf/downloads/mf/month-end-portfolio/2026/sep/Copy of Scheme Portfolio Details Aug 2026.xlsx"
}


def download_all_motilal_files():
    print("=" * 75)
    print("MOTILAL OSWAL MUTUAL FUND - PORTFOLIO DOWNLOADER")
    print(f"Target Directory: {RAW_DIR}")
    print(f"Target Months:    {len(TARGET_MONTHS)} (Oct 2024 to Aug 2026)")
    print("=" * 75)

    downloaded_count = 0
    skipped_count = 0

    for ym, patterns in TARGET_MONTHS:
        year, month_num = ym.split("-")
        dest_dir = RAW_DIR / year / month_num
        dest_dir.mkdir(parents=True, exist_ok=True)

        rel_path = STATIC_FILE_MAP.get(ym)
        if not rel_path:
            print(f"[WARN] No URL mapped for {ym}")
            continue

        raw_filename = os.path.basename(rel_path)
        clean_filename = urllib.parse.unquote(raw_filename)
        dest_file = dest_dir / clean_filename

        # Check if already downloaded and non-empty
        if dest_file.exists() and dest_file.stat().st_size > 5000:
            print(f"[SKIP] [{ym}] Already exists: {dest_file.name} ({dest_file.stat().st_size:,} bytes)")
            skipped_count += 1
            continue

        # Download file
        encoded_path = urllib.parse.quote(rel_path)
        url = f"{BASE_URL}{encoded_path}"
        print(f"[DOWNLOADING] [{ym}] {url} -> {dest_file.name}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 5000:
                with open(dest_file, "wb") as f:
                    f.write(resp.content)
                print(f"  [OK] Saved ({len(resp.content):,} bytes)")
                downloaded_count += 1
            else:
                print(f"  [ERROR] Status: {resp.status_code}, Length: {len(resp.content)}")
        except Exception as e:
            print(f"  [ERROR] Download failed: {e}")

    print("\n" + "=" * 75)
    print(f"Download Summary: {downloaded_count} downloaded, {skipped_count} skipped, Total: {len(TARGET_MONTHS)}")
    print("=" * 75)


if __name__ == "__main__":
    download_all_motilal_files()
