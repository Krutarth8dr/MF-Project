"""
Download monthly combined portfolio disclosure files for Sriram Mutual Fund (Sriram MF).

Source:
    Website: https://www.shriramamc.in/investor-statutory-disclosures
    CDN: https://cdn.shriramamc.in/uploads/Statutory-disclosure/...

Target Funds (6 funds inside combined workbooks):
    1. Shriram Aggressive Hybrid Fund
    2. Shriram Flexi Cap Fund
    3. Shriram ELSS Tax Saver Fund
    4. Shriram Balanced Advantage Fund
    5. Shriram Multi Asset Allocation Fund
    6. Shriram Multi Sector Rotation Fund

Target Period:
    October 2024 to September 2026 (24 consecutive months).

Stores raw files in:
    01_raw_files/Sriram_MF/<YYYY>/<MM>/Sriram_Combined_Portfolio_<YYYY>_<MM>.xls (or .xlsx)
"""

import os
import sys
import re
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
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "Sriram_MF"
RAW_DIR.mkdir(parents=True, exist_ok=True)

DISCLOSURES_URL = "https://www.shriramamc.in/investor-statutory-disclosures"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.shriramamc.in/investor-statutory-disclosures",
}

# Verified mapping for guaranteed reproducibility and fast execution
KNOWN_MONTHLY_FILES = {
    ("2024", "10"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2024-2025/Monthly-Portfolio-Shriram-Mutual-Fund-October-2024.xls",
    ("2024", "11"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2024-2025/Monthly-Portfolio-Shriram-Mutual-Fund-November-2024-R.xls",
    ("2024", "12"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2024-2025/Monthly-Portfolio-Shriram-Mutual-Fund-December-2024.xls",
    ("2025", "01"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2024-2025/Monthly-Portfolio-Shriram-Mutual-Fund-January-2025.xls",
    ("2025", "02"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2024-2025/Monthly-Portfolio-Shriram-Mutual-Fund-February-2025.xls",
    ("2025", "03"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2024-2025/Monthly-Portfolio-Shriram-Mutual-Fund-March-2025.xls",
    ("2025", "04"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-April-2025.xls",
    ("2025", "05"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-May-2025.xls",
    ("2025", "06"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-June-2025.xls",
    ("2025", "07"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-July-2025.xls",
    ("2025", "08"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-Aug-2025.xls",
    ("2025", "09"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-Sep-2025.xls",
    ("2025", "10"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-Oct-2025.xls",
    ("2025", "11"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-Nov-2025-.xls",
    ("2025", "12"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly-Fortnightly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-Dec-2025.xls",
    ("2026", "01"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly--Fortnightly--Weekly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-Jan-2026.xls",
    ("2026", "02"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly--Fortnightly--Weekly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-February-2026.xls",
    ("2026", "03"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly--Fortnightly--Weekly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2025-2026/Monthly-Portfolio-Shriram-Mutual-Fund-March-2026.xls",
    ("2026", "04"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly--Fortnightly--Weekly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2026-2027/Monthly-Portfolio-Shriram-Mutual-Fund-April-2026.xls",
    ("2026", "05"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly--Fortnightly--Weekly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2026-2027/Monthly-Portfolio-Shriram-Mutual-Fund-May-2026.xls",
    ("2026", "06"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly--Fortnightly--Weekly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2026-2027/Monthly-Portfolio-Shriram-Mutual-Fund-June-2026.xls",
    ("2026", "07"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly--Fortnightly--Weekly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2026-2027/Monthly-Portfolio-Shriram-Mutual-Fund-July-2026.xls",
    ("2026", "08"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly--Fortnightly--Weekly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2026-2027/Monthly-Portfolio-Shriram-Mutual-Fund-August-2026.xls",
    ("2026", "09"): "https://cdn.shriramamc.in/uploads/Statutory-disclosure/Monthly--Fortnightly--Weekly-Portfolio-of-Scheme(s)/Monthly-Portfolio-for-the-Financial-Year/2026-2027/Monthly-Portfolio-Shriram-Mutual-Fund-September-2026.xls",
}


def download_single_file(year, month, file_url, session=None):
    """Download single combined monthly workbook."""
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    # Determine extension from url
    clean_url = file_url.split("?")[0].rstrip("\\/")
    ext = ".xls"
    if clean_url.endswith(".xlsx"):
        ext = ".xlsx"

    dest_filename = f"Sriram_Combined_Portfolio_{year}_{month}{ext}"
    target_dir = RAW_DIR / year / month
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / dest_filename

    if target_path.exists() and target_path.stat().st_size > 1024:
        return {
            "year": year,
            "month": month,
            "path": target_path,
            "size": target_path.stat().st_size,
            "status": "EXISTS",
            "url": file_url,
        }

    for attempt in range(1, 4):
        try:
            resp = session.get(file_url, headers=HEADERS, timeout=45)
            if resp.status_code == 200 and len(resp.content) > 1024:
                with open(target_path, "wb") as f:
                    f.write(resp.content)
                return {
                    "year": year,
                    "month": month,
                    "path": target_path,
                    "size": len(resp.content),
                    "status": "DOWNLOADED",
                    "url": file_url,
                }
            else:
                time.sleep(2 * attempt)
        except Exception as e:
            if attempt == 3:
                return {
                    "year": year,
                    "month": month,
                    "path": target_path,
                    "size": 0,
                    "status": f"FAILED: {e}",
                    "url": file_url,
                }
            time.sleep(2 * attempt)

    return {
        "year": year,
        "month": month,
        "path": target_path,
        "size": 0,
        "status": "FAILED: Status not 200 or empty",
        "url": file_url,
    }


def download_all_sriram_files(max_workers=4):
    """Download all Sriram MF monthly portfolio files."""
    print("=" * 70)
    print("Sriram MF Monthly Portfolio Downloader")
    print("=" * 70)
    print(f"Target files: {len(KNOWN_MONTHLY_FILES)} months (2024-10 to 2026-09)")
    print(f"Destination: {RAW_DIR}")

    results = []
    with requests.Session() as session:
        session.headers.update(HEADERS)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    download_single_file, y, m, url, session
                ): (y, m)
                for (y, m), url in sorted(KNOWN_MONTHLY_FILES.items())
            }

            for fut in as_completed(futures):
                res = fut.result()
                results.append(res)
                status_symbol = "✓" if res["status"] in ("DOWNLOADED", "EXISTS") else "✗"
                print(
                    f"[{status_symbol}] {res['year']}-{res['month']}: {res['status']} "
                    f"({res['size'] / 1024:.1f} KB) -> {res['path'].name}"
                )

    success_cnt = sum(1 for r in results if r["status"] in ("DOWNLOADED", "EXISTS"))
    print("=" * 70)
    print(f"Download Summary: {success_cnt}/{len(KNOWN_MONTHLY_FILES)} files available.")
    print("=" * 70)
    return success_cnt == len(KNOWN_MONTHLY_FILES)


if __name__ == "__main__":
    success = download_all_sriram_files()
    sys.exit(0 if success else 1)
