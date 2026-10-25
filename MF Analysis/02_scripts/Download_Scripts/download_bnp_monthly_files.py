"""
Download script for BNP MF (Baroda BNP Paribas Mutual Fund) monthly portfolio files.
Downloads all available consolidated monthly portfolio files from:
https://www.barodabnpparibasmf.in/downloads/monthly-portfolio-scheme

Target files: ONLY 'All Funds' consolidated workbooks (e.g. BOBBNPMF_Monthly_Portfolio_*.xls).
Saves files to:
01_raw_files/BNP_MF/<YYYY>/<MM>/
"""

import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "BNP_MF"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.barodabnpparibasmf.in/"
PAGE_URL = f"{BASE_URL}downloads/monthly-portfolio-scheme"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
}

# Known monthly portfolio all-funds disclosures for October 2024 through September 2026
KNOWN_FILES = [
    {"year": "2024", "month": "10", "filename": "BOBBNPMF_Monthly_Portfolio_31-10-2024_New_9540.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-10-2024_New_9540.xls"},
    {"year": "2024", "month": "11", "filename": "BOBBNPMF_Monthly-Portfolio_30-11-2024_10005.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly-Portfolio_30-11-2024_10005.xls"},
    {"year": "2024", "month": "12", "filename": "BOBBNPMF_Monthly_Portfolio_31-12-2024_10443.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-12-2024_10443.xls"},
    {"year": "2025", "month": "01", "filename": "BOBBNPMF_Monthly_Portfolio_31-01-2025_10928.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-01-2025_10928.xls"},
    {"year": "2025", "month": "02", "filename": "BOBBNPMF_Monthly_Portfolio_28-02-2025_11393.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_28-02-2025_11393.xls"},
    {"year": "2025", "month": "03", "filename": "BOBBNPMF_Monthly_Portfolio_31-03-2025_11814.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-03-2025_11814.xls"},
    {"year": "2025", "month": "04", "filename": "BOBBNPMF_Monthly_Portfolio_30-04-2025_12282.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_30-04-2025_12282.xls"},
    {"year": "2025", "month": "05", "filename": "BOBBNPMF_Monthly-Portfolio_31-05-2025_12730.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly-Portfolio_31-05-2025_12730.xls"},
    {"year": "2025", "month": "06", "filename": "BOBBNPMF_Monthly_Portfolio_30-06-2025_13252.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_30-06-2025_13252.xls"},
    {"year": "2025", "month": "07", "filename": "BOBBNPMF_Monthly_Portfolio_31-07-2025_13732.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-07-2025_13732.xls"},
    {"year": "2025", "month": "08", "filename": "BOBBNPMF_Monthly_Portfolio_31-08-2025_14178.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-08-2025_14178.xls"},
    {"year": "2025", "month": "09", "filename": "BOBBNPMF_Monthly_Portfolio_30-09-2025_14667.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_30-09-2025_14667.xls"},
    {"year": "2025", "month": "10", "filename": "BOBBNPMF_Monthly_Portfolio_31-10-2025_15324.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-10-2025_15324.xls"},
    {"year": "2025", "month": "11", "filename": "BOBBNPMF_Monthly_Portfolio_30-11-2025_15662.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_30-11-2025_15662.xls"},
    {"year": "2025", "month": "12", "filename": "BOBBNPMF_Monthly_Portfolio_31-12-2025_16137.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-12-2025_16137.xls"},
    {"year": "2026", "month": "01", "filename": "BOBBNPMF_Monthly_Portfolio_31-01-2026_16625.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-01-2026_16625.xls"},
    {"year": "2026", "month": "02", "filename": "BOBBNPMF_Monthly_Portfolio_28-02-2026_17113.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_28-02-2026_17113.xls"},
    {"year": "2026", "month": "03", "filename": "BOBBNPMF_Monthly_Portfolio_31-03-2026_17568.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-03-2026_17568.xls"},
    {"year": "2026", "month": "04", "filename": "BOBBNPMF_Monthly_Portfolio_30-04-2026_18070.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_30-04-2026_18070.xls"},
    {"year": "2026", "month": "05", "filename": "BOBBNPMF_Monthly_Portfolio_31-05-2026_18534.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-05-2026_18534.xls"},
    {"year": "2026", "month": "06", "filename": "BOBBNPMF_Monthly_Portfolio_30-06-2026_18982.xlsx", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_30-06-2026_18982.xlsx"},
    {"year": "2026", "month": "07", "filename": "BOBBNPMF_Monthly_Portfolio_31-07-2026_19490.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-07-2026_19490.xls"},
    {"year": "2026", "month": "08", "filename": "BOBBNPMF_Monthly_Portfolio_31-08-2026_19961.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_31-08-2026_19961.xls"},
    {"year": "2026", "month": "09", "filename": "BOBBNPMF_Monthly_Portfolio_30-09-2026_20376.xls", "url": "https://www.barodabnpparibasmf.in/assets/download_documents/BOBBNPMF_Monthly_Portfolio_30-09-2026_20376.xls"},
]


def download_file(url, dest_path):
    if dest_path.exists() and dest_path.stat().st_size > 100000:
        print(f"  [EXISTS] {dest_path.name} ({dest_path.stat().st_size:,} bytes)")
        return True
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [DOWNLOADING] {url} -> {dest_path.name}...")
    req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            content = resp.read()
            with open(dest_path, "wb") as out:
                out.write(content)
        print(f"  [OK] Saved: {len(content):,} bytes")
        return True
    except Exception as e:
        print(f"  [ERROR] Download failed: {e}")
        return False


def discover_live_all_funds():
    discovered = []
    try:
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

        html = opener.open(urllib.request.Request(PAGE_URL, headers=HEADERS), timeout=15).read().decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        cat_input = soup.find("input", {"name": "category"})
        if not cat_input:
            return discovered
        category = cat_input["value"]
        post_url = f"{BASE_URL}ajax-load-more-documents-new"

        def get_csrf():
            for c in cj:
                if c.name == "csrf_cookie_name":
                    return c.value
            return None

        # Check latest months in current and previous year
        now_yr = 2026
        for yr in [now_yr, now_yr - 1]:
            for mo in range(1, 13):
                csrf = get_csrf()
                data = {
                    "csrf_test_name": csrf,
                    "cnt": "48",
                    "pagination": "0",
                    "send_category": category,
                    "send_year": str(yr),
                    "send_month": str(mo),
                    "remaining_cnt": "0",
                }
                req = urllib.request.Request(post_url, data=urllib.parse.urlencode(data).encode("utf-8"), headers=HEADERS)
                with opener.open(req, timeout=12) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                soup_m = BeautifulSoup(res.get("data", ""), "html.parser")
                for a in soup_m.find_all("a", href=True):
                    href = a["href"]
                    fname = href.split("/")[-1]
                    if ("monthly_portfolio" in fname.lower() or "monthly-portfolio" in fname.lower()) and not re.match(r"^(?:T0|YR)", fname, re.I):
                        m_dt = re.search(r'(\d{2})[-_](\d{2})[-_](\d{4})', fname)
                        if m_dt:
                            d, m, y = m_dt.groups()
                            discovered.append({
                                "year": y,
                                "month": m,
                                "filename": fname,
                                "url": href,
                            })
                        break
    except Exception as e:
        print(f"[WARN] Live discovery exception: {e}")
    return discovered


def main():
    print("=" * 80)
    print("BNP MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER (ALL FUNDS CONSOLIDATED)")
    print(f"Destination: {RAW_FOLDER}")
    print("=" * 80)

    all_dict = {}
    for item in KNOWN_FILES:
        key = (item["year"], item["month"])
        all_dict[key] = item

    # Run dynamic discovery to capture any new months
    live_items = discover_live_all_funds()
    for item in live_items:
        key = (item["year"], item["month"])
        all_dict[key] = item

    items = sorted(all_dict.values(), key=lambda x: (x["year"], x["month"]))
    print(f"Total monthly consolidated workbooks to download: {len(items)}")

    success_count = 0
    for item in items:
        yr = item["year"]
        mo = item["month"]
        url = item["url"]
        fname = item["filename"]
        dest_path = RAW_FOLDER / yr / mo / fname
        if download_file(url, dest_path):
            success_count += 1
        time.sleep(0.3)

    print("=" * 80)
    print(f"DOWNLOAD COMPLETE: {success_count}/{len(items)} files ready.")
    print("=" * 80)


if __name__ == "__main__":
    main()
