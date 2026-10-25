"""
Download script for Abakkus MF monthly portfolio files.
Downloads all available monthly portfolio files from:
https://www.abakkusmf.com/statutory-disclosures.html#
Saves files to:
01_raw_files/ABAKKUS_MF/<YYYY>/<MM>/
"""

import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "ABAKKUS_MF"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

DISCLOSURES_URL = "https://www.abakkusmf.com/statutory-disclosures.html"
BASE_URL = "https://www.abakkusmf.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.abakkusmf.com/",
}

# Known monthly portfolio disclosures
KNOWN_FILES = [
    {"year": "2025", "month": "12", "date": "2025-12-31", "url": "https://www.abakkusmf.com/uploads/Abakkus_MF_MONTHLY_PORTFOLIO_31_12_2025_562986311e.xlsx"},
    {"year": "2026", "month": "01", "date": "2026-01-31", "url": "https://www.abakkusmf.com/uploads/Abakkus_MF_Portfolio_31_01_2026_9cd68f430c.xls"},
    {"year": "2026", "month": "02", "date": "2026-02-28", "url": "https://www.abakkusmf.com/uploads/ABK_MF_MONTHLY_PORTFOLIO_February_28_2026_a9bc6bf1b7.xls"},
    {"year": "2026", "month": "03", "date": "2026-03-31", "url": "https://www.abakkusmf.com/uploads/IN_MF_MONTHLY_PORTFOLIO_March_31_2026_eb4d2050b9.xls"},
    {"year": "2026", "month": "04", "date": "2026-04-30", "url": "https://www.abakkusmf.com/uploads/IN_MF_MONTHLY_PORTFOLIO_April_30_2026_48e9b6a58c.xls"},
    {"year": "2026", "month": "05", "date": "2026-05-31", "url": "https://www.abakkusmf.com/uploads/Abakkus_Mutual_Fund_31_05_2026_f7ac956d1d.xls"},
    {"year": "2026", "month": "06", "date": "2026-06-30", "url": "https://www.abakkusmf.com/uploads/Monthly_Portfolio_Jun26_30_Jun_65d7e26b0a.xls"},
    {"year": "2026", "month": "07", "date": "2026-07-31", "url": "https://www.abakkusmf.com/uploads/Final_Monthly_Portfolio_Jul_31_a313e9e6dd.xls"},
    {"year": "2026", "month": "08", "date": "2026-08-31", "url": "https://www.abakkusmf.com/uploads/Portfolio_Aug31_Monthly_a00d994a66.xls"},
    {"year": "2026", "month": "09", "date": "2026-09-30", "url": "https://www.abakkusmf.com/uploads/Final_Monthly_Portolio_Sep30_2026_fd59e57829.xlsx"},
]

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
}


def parse_date_from_url_or_text(text):
    text_clean = str(text).replace("_", " ").replace("-", " ")
    m = re.search(r'(\d{1,2})\s*([A-Za-z]+)\s*(\d{4})', text_clean)
    if m:
        day, mon_str, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        mon = MONTH_MAP.get(mon_str[:3])
        if mon:
            return year, mon
    m2 = re.search(r'([A-Za-z]+)\s*(\d{1,2})\s*(\d{4})', text_clean)
    if m2:
        mon_str, day, year = m2.group(1).lower(), int(m2.group(2)), int(m2.group(3))
        mon = MONTH_MAP.get(mon_str[:3])
        if mon:
            return year, mon
    m3 = re.search(r'([A-Za-z]+)\s*(\d{2,4})', text_clean)
    if m3:
        mon_str, yr_str = m3.group(1).lower(), m3.group(2)
        mon = MONTH_MAP.get(mon_str[:3])
        if mon:
            yr = int("20" + yr_str) if len(yr_str) == 2 else int(yr_str)
            return yr, mon
    return None, None


def discover_online_files():
    found_files = []
    try:
        req = urllib.request.Request(DISCLOSURES_URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        urls = re.findall(r'href=[\'"]([^\'"]*uploads/[^\'"]+\.(?:xlsx|xls))[\'"]', html, re.I)
        for u in set(urls):
            full_u = u if u.startswith("http") else (BASE_URL + ("/" if not u.startswith("/") else "") + u)
            fname = full_u.split("/")[-1]
            if "portfolio" in fname.lower() or "monthly" in fname.lower():
                yr, mo = parse_date_from_url_or_text(fname)
                if yr and mo:
                    found_files.append({
                        "year": f"{yr:04d}",
                        "month": f"{mo:02d}",
                        "date": f"{yr:04d}-{mo:02d}-01",
                        "url": full_u
                    })
    except Exception as e:
        print(f"[WARN] Error fetching live disclosures page: {e}")
    return found_files


def download_file(url, dest_path):
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        print(f"  [EXISTS] {dest_path.name} ({dest_path.stat().st_size} bytes)")
        return True
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [DOWNLOADING] {url} -> {dest_path.name}...")
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            with open(dest_path, "wb") as out:
                out.write(content)
        print(f"  [OK] Saved: {len(content)} bytes")
        return True
    except Exception as e:
        print(f"  [ERROR] Download failed: {e}")
        return False


def main():
    print("=" * 80)
    print("ABAKKUS MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
    print(f"Destination: {RAW_FOLDER}")
    print("=" * 80)

    # Combine known list with dynamically discovered items
    all_files_dict = {}
    for item in KNOWN_FILES:
        key = (item["year"], item["month"])
        all_files_dict[key] = item

    discovered = discover_online_files()
    for item in discovered:
        key = (item["year"], item["month"])
        if key not in all_files_dict:
            all_files_dict[key] = item

    sorted_items = sorted(all_files_dict.values(), key=lambda x: (x["year"], x["month"]))
    print(f"Total months to process: {len(sorted_items)}")

    success_count = 0
    for item in sorted_items:
        yr = item["year"]
        mo = item["month"]
        url = item["url"]
        fname = url.split("/")[-1]
        dest_path = RAW_FOLDER / yr / mo / fname
        if download_file(url, dest_path):
            success_count += 1
        time.sleep(0.5)

    print("=" * 80)
    print(f"DOWNLOAD COMPLETE: {success_count}/{len(sorted_items)} files ready.")
    print("=" * 80)


if __name__ == "__main__":
    main()
