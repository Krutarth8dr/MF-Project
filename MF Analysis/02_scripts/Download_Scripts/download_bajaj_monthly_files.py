import os
import re
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from curl_cffi import requests

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "BAJAJ_FINSERV"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

PAGE_URL = "https://www.bajajamc.com/downloads?portfolio="
AJAX_URL = "https://www.bajajamc.com/wp-admin/admin-ajax.php"

START_DATE = datetime(2024, 10, 1)
END_DATE = datetime(2026, 8, 31)

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}

SECTION_ID = "757"  # Monthly Portfolio Section ID

# ==============================================================================
# CATALOG FETCHING
# ==============================================================================

def fetch_portfolio_catalog(session):
    print("[1/3] Loading Bajaj AMC downloads page to extract session nonce...")
    r = session.get(PAGE_URL, timeout=30)
    r.raise_for_status()

    # Extract nonce
    m = re.search(r'bajaj-downloads-js-js-extra.*?nonce["\']?\s*:\s*["\']([a-f0-9]+)["\']', r.text, re.S)
    if not m:
        m = re.search(r'data-ir-nonce=["\']([a-f0-9]+)["\']', r.text)

    if not m:
        raise ValueError("Failed to extract AJAX nonce from Bajaj AMC downloads page.")

    nonce = m.group(1)
    print(f"Extracted AJAX nonce: {nonce}")

    print("[2/3] Querying AJAX endpoints for Monthly Portfolio (Section 757)...")
    payload_years = {
        'action': 'bajaj_get_filter_options',
        'filter_for': 'years',
        'section_id': SECTION_ID,
        'nonce': nonce
    }
    r_years = session.post(AJAX_URL, data=payload_years, timeout=30)
    years_data = r_years.json()
    years_list = years_data.get('data', {}).get('options', [])
    print(f"Available FY years: {[y['value'] for y in years_list]}")

    target_files = []

    for y_obj in years_list:
        fy_str = y_obj['value']
        payload_months = {
            'action': 'bajaj_get_filter_options',
            'filter_for': 'months',
            'section_id': SECTION_ID,
            'year': fy_str,
            'nonce': nonce
        }
        r_months = session.post(AJAX_URL, data=payload_months, timeout=30)
        months_data = r_months.json()
        months_list = months_data.get('data', {}).get('options', [])

        for m_obj in months_list:
            mo_name = m_obj['value']
            mo_num = MONTH_MAP.get(mo_name.lower().strip())
            if not mo_num:
                continue

            try:
                start_yr = int(fy_str.split('-')[0])
            except Exception:
                continue
            cal_year = start_yr if mo_num >= 4 else start_yr + 1
            dt = datetime(cal_year, mo_num, 1)

            if not (START_DATE <= dt <= END_DATE):
                continue

            payload_dl = {
                'action': 'bajaj_get_downloads',
                'section_id': SECTION_ID,
                'year': fy_str,
                'month': mo_name,
                'nonce': nonce
            }
            r_dl = session.post(AJAX_URL, data=payload_dl, timeout=30)
            dl_json = r_dl.json()
            data_field = dl_json.get('data', {})
            html_content = data_field.get('html', '') if isinstance(data_field, dict) else str(data_field)

            links = re.findall(r'href=["\'](https?://[^\s"\']+)["\']', html_content)
            for link in links:
                if '.xls' in link.lower() or '.xlsx' in link.lower():
                    target_files.append((dt, cal_year, mo_num, link))

    target_files.sort(key=lambda x: x[0])
    return target_files

# ==============================================================================
# MAIN DOWNLOAD PIPELINE
# ==============================================================================

def run_download():
    print("=" * 70)
    print("BAJAJ FINSERV MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
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

    for dt, y, m, url in catalog:
        month_label = dt.strftime("%b %Y")
        target_dir = RAW_FOLDER / str(y) / f"{m:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = os.path.basename(url.split('?')[0])
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
