"""
Download monthly portfolio disclosure files for The Wealth Company Mutual Fund (The Wealth Company MF).

Source:
    Website: https://www.wealthcompanyamc.in/literature-forms/portfolio-documents/monthly/
    Uploads: https://www.wealthcompanyamc.in/uploads/...

Target Funds (8 funds):
    1. The Wealth Company Multi Cap Fund
    2. The Wealth Company Mid Cap Fund
    3. The Wealth Company Large & Mid Cap Fund
    4. The Wealth Company Flexicap Fund
    5. The Wealth Company Multi Asset Allocation Fund
    6. The Wealth Company Ethical Fund
    7. The Wealth Company Balanced Advantage Fund
    8. The Wealth Company Small Cap Fund

Target Period:
    Inception (October 2025) to September 2026.

Stores raw files in:
    01_raw_files/The_Wealth_Company_MF/<YYYY>/<MM>/<FundCode>_<OriginalFilename>
"""

import os
import sys
import re
import json
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
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "The_Wealth_Company_MF"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.wealthcompanyamc.in/literature-forms/portfolio-documents/monthly/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.wealthcompanyamc.in/literature-forms/portfolio-documents/monthly/",
}

TARGET_FUNDS = {
    "The Wealth Company Multi Cap Fund": "Multi_Cap",
    "The Wealth Company Mid Cap Fund": "Mid_Cap",
    "The Wealth Company Large & Mid Cap Fund": "Large_Mid_Cap",
    "The Wealth Company Flexicap Fund": "Flexicap",
    "The Wealth Company Multi Asset Allocation Fund": "Multi_Asset",
    "The Wealth Company Ethical Fund": "Ethical",
    "The Wealth Company Balanced Advantage Fund": "Balanced_Advantage",
    "The Wealth Company Small Cap Fund": "Small_Cap",
}

MONTHS_MAP = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12
}


def match_target_fund(name_or_url):
    s = name_or_url.lower().replace("_", " ").replace("-", " ").replace("&", "and")
    s = re.sub(r'\s+', ' ', s)

    if "multi cap" in s and "large" not in s:
        return "The Wealth Company Multi Cap Fund"
    elif "mid cap" in s and "large" not in s and "multi" not in s:
        return "The Wealth Company Mid Cap Fund"
    elif "large" in s and "mid" in s:
        return "The Wealth Company Large & Mid Cap Fund"
    elif "flexi" in s:
        return "The Wealth Company Flexicap Fund"
    elif "multi asset" in s:
        return "The Wealth Company Multi Asset Allocation Fund"
    elif "ethical" in s:
        return "The Wealth Company Ethical Fund"
    elif "balanced advantage" in s:
        return "The Wealth Company Balanced Advantage Fund"
    elif "small cap" in s:
        return "The Wealth Company Small Cap Fund"
    return None


def fetch_all_downloads_metadata():
    """Scrapes the paginated React payload to discover all portfolio document links."""
    session = requests.Session()
    session.headers.update(HEADERS)

    discovered = []
    for page in range(1, 10):
        url = f"{BASE_URL}?page={page}"
        try:
            r = session.get(url, timeout=25)
            if r.status_code != 200:
                break
            m = re.search(r'\\"downloads\\":\[(.*?)\](?:,\\"pagination\\"|\])', r.text)
            if not m:
                break
            raw_arr = "[" + m.group(1) + "]"
            clean_json_str = raw_arr.replace('\\"', '"').replace('\\\\', '\\')
            items = json.loads(clean_json_str)
            if not items:
                break
            for item in items:
                name = item.get("name", "").strip()
                att = item.get("attachment") or {}
                rel_url = att.get("url") or ""
                if not rel_url:
                    continue
                full_url = f"https://www.wealthcompanyamc.in{rel_url}"

                fund_canonical = match_target_fund(name) or match_target_fund(rel_url)
                if not fund_canonical:
                    continue

                # Determine month and year
                # e.g. "Sep 30, 2026", "October 31,2025", "November 30, 2025"
                m_date = re.search(r'([A-Za-z]+)\s*(\d{1,2})?\s*,?\s*(\d{4})', name)
                ym = None
                if m_date:
                    m_str = m_date.group(1).lower()
                    year = int(m_date.group(3))
                    if m_str in MONTHS_MAP:
                        ym = f"{year}-{MONTHS_MAP[m_str]:02d}"

                if not ym and item.get("uploadDate"):
                    ym = item["uploadDate"][:7]

                if ym:
                    discovered.append({
                        "ym": ym,
                        "year": ym[:4],
                        "month": ym[5:7],
                        "fund": fund_canonical,
                        "name": name,
                        "url": full_url,
                        "filename": rel_url.split("/")[-1],
                    })
        except Exception as e:
            print(f"Error scraping page {page}: {e}")
            break

    # Deduplicate by (ym, fund)
    unique_map = {}
    for item in discovered:
        key = (item["ym"], item["fund"])
        if key not in unique_map:
            unique_map[key] = item

    return sorted(list(unique_map.values()), key=lambda x: (x["ym"], x["fund"]))


