import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "HSBC"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

INFO_LIBRARY_URL = "https://www.assetmanagement.hsbc.co.in/en/mutual-funds/investor-resources/information-library"
BASE_URL = "https://www.assetmanagement.hsbc.co.in"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 60
MAX_RETRIES = 3

START_DATE = datetime(2024, 10, 1)
END_DATE = datetime(2026, 8, 31)

# Canonical 14 Target Funds
TARGET_FUNDS = [
    "HSBC Aggressive Hybrid Fund",
    "HSBC Large Cap Fund",
    "HSBC Large & Mid Cap Fund",
    "HSBC Midcap Fund",
    "HSBC Flexi Cap Fund",
    "HSBC Multi Cap Fund",
    "HSBC Small Cap Fund",
    "HSBC Infrastructure Fund",
    "HSBC Value Fund",
    "HSBC Business Cycles Fund",
    "HSBC ELSS Tax saver Fund",
    "HSBC Consumption Fund",
    "HSBC Balanced Advantage Fund",
    "HSBC Financial Services Fund",
]

MONTH_NAME_MAP = {
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
    "dec": 12, "december": 12,
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def print_separator(title=None):
    print("\n" + "=" * 90)
    if title:
        print(title)
        print("=" * 90)


def parse_date_from_link(text, href):
    """
    Parses portfolio date from link text or href.
    Prioritizes text/filename dates over folder dates.
    """
    # 1. Look for 'DD Month YYYY' in link text
    m_text = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if m_text:
        d = int(m_text.group(1))
        mon_str = m_text.group(2).lower()
        y = int(m_text.group(3))
        if mon_str in MONTH_NAME_MAP:
            return datetime(y, MONTH_NAME_MAP[mon_str], d)

    # 2. Look for 'DD-mon-YYYY' in filename
    filename = href.split("/")[-1].lower()
    m_file = re.search(r"(\d{1,2})-([a-z]+)-(\d{4})", filename)
    if m_file:
        d = int(m_file.group(1))
        mon_str = m_file.group(2)
        y = int(m_file.group(3))
        if mon_str in MONTH_NAME_MAP:
            return datetime(y, MONTH_NAME_MAP[mon_str], d)

    # 3. Look for 'document-DDMMYYYY' or '/DDMMYYYY/'
    m_doc = re.search(r"document-(\d{2})(\d{2})(\d{4})", href) or re.search(
        r"/(\d{2})(\d{2})(\d{4})/", href
    )
    if m_doc:
        d, m, y = int(m_doc.group(1)), int(m_doc.group(2)), int(m_doc.group(3))
        try:
            return datetime(y, m, d)
        except ValueError:
            pass

    return None


def match_target_fund(text, href):
    """
    Matches link to one of the 14 canonical HSBC target funds.
    """
    combined = f"{text} {href.split('/')[-1]}".lower()

    # Exclusions
    exclusions = [
        "fof", "index", "debt", "gilt", "overnight", "liquid", "savings",
        "conservative", "arbitrage", "brazil", "asia", "global", "export",
        "dynamic bond", "money market", "short duration", "ultra short",
        "low duration", "credit risk", "corporate bond", "banking and psu"
    ]
    if any(ex in combined for ex in exclusions):
        return None

    if "aggressive" in combined and "hybrid" in combined:
        return "HSBC Aggressive Hybrid Fund"
    if "balanced" in combined and "advantage" in combined:
        return "HSBC Balanced Advantage Fund"
    if "large" in combined and "mid" in combined:
        return "HSBC Large & Mid Cap Fund"
    if "large" in combined and "cap" in combined and "mid" not in combined:
        return "HSBC Large Cap Fund"
    if ("midcap" in combined or "mid cap" in combined or "mid-cap" in combined) and "large" not in combined:
        return "HSBC Midcap Fund"
    if "flexi" in combined:
        return "HSBC Flexi Cap Fund"
    if "multi" in combined and "cap" in combined:
        return "HSBC Multi Cap Fund"
    if "small" in combined and "cap" in combined:
        return "HSBC Small Cap Fund"
    if "infrastructure" in combined:
        return "HSBC Infrastructure Fund"
    if "value" in combined:
        return "HSBC Value Fund"
    if "business" in combined:
        return "HSBC Business Cycles Fund"
    if "elss" in combined or "tax saver" in combined or "tax-saver" in combined or "tax saver equity" in combined:
        return "HSBC ELSS Tax saver Fund"
    if "consumption" in combined:
        return "HSBC Consumption Fund"
    if "financial" in combined and "services" in combined:
        return "HSBC Financial Services Fund"

    return None


def fetch_page_content():
    """
    Fetches the HTML page of HSBC Information Library.
    """
    print(f"Fetching HSBC Information Library from:\n  {INFO_LIBRARY_URL}")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(INFO_LIBRARY_URL, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            print(f"Successfully fetched page ({len(response.text):,} bytes).")
            return response.text
        except Exception as e:
            print(f"  Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(3 * attempt)
            else:
                raise


def download_file(url, target_path):
    """
    Downloads file from url to target_path with retries.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
            resp.raise_for_status()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
            else:
                print(f"    Error downloading {url}: {e}")
                return False


# ==============================================================================
# MAIN DOWNLOAD PIPELINE
# ==============================================================================

def main():
    print_separator("HSBC MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
    print(f"Date Range: {START_DATE.strftime('%b %Y')} to {END_DATE.strftime('%b %Y')}")
    print(f"Target Funds ({len(TARGET_FUNDS)}):")
    for f in TARGET_FUNDS:
        print(f"  - {f}")

    html = fetch_page_content()
    soup = BeautifulSoup(html, "html.parser")

    links = soup.find_all("a", href=True)
    print(f"Found {len(links)} total links on page.")

    # Parse and filter portfolio links
    candidates = []
    for a in links:
        href = a["href"]
        text = a.get_text(strip=True)

        if not (href.endswith(".xlsx") or href.endswith(".xls") or "/portfolios/" in href.lower()):
            continue

        full_url = urljoin(BASE_URL, href)
        date_val = parse_date_from_link(text, href)

        if not date_val:
            continue

        # Check date range and month-end (day >= 28)
        if not (START_DATE <= date_val <= END_DATE and date_val.day >= 28):
            continue

        fund_name = match_target_fund(text, href)
        if not fund_name:
            continue

        is_half_yearly = "half-yearly" in href.lower()

        candidates.append({
            "fund_name": fund_name,
            "date": date_val,
            "year": date_val.year,
            "month": date_val.month,
            "ym": date_val.strftime("%Y-%m"),
            "url": full_url,
            "filename": href.split("/")[-1],
            "text": text,
            "is_half_yearly": is_half_yearly,
        })

    print(f"Matched {len(candidates)} candidate files for target funds.")

    # Deduplicate: if both regular monthly and half-yearly exist for same fund & month, prefer regular
    by_key = {}
    for c in candidates:
        key = (c["ym"], c["fund_name"])
        if key not in by_key:
            by_key[key] = c
        else:
            if by_key[key]["is_half_yearly"] and not c["is_half_yearly"]:
                by_key[key] = c

    deduped_items = sorted(by_key.values(), key=lambda x: (x["date"], x["fund_name"]))
    print(f"Unique fund-month files to download: {len(deduped_items)}")

    # Download loop
    print_separator("STARTING DOWNLOADS")

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, item in enumerate(deduped_items, start=1):
        ym_folder = RAW_FOLDER / f"{item['year']}" / f"{item['month']:02d}"
        target_file = ym_folder / item["filename"]

        # Check if already downloaded and valid
        if target_file.exists() and target_file.stat().st_size > 1024:
            skipped_count += 1
            print(f"[{idx:3d}/{len(deduped_items):3d}] [EXISTS] {item['ym']} | {item['fund_name']:<30} -> {target_file.name}")
            continue

        print(f"[{idx:3d}/{len(deduped_items):3d}] [DOWNLOADING] {item['ym']} | {item['fund_name']:<30} -> {target_file.name}")
        ok = download_file(item["url"], target_file)
        if ok:
            success_count += 1
        else:
            failed_count += 1

        time.sleep(0.1)

    print_separator("DOWNLOAD SUMMARY")
    print(f"Total Target Files:  {len(deduped_items)}")
    print(f"Newly Downloaded:    {success_count}")
    print(f"Already Existing:    {skipped_count}")
    print(f"Failed Downloads:    {failed_count}")
    print(f"Saved to:            {RAW_FOLDER}")


if __name__ == "__main__":
    main()
