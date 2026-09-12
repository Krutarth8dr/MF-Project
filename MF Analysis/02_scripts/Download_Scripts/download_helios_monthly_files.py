import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
import urllib3
from pathlib import Path

urllib3.disable_warnings()

# ==============================================================================
# SETTINGS & CONFIGURATION
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_BASE_DIR = PROJECT_ROOT / "01_raw_files" / "HELIOS"
RAW_BASE_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOADS_URL = "https://www.heliosmf.in/downloads"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

TARGET_FUNDS = [
    "Helios Small Cap Fund",
    "Helios Mid Cap Fund",
    "Helios Large & Mid Cap Fund",
    "Helios Flexi Cap Fund",
    "Helios Balanced Advantage Fund",
    "Helios Financial Services Fund",
]

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

START_MONTH = "2024-10"
END_MONTH = "2026-08"


def extract_helios_monthly_links():
    print(f"Fetching downloads page: {DOWNLOADS_URL}...")
    resp = requests.get(DOWNLOADS_URL, headers=HEADERS, verify=False, timeout=30)
    if resp.status_code != 200:
        print(f"ERROR: Failed to fetch downloads page (Status: {resp.status_code})")
        sys.exit(1)

    soup = BeautifulSoup(resp.text, "html.parser")
    all_links = []

    for tf in TARGET_FUNDS:
        for cat_item in soup.find_all("div", class_=lambda c: c and "hlx-dl-cat-item" in c):
            heading = cat_item.find(["h4", "h3", "h2", "button", "span"], class_=lambda c: c and ("hlx-dl-heading" in c or "hlx-dl-cat-trigger" in c))
            if heading and tf.lower() in heading.get_text(strip=True).lower():
                parent_text = " ".join([p.get_text(strip=True) for p in cat_item.parents if hasattr(p, "get_text")])
                if "monthly portfolio" not in parent_text.lower():
                    continue

                links = cat_item.find_all("a", href=lambda href: href and (".xls" in href.lower() or ".xlsx" in href.lower()))
                for a in links:
                    text = a.get_text(strip=True)
                    href = a["href"]
                    if not href.startswith("http"):
                        href = "https://www.heliosmf.in" + href

                    if "half-yearly" in href.lower() or "half_yearly" in href.lower() or "fortnightly" in href.lower():
                        continue

                    m = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})", text, re.I)
                    if not m:
                        m = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)[-_](\d{4})", href, re.I)
                    if not m:
                        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?[-_](january|february|march|april|may|june|july|august|september|october|november|december)[-_](\d{4})", href, re.I)
                        if m:
                            m_tuple = (m.group(2), m.group(3))
                        else:
                            m_tuple = None
                    else:
                        m_tuple = (m.group(1), m.group(2))

                    if m_tuple:
                        mo_name, yr_str = m_tuple[0], m_tuple[1]
                        mo_num = MONTH_MAP.get(mo_name.lower())
                        yr = int(yr_str)
                        month_key = f"{yr:04d}-{mo_num:02d}"

                        if START_MONTH <= month_key <= END_MONTH:
                            # Avoid duplicates
                            if not any(l["fund_name"] == tf and l["month"] == month_key for l in all_links):
                                all_links.append({
                                    "fund_name": tf,
                                    "month": month_key,
                                    "year": yr,
                                    "month_num": mo_num,
                                    "url": href,
                                    "link_text": text
                                })

    return all_links


def download_helios_files():
    print("=" * 75)
    print("HELIOS MUTUAL FUND - PORTFOLIO DOWNLOADER")
    print(f"Target Base Directory: {RAW_BASE_DIR}")
    print(f"Target Date Range:     {START_MONTH} to {END_MONTH}")
    print(f"Target Funds:          {len(TARGET_FUNDS)} funds")
    print("=" * 75)

    links = extract_helios_monthly_links()
    links.sort(key=lambda x: (x["month"], x["fund_name"]))

    print(f"\nFound {len(links)} portfolio files to download across target date range.\n")

    downloaded = 0
    skipped = 0
    failed = 0

    for idx, item in enumerate(links, 1):
        fund_name = item["fund_name"]
        month_key = item["month"]
        yr = item["year"]
        mo_num = item["month_num"]
        url = item["url"]

        month_dir = RAW_BASE_DIR / str(yr) / f"{mo_num:02d}"
        month_dir.mkdir(parents=True, exist_ok=True)

        url_filename = url.split("/")[-1].split("?")[0]
        ext = ".xls" if url_filename.lower().endswith(".xls") else ".xlsx"
        # Standardize local filename
        local_filename = f"{fund_name.replace(' ', '_').replace('&', 'and')}_{yr}_{mo_num:02d}{ext}"
        local_filepath = month_dir / local_filename

        if local_filepath.exists() and local_filepath.stat().st_size > 1000:
            print(f"  [{idx}/{len(links)}] [SKIP] {month_key} | {fund_name} -> {local_filename} ({local_filepath.stat().st_size:,} bytes)")
            skipped += 1
            continue

        print(f"  [{idx}/{len(links)}] [DOWNLOADING] {month_key} | {fund_name} -> {url}...")
        try:
            resp = requests.get(url, headers=HEADERS, verify=False, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 1000:
                local_filepath.write_bytes(resp.content)
                print(f"    [OK] Saved ({len(resp.content):,} bytes)")
                downloaded += 1
            else:
                print(f"    [FAIL] Status: {resp.status_code}, Length: {len(resp.content)}")
                failed += 1
        except Exception as e:
            print(f"    [ERROR] {e}")
            failed += 1

        time.sleep(0.3)

    print("\n" + "=" * 75)
    print(f"Download Summary: {downloaded} downloaded, {skipped} skipped, {failed} failed")
    print(f"Total Files Expected: {len(links)}")
    print("=" * 75)


if __name__ == "__main__":
    download_helios_files()
