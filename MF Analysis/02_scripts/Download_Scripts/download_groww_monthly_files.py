import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "GROWW"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

PAGE_URL = "https://www.growwmf.in/statutory-disclosure/portfolio"

START_DATE = datetime(2024, 10, 1)
END_DATE = datetime(2026, 8, 31)

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": PAGE_URL
}


def parse_date_robust(text):
    """
    Parses date string into a datetime object.
    Supports formats like '31-AUG-2026', 'May 31, 2026', 'Nov_30_2024', 'Oct 2024'.
    """
    if not text:
        return None
    s = str(text).replace(",", " ").replace("_", " ")
    # Format: 31-AUG-2026 or 31 Aug 2026
    m = re.search(r'(\d{1,2})\s*[-/ ]\s*([A-Za-z]+)\s*[-/ ]\s*(\d{4})', s)
    if m:
        day, mon_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        mon = MONTH_MAP.get(mon_name[:3])
        if mon:
            return datetime(year, mon, min(day, 28))
    # Format: Aug 31 2026 or August 31 2026
    m2 = re.search(r'([A-Za-z]+)\s*[-/ ]\s*(\d{1,2})\s*[-/ ]\s*(\d{4})', s)
    if m2:
        mon_name, day, year = m2.group(1).lower(), int(m2.group(2)), int(m2.group(3))
        mon = MONTH_MAP.get(mon_name[:3])
        if mon:
            return datetime(year, mon, min(day, 28))
    # Format: Oct 2024
    m3 = re.search(r'([A-Za-z]+)\s*[-/ ]\s*(\d{4})', s)
    if m3:
        mon_name, year = m3.group(1).lower(), int(m3.group(2))
        mon = MONTH_MAP.get(mon_name[:3])
        if mon:
            return datetime(year, mon, 1)
    return None


def fetch_portfolio_catalog():
    """
    Fetches statutory disclosure page and extracts all Monthly Portfolio files.
    """
    print(f"[1/3] Loading Groww MF portfolio page: {PAGE_URL}")
    resp = requests.get(PAGE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    next_data_tag = soup.find("script", id="__NEXT_DATA__")
    if not next_data_tag:
        raise ValueError("Could not find __NEXT_DATA__ in Groww MF portfolio page.")

    data = json.loads(next_data_tag.string)
    page_props = data.get("props", {}).get("pageProps", {})
    files_data = page_props.get("filesData", {})
    folders = files_data.get("folders", [])

    portfolio_folder = None
    for f in folders:
        if "portfolio" in f.get("name", "").strip().lower():
            portfolio_folder = f
            break

    if not portfolio_folder:
        raise ValueError("Could not find 'Portfolio' folder in filesData hierarchy.")

    catalog = []
    subfolders = portfolio_folder.get("folders", [])

    for sub in subfolders:
        # Process files in year folder
        for file_info in sub.get("files", []):
            fname = file_info.get("name", "")
            purl = file_info.get("publicUrl", "")
            if "monthly" in fname.lower() and fname.lower().endswith(('.xls', '.xlsx')):
                dt = parse_date_robust(fname)
                if dt and (START_DATE <= dt <= END_DATE):
                    catalog.append((dt, fname, purl))

        # Process any sub-subfolders if present
        for sub_sub in sub.get("folders", []):
            for file_info in sub_sub.get("files", []):
                fname = file_info.get("name", "")
                purl = file_info.get("publicUrl", "")
                if "monthly" in fname.lower() and fname.lower().endswith(('.xls', '.xlsx')):
                    dt = parse_date_robust(fname)
                    if dt and (START_DATE <= dt <= END_DATE):
                        catalog.append((dt, fname, purl))

    # Sort catalog chronologically
    catalog.sort(key=lambda x: x[0])
    return catalog


def run_download():
    print("=" * 70)
    print("GROWW MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
    print(f"Target Date Range: {START_DATE.strftime('%b %Y')} to {END_DATE.strftime('%b %Y')}")
    print(f"Raw Output Folder: {RAW_FOLDER}")
    print("=" * 70)

    catalog = fetch_portfolio_catalog()
    print(f"\n[2/3] Found {len(catalog)} monthly files in target date range (Oct 2024 - Aug 2026).")

    downloaded = 0
    skipped = 0
    failed = 0

    print("\n[3/3] Downloading monthly files...")
    for dt, fname, url in catalog:
        year_str = str(dt.year)
        month_str = f"{dt.month:02d}"
        month_label = dt.strftime("%b %Y")

        target_dir = RAW_FOLDER / year_str / month_str
        target_dir.mkdir(parents=True, exist_ok=True)

        clean_filename = os.path.basename(url.split('?')[0])
        clean_filename = requests.utils.unquote(clean_filename)
        target_file = target_dir / clean_filename

        if target_file.exists() and target_file.stat().st_size > 10000:
            print(f"  [SKIPPED] {month_label}: {clean_filename} ({target_file.stat().st_size:,} bytes)")
            skipped += 1
            continue

        print(f"  [DOWNLOADING] {month_label} -> {clean_filename} ...", end="", flush=True)
        success = False
        for attempt in range(1, 4):
            try:
                r = requests.get(url, headers=HEADERS, timeout=60)
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
