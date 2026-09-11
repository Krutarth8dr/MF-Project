import os
import re
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from curl_cffi import requests

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "TATA"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

PAGE_URL = "https://www.tatamutualfund.com/schemes-related/portfolio"

START_DATE = datetime(2024, 10, 1)
END_DATE = datetime(2026, 8, 31)

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}

# ==============================================================================
# CATALOG EXTRACTION
# ==============================================================================

def parse_date_from_filename(filename_or_url):
    dec = urllib.parse.unquote(filename_or_url)
    
    # Matches patterns like:
    # "Monthly Portfolio as on 31st August 2026.xlsx"
    # "Monthly Portfolio as on - 31st January 2025.xls"
    # "portfolio-as-on-31st-october-2024.xls"
    # "2026-09/Monthly Portfolio as on 31st August 2026.xlsx"
    
    # 1. Regex for "as on ... [day] [month] [year]"
    m = re.search(r'(?:as\s*on|portfolio)\s*[-_]?\s*(?:[-_]?\s*)?(\d{1,2})(?:st|nd|rd|th)?\s*[-_ ]\s*([a-zA-Z]+)\s*[-_ ]\s*(\d{4})', dec, re.I)
    if m:
        day_str, mo_str, yr_str = m.groups()
        mo_num = MONTH_MAP.get(mo_str.lower().strip())
        if mo_num:
            return datetime(int(yr_str), mo_num, 1)

    # 2. Regex for "[month] [year]"
    m2 = re.search(r'([a-zA-Z]+)\s*[-_ ]\s*(\d{4})', dec, re.I)
    if m2:
        mo_str, yr_str = m2.groups()
        mo_num = MONTH_MAP.get(mo_str.lower().strip())
        if mo_num:
            return datetime(int(yr_str), mo_num, 1)

    return None


def fetch_portfolio_catalog(session):
    print("[1/3] Loading Tata Mutual Fund portfolio page...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Referer': 'https://www.tatamutualfund.com/'
    }
    r = session.get(PAGE_URL, headers=headers, timeout=30)
    r.raise_for_status()

    print("[2/3] Extracting Monthly Portfolio URLs from HTML...")
    links = set(re.findall(r'https?://(?:betacms\.)?tatamutualfund\.com/system/files/[^\s"\'\\<>,]+', r.text))
    print(f"Total raw links found on page: {len(links)}")

    monthly_files = {}

    for link in links:
        dec = urllib.parse.unquote(link)
        dec_lower = dec.lower()

        # Must be monthly portfolio and excel file
        if not (dec_lower.endswith('.xlsx') or dec_lower.endswith('.xls')):
            continue

        if ('weekly' in dec_lower or 'fortnightly' in dec_lower or 'aaum' in dec_lower or 
            'debt' in dec_lower or 'segregated' in dec_lower):
            continue

        if 'monthly' not in dec_lower and 'portfolio' not in dec_lower:
            continue

        dt = parse_date_from_filename(dec)
        if dt and (START_DATE <= dt <= END_DATE):
            # Prefer xlsx or latest version if duplicates
            key = (dt.year, dt.month)
            if key not in monthly_files or '.xlsx' in link:
                monthly_files[key] = (dt, link)

    target_list = sorted(monthly_files.values(), key=lambda x: x[0])
    return target_list

# ==============================================================================
# MAIN DOWNLOAD PIPELINE
# ==============================================================================

def run_download():
    print("=" * 70)
    print("TATA MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
    print(f"Target Date Range: {START_DATE.strftime('%b %Y')} to {END_DATE.strftime('%b %Y')}")
    print(f"Raw Output Folder: {RAW_FOLDER}")
    print("=" * 70)

    session = requests.Session(impersonate='chrome124')
    catalog = fetch_portfolio_catalog(session)
    print(f"\n[3/3] Found {len(catalog)} monthly files matching target date range (Oct 2024 - Aug 2026).")

    downloaded = 0
    skipped = 0
    failed = 0

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Referer': PAGE_URL
    }

    for dt, url in catalog:
        month_label = dt.strftime("%b %Y")
        y = dt.year
        m = dt.month

        target_dir = RAW_FOLDER / str(y) / f"{m:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = os.path.basename(urllib.parse.unquote(url.split('?')[0]))
        target_file = target_dir / filename

        if target_file.exists() and target_file.stat().st_size > 10000:
            print(f"  [SKIPPED] {month_label}: {filename} (Already exists, size: {target_file.stat().st_size:,} bytes)")
            skipped += 1
            continue

        print(f"  [DOWNLOADING] {month_label} -> {filename} ...", end="", flush=True)

        success = False
        for attempt in range(1, 4):
            try:
                r = session.get(url, headers=headers, timeout=60)
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(target_file, "wb") as f:
                        f.write(r.content)
                    print(f" DONE ({len(r.content):,} bytes)")
                    downloaded += 1
                    success = True
                    break
                else:
                    print(f" [Retry {attempt}: status {r.status_code}]", end="", flush=True)
                    time.sleep(2)
            except Exception as e:
                print(f" [Retry {attempt}: {e}]", end="", flush=True)
                time.sleep(2)

        if not success:
            print(" FAILED")
            failed += 1

    print("\n" + "=" * 70)
    print("DOWNLOAD SUMMARY:")
    print(f"  Total target months: {len(catalog)}")
    print(f"  Newly downloaded:    {downloaded}")
    print(f"  Already existed:     {skipped}")
    print(f"  Failed:              {failed}")
    print("=" * 70)

if __name__ == "__main__":
    run_download()
