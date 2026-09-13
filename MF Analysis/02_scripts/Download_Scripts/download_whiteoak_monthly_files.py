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
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "WHITEOAK"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

API_BASE_URL = "https://cms.whiteoakamc.com/api/scheme-portfolios"

START_DATE = datetime(2024, 10, 1)
END_DATE = datetime(2026, 8, 31)

TARGET_FUNDS = [
    # Existing 7 funds
    "WhiteOak Capital Large Cap Fund",
    "WhiteOak Capital Flexi Cap Fund",
    "WhiteOak Capital Mid Cap Fund",
    "WhiteOak Capital ELSS Tax Saver Fund",
    "WhiteOak Capital Balanced Advantage Fund",
    "WhiteOak Capital Multi Asset Allocation Fund",
    "WhiteOak Capital Multi Cap Fund",
    # 9 New funds
    "WhiteOak Capital Balanced Hybrid Fund",
    "WhiteOak Capital Large & Mid Cap Fund",
    "WhiteOak Capital Banking & Financial Services Fund",
    "WhiteOak Capital Pharma and Healthcare Fund",
    "WhiteOak Capital Special Opportunities Fund",
    "WhiteOak Capital Digital Bharat Fund",
    "WhiteOak Capital Quality Equity Fund",
    "WhiteOak Capital Equity Savings Fund",
    "WhiteOak Capital Consumption Opportunities Fund",
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


def normalize_text(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


TARGET_NORM_MAP = {normalize_text(f): f for f in TARGET_FUNDS}


def match_canonical_fund(scheme_name, doc_name):
    norm_scheme = normalize_text(scheme_name or "")
    norm_doc = normalize_text(doc_name or "")

    # Check more specific names first to avoid collisions
    ordered_funds = [
        "WhiteOak Capital Large & Mid Cap Fund",
        "WhiteOak Capital Large Cap Fund",
        "WhiteOak Capital Mid Cap Fund",
        "WhiteOak Capital Flexi Cap Fund",
        "WhiteOak Capital ELSS Tax Saver Fund",
        "WhiteOak Capital Balanced Hybrid Fund",
        "WhiteOak Capital Balanced Advantage Fund",
        "WhiteOak Capital Multi Asset Allocation Fund",
        "WhiteOak Capital Multi Cap Fund",
        "WhiteOak Capital Banking & Financial Services Fund",
        "WhiteOak Capital Pharma and Healthcare Fund",
        "WhiteOak Capital Special Opportunities Fund",
        "WhiteOak Capital Digital Bharat Fund",
        "WhiteOak Capital Quality Equity Fund",
        "WhiteOak Capital Equity Savings Fund",
        "WhiteOak Capital Consumption Opportunities Fund",
    ]

    for f in ordered_funds:
        norm_f = normalize_text(f)
        if norm_f in norm_scheme or norm_f in norm_doc:
            return f

    return None


def parse_date_from_text(doc_name, file_name):
    for text in [doc_name, file_name]:
        if not text:
            continue
        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*[-_ ]?\s*([a-zA-Z]+)\s*[-_ ]?\s*(\d{4})", text, re.I)
        if m:
            d_str, m_str, y_str = m.groups()
            m_num = MONTH_MAP.get(m_str.lower().strip())
            if m_num:
                return datetime(int(y_str), m_num, 1)

        m2 = re.search(r"([a-zA-Z]+)\s*[-_ ]?\s*(\d{4})", text, re.I)
        if m2:
            m_str, y_str = m2.groups()
            m_num = MONTH_MAP.get(m_str.lower().strip())
            if m_num:
                return datetime(int(y_str), m_num, 1)
    return None


def fetch_whiteoak_catalog(session):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Referer": "https://mf.whiteoakamc.com/",
        "Accept": "*/*",
    }

    all_items = []
    page = 1
    page_size = 100

    print("[1/3] Fetching scheme portfolios catalog from WhiteOak Strapi CMS...")
    while True:
        url = f"{API_BASE_URL}?populate=*&pagination[page]={page}&pagination[pageSize]={page_size}&sort[0]=id:desc"
        r = session.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        res = r.json()
        items = res.get("data", [])
        all_items.extend(items)
        pagination = res.get("meta", {}).get("pagination", {})
        page_count = pagination.get("pageCount", 1)
        print(f"  Fetched Page {page}/{page_count} ({len(items)} items, cumulative: {len(all_items)})")
        if page >= page_count:
            break
        page += 1

    print(f"\n[2/3] Filtering Monthly Portfolio files for target funds (Oct 2024 - Aug 2026)...")

    matched_catalog = []
    for it in all_items:
        attrs = it.get("attributes", {})
        period = str(attrs.get("period", "")).strip()
        if period.lower() != "monthly":
            continue

        scheme_name = attrs.get("scheme_name", "")
        doc_name = attrs.get("doc_name", "")

        fund_match = match_canonical_fund(scheme_name, doc_name)
        if not fund_match:
            continue

        doc_file = attrs.get("doc_file", {}).get("data", {})
        if not doc_file:
            continue

        file_attrs = doc_file.get("attributes", {})
        file_name = file_attrs.get("name", "")
        file_url = file_attrs.get("url", "")
        ext = file_attrs.get("ext", "").lower()

        if ext not in [".xlsx", ".xls"]:
            continue

        dt = parse_date_from_text(doc_name, file_name)
        if not dt:
            continue

        if START_DATE <= dt <= END_DATE:
            matched_catalog.append({
                "fund_name": fund_match,
                "doc_name": doc_name,
                "file_name": file_name,
                "file_url": file_url,
                "dt": dt,
                "year": dt.year,
                "month": dt.month,
            })

    # Sort by date, fund
    matched_catalog.sort(key=lambda x: (x["dt"], x["fund_name"]))
    print(f"  Found {len(matched_catalog)} matching monthly workbooks across {len(TARGET_FUNDS)} funds.")
    return matched_catalog


def run_download():
    print("=" * 75)
    print("WHITEOAK MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
    print(f"Target Date Range: {START_DATE.strftime('%b %Y')} to {END_DATE.strftime('%b %Y')}")
    print(f"Target Funds:      {len(TARGET_FUNDS)} funds")
    print(f"Raw Output Folder: {RAW_FOLDER}")
    print("=" * 75)

    session = requests.Session(impersonate="chrome124")
    catalog = fetch_whiteoak_catalog(session)

    downloaded = 0
    skipped = 0
    failed = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Referer": "https://mf.whiteoakamc.com/",
    }

    print("\n[3/3] Downloading monthly files...")
    for item in catalog:
        fund_name = item["fund_name"]
        dt = item["dt"]
        url = item["file_url"]
        orig_filename = item["file_name"]

        y = dt.year
        m = dt.month
        month_label = dt.strftime("%b %Y")

        target_dir = RAW_FOLDER / str(y) / f"{m:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / orig_filename

        if target_file.exists() and target_file.stat().st_size > 5000:
            print(f"  [SKIPPED] [{month_label}] {fund_name} ({orig_filename})")
            skipped += 1
            continue

        print(f"  [DOWNLOADING] [{month_label}] {fund_name} -> {orig_filename} ... ", end="", flush=True)

        success = False
        for attempt in range(1, 4):
            try:
                r = session.get(url, headers=headers, timeout=60)
                if r.status_code == 200 and len(r.content) > 5000:
                    with open(target_file, "wb") as f:
                        f.write(r.content)
                    print(f"DONE ({len(r.content):,} bytes)")
                    downloaded += 1
                    success = True
                    break
                else:
                    print(f"[Retry {attempt}: {r.status_code}] ", end="", flush=True)
                    time.sleep(2)
            except Exception as e:
                print(f"[Retry {attempt}: {e}] ", end="", flush=True)
                time.sleep(2)

        if not success:
            print("FAILED")
            failed += 1

    print("\n" + "=" * 75)
    print("DOWNLOAD SUMMARY:")
    print(f"  Total target files: {len(catalog)}")
    print(f"  Newly downloaded:   {downloaded}")
    print(f"  Already existed:    {skipped}")
    print(f"  Failed:             {failed}")
    print("=" * 75)


if __name__ == "__main__":
    run_download()
