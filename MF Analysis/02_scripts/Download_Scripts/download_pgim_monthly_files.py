"""
Download monthly portfolio disclosure files for PGIM Mutual Fund (PGIM MF).

Source:
    Website: http://pgimindia.com/mutual-funds/disclosures/Portfolios/Monthly-Portfolio
    API Endpoint: https://www.pgimindia.com/api/v1/brochure/published/disclosure
    Payload: {"headerId": 2, "sectionId": "SECTION_747960037"}

Target Funds (12 funds):
    1. PGIM India Healthcare Fund (launched Dec 2024: 22 months)
    2. PGIM India Small Cap Fund (24 months)
    3. PGIM India Multi Cap Fund (24 months)
    4. PGIM India Multi Asset Allocation Fund (launched Nov 2025: 11 months)
    5. PGIM India Midcap Fund (24 months)
    6. PGIM India Large Cap Fund (24 months)
    7. PGIM India Large and Midcap Fund (24 months)
    8. PGIM India Flexi Cap Fund (24 months)
    9. PGIM India Equity Savings Fund (24 months)
    10. PGIM India ELSS Tax Saver Fund (24 months)
    11. PGIM India Balanced Advantage Fund (24 months)
    12. PGIM India Aggressive Hybrid Equity Fund (launched Jun 2025: 16 months)

Target Period:
    October 2024 to September 2026 (24 months or from fund inception).

Note:
    - Files are served as .xlsx or .xlsb directly from PGIM brochure asset storage.
    - Stores raw files in:
      01_raw_files/PGIM_MF/<YYYY>/<MM>/<SchemeSlug>_<OriginalFilename>
"""

import os
import sys
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "PGIM_MF"
RAW_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "https://www.pgimindia.com/api/v1/brochure/published/disclosure"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.pgimindia.com/mutual-funds/disclosures/Portfolios/Monthly-Portfolio",
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
}

TARGET_FUNDS = {
    "Healthcare": "PGIM India Healthcare Fund",
    "SmallCap": "PGIM India Small Cap Fund",
    "MultiCap": "PGIM India Multi Cap Fund",
    "MultiAsset": "PGIM India Multi Asset Allocation Fund",
    "Midcap": "PGIM India Midcap Fund",
    "LargeCap": "PGIM India Large Cap Fund",
    "LargeAndMidcap": "PGIM India Large and Midcap Fund",
    "FlexiCap": "PGIM India Flexi Cap Fund",
    "EquitySavings": "PGIM India Equity Savings Fund",
    "ELSS": "PGIM India ELSS Tax Saver Fund",
    "BalancedAdvantage": "PGIM India Balanced Advantage Fund",
    "AggressiveHybrid": "PGIM India Aggressive Hybrid Equity Fund",
}

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}


def parse_period(item):
    """Extract (year, month) from dateMonthYear or title."""
    dmy = item.get("dateMonthYear") or ""
    m = re.search(r"([a-zA-Z]{3,9})\s*(\d{4})", dmy)
    if m:
        m_str = m.group(1)[:3].lower()
        yr = int(m.group(2))
        if m_str in MONTH_MAP:
            return yr, MONTH_MAP[m_str]

    title = item.get("title") or ""
    m = re.search(r"([a-zA-Z]{3,9})\s*(\d{4})", title)
    if m:
        m_str = m.group(1)[:3].lower()
        yr = int(m.group(2))
        if m_str in MONTH_MAP:
            return yr, MONTH_MAP[m_str]

    return None, None


def classify_fund(title):
    """Match disclosure title to standard target fund slug."""
    t = title.upper().replace("&", "AND")
    if "HEALTHCARE" in t:
        return "Healthcare"
    if "MULTI ASSET" in t:
        return "MultiAsset"
    if "MULTI CAP" in t:
        return "MultiCap"
    if "SMALL CAP" in t:
        return "SmallCap"
    if "LARGE AND MIDCAP" in t or "LARGE & MIDCAP" in t:
        return "LargeAndMidcap"
    if "LARGE CAP" in t and "MIDCAP" not in t:
        return "LargeCap"
    if "MIDCAP" in t:
        return "Midcap"
    if "FLEXI CAP" in t:
        return "FlexiCap"
    if "EQUITY SAVINGS" in t:
        return "EquitySavings"
    if "ELSS" in t:
        return "ELSS"
    if "BALANCED ADVANTAGE" in t:
        return "BalancedAdvantage"
    if "AGGRESSIVE HYBRID" in t:
        return "AggressiveHybrid"
    return None