def download_single_file(item, session=None):
    """Download single portfolio file."""
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    year = item["year"]
    month = item["month"]
    fund_code = TARGET_FUNDS[item["fund"]]
    dest_filename = f"{fund_code}_{item['filename']}"

    target_dir = RAW_DIR / year / month
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / dest_filename

    if target_path.exists() and target_path.stat().st_size > 1024:
        return {
            "year": year,
            "month": month,
            "fund": item["fund"],
            "path": target_path,
            "size": target_path.stat().st_size,
            "status": "EXISTS",
            "url": item["url"],
        }

    for attempt in range(1, 4):
        try:
            resp = session.get(item["url"], headers=HEADERS, timeout=45)
            if resp.status_code == 200 and len(resp.content) > 1024:
                with open(target_path, "wb") as f:
                    f.write(resp.content)
                return {
                    "year": year,
                    "month": month,
                    "fund": item["fund"],
                    "path": target_path,
                    "size": len(resp.content),
                    "status": "DOWNLOADED",
                    "url": item["url"],
                }
            else:
                time.sleep(2 * attempt)
        except Exception as e:
            if attempt == 3:
                return {
                    "year": year,
                    "month": month,
                    "fund": item["fund"],
                    "path": target_path,
                    "size": 0,
                    "status": f"FAILED: {e}",
                    "url": item["url"],
                }
            time.sleep(2 * attempt)

    return {
        "year": year,
        "month": month,
        "fund": item["fund"],
        "path": target_path,
        "size": 0,
        "status": "FAILED: Non-200 or empty",
        "url": item["url"],
    }


def download_all_wealth_company_files(max_workers=5):
    """Download all The Wealth Company MF target fund portfolio files."""
    print("=" * 80)
    print("The Wealth Company MF Monthly Portfolio Downloader")
    print("=" * 80)

    items = fetch_all_downloads_metadata()
    print(f"Discovered {len(items)} files across {len(set(x['ym'] for x in items))} months.")
    print(f"Destination: {RAW_DIR}")

    results = []
    with requests.Session() as session:
        session.headers.update(HEADERS)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(download_single_file, item, session): item
                for item in items
            }

            for fut in as_completed(futures):
                res = fut.result()
                results.append(res)
                status_symbol = "✓" if res["status"] in ("DOWNLOADED", "EXISTS") else "✗"
                print(
                    f"[{status_symbol}] {res['year']}-{res['month']} | {res['fund']}: "
                    f"{res['status']} ({res['size'] / 1024:.1f} KB) -> {res['path'].name}"
                )

    success_cnt = sum(1 for r in results if r["status"] in ("DOWNLOADED", "EXISTS"))
    print("=" * 80)
    print(f"Download Summary: {success_cnt}/{len(items)} files available.")
    print("=" * 80)
    return success_cnt == len(items)


if __name__ == "__main__":
    success = download_all_wealth_company_files()
    sys.exit(0 if success else 1)
