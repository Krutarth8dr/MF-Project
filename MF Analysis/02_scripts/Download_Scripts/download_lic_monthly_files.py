"""
Download monthly portfolio disclosure files for LIC Mutual Fund (LIC MF).

Source:
    Website: https://www.licmf.com/downloads/monthly-portfolio
    Files API: https://www.licmf.com/downloads/portfolio-files

Target Funds (17 Equity funds):
    1.  LEULIS  : LIC MF Unit Linked Insurance Scheme
    2.  LEEQTF  : LIC MF Flexi Cap Fund
    3.  LEMIDF  : LIC MF Large & Midcap Fund
    4.  LEBFSF  : LIC MF Banking and Financial Services Fund
    5.  LEMUCF  : LIC MF Multi Cap Fund
    6.  LEDDYF  : LICMF Dividend Yield Fund
    7.  LEFE30  : LICMF Focused Fund
    8.  LEEMCF  : LICMF Mid cap Fund
    9.  LEDHCF  : LICMF Healthcare Fund
    10. LEESCF  : LICMF Small Cap Fund
    11. LEGROW  : LIC MF Large Cap Fund
    12. LELTVF  : LIC MF Value Fund
    13. LEMFGF  : LIC MF Manufacturing Fund
    14. LECOSF  : LIC MF Consumption Fund
    15. LETECF  : LIC MF Technology Fund
    16. LETAXP  : LIC MF ELSS Tax Saver Fund
    17. LEINFA  : LIC MF Infrastructure Fund

Target Period:
    October 2024 to September 2026 (or from inception for newer funds).

Stores raw files in:
    01_raw_files/LIC_MF/<YYYY>/<MM>/<filename>
"""

import sys
import os
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "LIC_MF"

URL_FILES = "https://www.licmf.com/downloads/portfolio-files"
BASE_URL = "https://www.licmf.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

FUNDS = [
    ("LEULIS", "LIC MF Unit Linked Insurance Scheme"),
    ("LEEQTF", "LIC MF Flexi Cap Fund"),
    ("LEMIDF", "LIC MF Large & Midcap Fund"),
    ("LEBFSF", "LIC MF Banking and Financial Services Fund"),
    ("LEMUCF", "LIC MF Multi Cap Fund"),
    ("LEDDYF", "LICMF Dividend Yield Fund"),
    ("LEFE30", "LICMF Focused Fund"),
    ("LEEMCF", "LICMF Mid cap Fund"),
    ("LEDHCF", "LICMF Healthcare Fund"),
    ("LEESCF", "LICMF Small Cap Fund"),
    ("LEGROW", "LIC MF Large Cap Fund"),
    ("LELTVF", "LIC MF Value Fund"),
    ("LEMFGF", "LIC MF Manufacturing Fund"),
    ("LECOSF", "LIC MF Consumption Fund"),
    ("LETECF", "LIC MF Technology Fund"),
    ("LETAXP", "LIC MF ELSS Tax Saver Fund"),
    ("LEINFA", "LIC MF Infrastructure Fund"),
]


def generate_target_months():
    """Generates (year, month) from October 2024 to September 2026."""
    months = []
    for y in [2024, 2025, 2026]:
        for m in range(1, 13):
            if y == 2024 and m < 10:
                continue
            if y == 2026 and m > 9:
                continue
            months.append((y, m))
    return months


def fetch_file_link(session, f_code, year, month):
    """Queries the LIC MF API for a specific fund and month."""
    data = {
        "scheme_code": f_code,
        "fund_name": "",
        "type": "monthly_portfolio",
        "month": str(month),
        "year": str(year)
    }
    for attempt in range(3):
        try:
            r = session.post(URL_FILES, headers=HEADERS, data=data, timeout=20)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                a = soup.find("a", href=True)
                if a and a["href"].endswith((".xlsx", ".xls")):
                    href = a["href"]
                    if not href.startswith("http"):
                        href = BASE_URL + href
                    return href
            return None
        except Exception as e:
            if attempt == 2:
                return None
            time.sleep(1)
    return None


def download_file(session, url, target_path):
    """Downloads a file if not already existing."""
    if target_path.exists() and target_path.stat().st_size > 1000:
        return True, "Already exists"

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp")

    for attempt in range(3):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(temp_path, "wb") as f:
                    f.write(r.content)
                temp_path.replace(target_path)
                return True, f"Downloaded ({len(r.content):,} bytes)"
            time.sleep(1)
        except Exception as e:
            if attempt == 2:
                return False, str(e)
            time.sleep(1)

    if temp_path.exists():
        temp_path.unlink()
    return False, "Failed after 3 attempts"


def process_task(task):
    f_code, f_name, year, month = task
    session = requests.Session()
    link = fetch_file_link(session, f_code, year, month)
    if not link:
        return (f_code, f_name, year, month, None, False, "No file published")

    filename = link.split("/")[-1].split("?")[0]
    # Clean up filename if containing colon
    clean_filename = filename.replace(":", "-")
    target_path = RAW_DIR / str(year) / f"{month:02d}" / f"{f_code}_{clean_filename}"

    ok, msg = download_file(session, link, target_path)
    return (f_code, f_name, year, month, link, ok, msg)


def main():
    print("=" * 80)
    print("LIC Mutual Fund (LIC MF) - Monthly Portfolio Downloader")
    print("=" * 80)
    print(f"Target Funds  : {len(FUNDS)} Equity funds")
    months = generate_target_months()
    print(f"Target Months : {len(months)} (Oct 2024 to Sep 2026)")
    print(f"Output Root   : {RAW_DIR}")
    print("=" * 80)

    tasks = []
    for f_code, f_name in FUNDS:
        for y, m in months:
            tasks.append((f_code, f_name, y, m))

    print(f"\nQuerying and downloading {len(tasks)} fund-month slots using 10 worker threads...\n")

    successful = 0
    not_published = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_task, t): t for t in tasks}
        completed = 0
        for fut in as_completed(futures):
            completed += 1
            f_code, f_name, year, month, link, ok, msg = fut.result()
            if ok:
                successful += 1
                if completed % 20 == 0 or completed == len(tasks):
                    print(f"[{completed:3d}/{len(tasks)}] [OK] {year}-{month:02d} | {f_code:8} ({f_name[:25]:25}) -> {msg}")
            elif not link:
                not_published += 1
            else:
                errors += 1
                print(f"[{completed:3d}/{len(tasks)}] [FAIL] {year}-{month:02d} | {f_code:8} -> {msg}")

    print("\n" + "=" * 80)
    print("Download Summary")
    print("=" * 80)
    print(f"Total Slots Evaluated : {len(tasks)}")
    print(f"Files Downloaded/OK   : {successful}")
    print(f"Not Published         : {not_published}")
    print(f"Failed Downloads      : {errors}")
    print(f"Output Directory      : {RAW_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