def fetch_disclosure_items():
    """Call PGIM API to fetch all portfolio disclosures."""
    print("Fetching disclosures from PGIM API...")
    payload = {"headerId": 2, "sectionId": "SECTION_747960037"}
    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    target_periods = set()
    for y in [2024, 2025, 2026]:
        for m in range(1, 13):
            if (y == 2024 and m >= 10) or (y == 2025) or (y == 2026 and m <= 9):
                target_periods.add((y, m))

    selected_files = {}

    for tab in data.get("data", []):
        for item in tab.get("content", []):
            title = item.get("title", "").strip()
            path = item.get("pdfPath", "").strip()
            if not path or not (path.endswith(".xlsx") or path.endswith(".xlsb") or path.endswith(".xls")):
                continue

            slug = classify_fund(title)
            if not slug:
                continue

            yr, mo = parse_period(item)
            if not yr or not mo or (yr, mo) not in target_periods:
                continue

            key = (slug, yr, mo)
            # If not yet seen, or if prefer .xlsx over .xlsb
            if key not in selected_files:
                selected_files[key] = {
                    "slug": slug,
                    "year": yr,
                    "month": mo,
                    "title": title,
                    "url": path,
                }
            elif path.endswith(".xlsx") and not selected_files[key]["url"].endswith(".xlsx"):
                selected_files[key] = {
                    "slug": slug,
                    "year": yr,
                    "month": mo,
                    "title": title,
                    "url": path,
                }

    return selected_files


def download_single_file(file_info, session=None):
    """Download single portfolio workbook and store in YYYY/MM/ folder."""
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    slug = file_info["slug"]
    year = file_info["year"]
    month = file_info["month"]
    url = file_info["url"]

    # Encode spaces in URL if needed
    safe_url = quote(url, safe=":/%?&=#+@~*'")

    raw_filename = url.split("/")[-1].split("?")[0]
    dest_filename = f"{slug}_{raw_filename}"
    target_dir = RAW_DIR / str(year) / f"{month:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / dest_filename

    # Skip if already exists with valid size
    if target_path.exists() and target_path.stat().st_size > 1024:
        return {
            "slug": slug,
            "year": year,
            "month": month,
            "path": target_path,
            "size": target_path.stat().st_size,
            "status": "EXISTS",
            "url": url,
        }

    for attempt in range(1, 4):
        try:
            resp = session.get(safe_url, headers=HEADERS, timeout=45)
            if resp.status_code == 200 and len(resp.content) > 1024:
                with open(target_path, "wb") as f:
                    f.write(resp.content)
                return {
                    "slug": slug,
                    "year": year,
                    "month": month,
                    "path": target_path,
                    "size": len(resp.content),
                    "status": "DOWNLOADED",
                    "url": url,
                }
            else:
                if attempt == 3:
                    return {
                        "slug": slug,
                        "year": year,
                        "month": month,
                        "path": None,
                        "size": len(resp.content) if resp.status_code == 200 else 0,
                        "status": f"FAILED (HTTP {resp.status_code})",
                        "url": url,
                    }
                time.sleep(2)
        except Exception as e:
            if attempt == 3:
                return {
                    "slug": slug,
                    "year": year,
                    "month": month,
                    "path": None,
                    "size": 0,
                    "status": f"ERROR: {e}",
                    "url": url,
                }
            time.sleep(2)


def main():
    print("=" * 80)
    print("PGIM MF Monthly Portfolio Downloader")
    print(f"Target Directory: {RAW_DIR}")
    print("=" * 80)

    files_to_download = fetch_disclosure_items()
    print(f"Discovered {len(files_to_download)} monthly files across {len(TARGET_FUNDS)} funds.")

    # Breakdown per fund
    counts = {}
    for (slug, yr, mo) in files_to_download:
        counts[slug] = counts.get(slug, 0) + 1
    for slug, fn in TARGET_FUNDS.items():
        print(f"  - {slug:20} ({fn:40}): {counts.get(slug, 0):2d} files")

    session = requests.Session()
    session.headers.update(HEADERS)

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(download_single_file, finfo, session): finfo
            for finfo in files_to_download.values()
        }
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            print(f"[{res['status']:10}] {res['slug']:15} | {res['year']}-{res['month']:02d} | {res['size']:,} bytes -> {res['url'].split('/')[-1]}")

    print("\n" + "=" * 80)
    success = [r for r in results if r["status"] in ("DOWNLOADED", "EXISTS")]
    failed = [r for r in results if r["status"] not in ("DOWNLOADED", "EXISTS")]
    print(f"SUMMARY: {len(success)} succeeded, {len(failed)} failed out of {len(files_to_download)} total files.")
    if failed:
        print("Failed files:")
        for r in failed:
            print(f"  - {r['slug']} {r['year']}-{r['month']}: {r['status']} ({r['url']})")
    print("=" * 80)


if __name__ == "__main__":
    main()
