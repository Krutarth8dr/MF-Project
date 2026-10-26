"""
Download monthly portfolio disclosure files for Samco Mutual Fund (Samco MF).

Source:
    Website: https://www.samcomf.com/StatutoryDisclosure#PortfolioDisclosures

Target Funds (4 funds):
    1. Samco Multi Cap Fund (MultiCap)
    2. Samco Special Opportunities Fund (Special_Opportunities)
    3. Samco Flexi Cap Fund (Flexicap)
    4. Samco Small Cap Fund (Small_Cap)

Target Period:
    October 2024 to September 2026 (24 months or from fund inception).

Output Structure:
    01_raw_files/Samco_MF/<YYYY>/<MM>/<Fund_Code>_<YYYY>_<MM>.<ext>
"""

import os
import sys
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "Samco_MF"
RAW_DIR.mkdir(parents=True, exist_ok=True)

DISCLOSURE_URL = "https://www.samcomf.com/StatutoryDisclosure"
BASE_URL = "https://www.samcomf.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.samcomf.com/",
}

FUNDS = {
    "SAMCO_MULTICAP": {
        "name": "Samco Multi Cap Fund",
        "regex": r"multicap|multi_cap",
    },
    "SAMCO_SPECIAL_OPP": {
        "name": "Samco Special Opportunities Fund",
        "regex": r"special_opportunities|specialopportunities",
    },
    "SAMCO_FLEXICAP": {
        "name": "Samco Flexi Cap Fund",
        "regex": r"flexicap|flexi_cap",
    },
    "SAMCO_SMALLCAP": {
        "name": "Samco Small Cap Fund",
        "regex": r"small_cap|smallcap",
    },
}

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4, "apirl": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def parse_month_year(filename: str):
    """Extract (year, month) from URL or filename."""
    fn_lower = filename.lower()

    # Search for year (2020-2029)
    years = re.findall(r"202[0-9]", fn_lower)
    if not years:
        return None, None
    year = int(years[0])

    # Search for month name (longest name match first to avoid 'mar' in 'march')
    month = None
    for m_name in sorted(MONTH_MAP.keys(), key=lambda x: -len(x)):
        if m_name in fn_lower:
            month = MONTH_MAP[m_name]
            break

    return year, month


def scrape_samco_catalog():
    """Fetch all portfolio download links from StatutoryDisclosure page."""
    print("=" * 80)
    print("Fetching Samco Statutory Disclosure catalog...")
    print(f"URL: {DISCLOSURE_URL}")
    print("=" * 80)

    try:
        resp = requests.get(DISCLOSURE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        print(f"❌ Failed to load StatutoryDisclosure: {exc}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    all_links = set()

    for a in soup.find_all("a"):
        href = a.get("href", "")
        if not href:
            continue
        h_strip = href.strip()
        if ("amc-document-download" in h_strip or "media.samcomf.com" in h_strip) and (
            h_strip.lower().endswith(".xlsx") or h_strip.lower().endswith(".xls")
        ):
            if h_strip.startswith("/"):
                h_strip = BASE_URL + h_strip
            all_links.add(h_strip)

    print(f"Discovered {len(all_links)} unique Excel links across Samco site.")

    # Match against target schemes and months (Oct 2024 to Sep 2026)
    tasks = []
    for fund_code, fund_cfg in FUNDS.items():
        pattern = fund_cfg["regex"]
        found_for_fund = {}

        for url in sorted(all_links):
            fn = url.split("/")[-1]
            fn_lower = fn.lower()

            # Ignore fortnightly files
            if "fortnightly" in fn_lower or re.search(r"15[0-9]{6}", fn_lower):
                continue

            if not re.search(pattern, fn_lower):
                continue

            year, month = parse_month_year(fn)
            if not year or not month:
                continue

            # Target range: Oct 2024 to Sep 2026
            if (year == 2024 and month >= 10) or (year == 2025) or (year == 2026 and month <= 9):
                key = f"{year}-{month:02d}"
                is_hy = "hy" in fn_lower or "half" in fn_lower

                # Prefer monthly over half-yearly if both present
                if key not in found_for_fund or (found_for_fund[key]["is_hy"] and not is_hy):
                    found_for_fund[key] = {
                        "fund_code": fund_code,
                        "fund_name": fund_cfg["name"],
                        "year": year,
                        "month": month,
                        "is_hy": is_hy,
                        "url": url,
                        "filename": fn,
                    }

        for item in found_for_fund.values():
            tasks.append(item)

    print(f"Matched {len(tasks)} target monthly files for the 4 schemes.")
    return sorted(tasks, key=lambda t: (t["fund_code"], t["year"], t["month"]))


def download_single_file(item: dict) -> dict:
    """Download one portfolio Excel file to disk."""
    fund_code = item["fund_code"]
    year = item["year"]
    month = item["month"]
    url = item["url"]

    # Target path
    ext = Path(item["filename"]).suffix or ".xlsx"
    dest_dir = RAW_DIR / str(year) / f"{month:02d}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / f"{fund_code}_{year}_{month:02d}{ext}"

    # Skip if valid existing file
    if dest_file.exists() and dest_file.stat().st_size > 5000:
        return {
            "status": "SKIPPED",
            "file": dest_file,
            "size": dest_file.stat().st_size,
            "fund": item["fund_name"],
            "period": f"{year}-{month:02d}",
        }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 5000:
                with open(dest_file, "wb") as f:
                    f.write(resp.content)
                return {
                    "status": "DOWNLOADED",
                    "file": dest_file,
                    "size": len(resp.content),
                    "fund": item["fund_name"],
                    "period": f"{year}-{month:02d}",
                }
            time.sleep(1)
        except Exception as exc:
            if attempt == max_retries:
                return {
                    "status": "ERROR",
                    "error": str(exc),
                    "fund": item["fund_name"],
                    "period": f"{year}-{month:02d}",
                    "url": url,
                }
            time.sleep(2)

    return {
        "status": "FAILED",
        "fund": item["fund_name"],
        "period": f"{year}-{month:02d}",
        "url": url,
    }


def main():
    start_time = time.time()
    tasks = scrape_samco_catalog()

    if not tasks:
        print("❌ No files found to download!")
        sys.exit(1)

    print("\n" + "=" * 80)
    print(f"Downloading {len(tasks)} Samco MF portfolio files (parallel execution)...")
    print("=" * 80)

    downloaded = 0
    skipped = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(download_single_file, task): task for task in tasks}
        for future in as_completed(futures):
            res = future.result()
            st = res["status"]
            fund = res["fund"]
            period = res["period"]
            if st == "DOWNLOADED":
                downloaded += 1
                size_kb = res["size"] / 1024
                print(f"  ✓ [{period}] {fund}: {size_kb:.1f} KB")
            elif st == "SKIPPED":
                skipped += 1
                size_kb = res["size"] / 1024
                print(f"  - [{period}] {fund}: already present ({size_kb:.1f} KB)")
            else:
                failed += 1
                err = res.get("error", "HTTP error")
                print(f"  ❌ [{period}] {fund}: {err} ({res.get('url', '')})")

    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print("DOWNLOAD COMPLETE")
    print(f"Total: {len(tasks)} | Downloaded: {downloaded} | Skipped: {skipped} | Failed: {failed}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Storage: {RAW_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
