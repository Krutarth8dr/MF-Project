"""
Taurus Mutual Fund - Monthly Portfolio Downloader
Downloads monthly portfolio files for 7 target equity funds from October 2024 to August 2026 (23 months).
Files are saved to: 01_raw_files/TAURUS/<YYYY>/<MM>/
"""

import os
import sys
import time
import urllib.parse
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import urllib3

# Suppress insecure HTTPS warnings if needed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "TAURUS"
BASE_URL = "https://taurusmutualfund.com"
PORTFOLIO_PAGE_URL = f"{BASE_URL}/monthly-portfolio"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Drupal Term IDs for Years
YEAR_IDS = {
    "2024": "514",
    "2025": "558",
    "2026": "567"
}

# Drupal Term IDs for Months
MONTH_IDS = {
    "01": ("January", "281"),
    "02": ("February", "282"),
    "03": ("March", "283"),
    "04": ("April", "284"),
    "05": ("May", "285"),
    "06": ("June", "286"),
    "07": ("July", "287"),
    "08": ("August", "288"),
    "09": ("September", "289"),
    "10": ("October", "290"),
    "11": ("November", "291"),
    "12": ("December", "292")
}

# 23 Target Months: October 2024 to August 2026
TARGET_MONTHS = [
    # 2024
    ("2024", "10"), ("2024", "11"), ("2024", "12"),
    # 2025
    ("2025", "01"), ("2025", "02"), ("2025", "03"), ("2025", "04"), ("2025", "05"), ("2025", "06"),
    ("2025", "07"), ("2025", "08"), ("2025", "09"), ("2025", "10"), ("2025", "11"), ("2025", "12"),
    # 2026
    ("2026", "01"), ("2026", "02"), ("2026", "03"), ("2026", "04"), ("2026", "05"), ("2026", "06"),
    ("2026", "07"), ("2026", "08")
]

# 7 Target Funds Config
TARGET_FUNDS_PATTERNS = {
    "Taurus Flexi Cap Fund": ["flexi", "tss"],
    "Taurus Large Cap Fund": ["large", "tbf", "bonanza"],
    "Taurus Infrastructure Fund": ["infrastructure", "tisf"],
    "Taurus ELSS Tax Saver Fund": ["elss", "tax", "tsf", "taxshield"],
    "Taurus Mid Cap Fund": ["mid", "tdf", "discovery"],
    "Taurus Ethical Fund": ["ethical", "tef"],
    "Taurus Banking and Financial Services": ["banking", "financial", "fin_serv", "tbfs"]
}


def download_all_taurus_files():
    print("=" * 75)
    print("TAURUS MUTUAL FUND - PORTFOLIO DOWNLOADER")
    print(f"Target Directory: {RAW_DIR}")
    print(f"Target Months:    {len(TARGET_MONTHS)} (Oct 2024 to Aug 2026)")
    print(f"Target Funds:     {len(TARGET_FUNDS_PATTERNS)} funds")
    print("=" * 75)

    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    for year, month in TARGET_MONTHS:
        ym = f"{year}-{month}"
        month_name, month_id = MONTH_IDS[month]
        year_id = YEAR_IDS[year]

        dest_dir = RAW_DIR / year / month
        dest_dir.mkdir(parents=True, exist_ok=True)

        url = f"{PORTFOLIO_PAGE_URL}?field_monthly_portfolio_target_id={year_id}&field_month_target_id={month_id}"
        print(f"\n[{ym} - {month_name} {year}] Querying page: {url}")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=25, verify=False)
            if resp.status_code != 200:
                print(f"  [ERROR] Page returned status {resp.status_code}")
                failed_count += 1
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            excel_links = []
            for a in soup.find_all("a"):
                href = a.get("href", "")
                if any(href.lower().endswith(ext) for ext in [".xlsx", ".xls", ".csv"]):
                    txt = a.text.strip()
                    full_url = urllib.parse.urljoin(BASE_URL, href)
                    excel_links.append({"text": txt, "url": full_url, "href": href})

            matched_this_month = 0
            for item in excel_links:
                txt = item["text"]
                file_url = item["url"]
                raw_filename = os.path.basename(urllib.parse.unquote(file_url))

                # Check if this file belongs to one of our 7 target funds
                check_str = (txt + " " + raw_filename).lower()
                is_target = False
                target_fund_name = None
                for cname, patterns in TARGET_FUNDS_PATTERNS.items():
                    if any(p in check_str for p in patterns):
                        is_target = True
                        target_fund_name = cname
                        break

                if not is_target:
                    continue

                matched_this_month += 1
                dest_file = dest_dir / raw_filename

                if dest_file.exists() and dest_file.stat().st_size > 5000:
                    print(f"  [SKIP] {target_fund_name} -> {raw_filename} ({dest_file.stat().st_size:,} bytes)")
                    skipped_count += 1
                    continue

                print(f"  [DOWNLOADING] {target_fund_name} -> {raw_filename}...")
                try:
                    f_resp = requests.get(file_url, headers=HEADERS, timeout=30, verify=False)
                    if f_resp.status_code == 200 and len(f_resp.content) > 5000:
                        with open(dest_file, "wb") as f:
                            f.write(f_resp.content)
                        print(f"    [OK] Saved ({len(f_resp.content):,} bytes)")
                        downloaded_count += 1
                    else:
                        print(f"    [ERROR] Status: {f_resp.status_code}, Length: {len(f_resp.content)}")
                        failed_count += 1
                except Exception as e:
                    print(f"    [ERROR] Failed to download {file_url}: {e}")
                    failed_count += 1

            print(f"  Matched {matched_this_month}/{len(TARGET_FUNDS_PATTERNS)} funds for {ym}")

        except Exception as e:
            print(f"  [ERROR] Failed to fetch month page: {e}")
            failed_count += 1

        time.sleep(0.4)

    print("\n" + "=" * 75)
    print(f"Download Summary: {downloaded_count} downloaded, {skipped_count} skipped, {failed_count} failed")
    print(f"Total Expected Files: {len(TARGET_MONTHS) * len(TARGET_FUNDS_PATTERNS)} (23 months x 7 funds = 161 files)")
    print("=" * 75)


if __name__ == "__main__":
    download_all_taurus_files()
