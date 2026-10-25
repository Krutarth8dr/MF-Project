"""
Download script for AlphaGrep MF monthly portfolio files.
Downloads all available monthly portfolio files from:
https://www.alphagrepmf.ai/disclosures (backed by https://cmsweb.alphagrepmf.ai)
Target Funds:
- AlphaGrep Flexi Cap Fund
- AlphaGrep Multi Asset Allocation Fund

Saves files to:
01_raw_files/ALPHAGREP_MF/<YYYY>/<MM>/
"""

import json
import os
import re
import socket
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "ALPHAGREP_MF"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

BASE_CMS = "https://cmsweb.alphagrepmf.ai"
PORTFOLIOS_API = f"{BASE_CMS}/api/portfolios?populate=*"

# DNS fallback patch for environments where cmsweb.alphagrepmf.ai resolution times out
orig_getaddrinfo = socket.getaddrinfo

def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host in ["cmsweb.alphagrepmf.ai", "www.alphagrepmf.ai", "alphagrepmf.ai"]:
        return orig_getaddrinfo("103.96.92.170", port, family, type, proto, flags)
    return orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = patched_getaddrinfo

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.alphagrepmf.ai/",
}

TARGET_SCHEME_SLUGS = {
    "AlphaGrep_Flexi_Cap_Fund": "AlphaGrep Flexi Cap Fund",
    "AlphaGrep_Multi_Asset_Allocation_Fund": "AlphaGrep Multi Asset Allocation Fund",
}

# Known files fallback in case CMS API endpoint schema changes in the future
KNOWN_PORTFOLIOS = [
    {
        "scheme": "AlphaGrep Multi Asset Allocation Fund",
        "year": "2026",
        "month": "07",
        "filename": "AlphaGrep_Multi_Asset_July_2026.xls",
        "url": f"{BASE_CMS}/uploads/July_2026_eb239da0d5.xls",
    },
    {
        "scheme": "AlphaGrep Multi Asset Allocation Fund",
        "year": "2026",
        "month": "08",
        "filename": "AlphaGrep_Multi_Asset_August_2026.xls",
        "url": f"{BASE_CMS}/uploads/August_2026_3f4ccd750c.xls",
    },
    {
        "scheme": "AlphaGrep Multi Asset Allocation Fund",
        "year": "2026",
        "month": "09",
        "filename": "AlphaGrep_Multi_Asset_September_2026.xls",
        "url": f"{BASE_CMS}/uploads/September_2026_7e4d87f8f8.xls",
    },
    {
        "scheme": "AlphaGrep Flexi Cap Fund",
        "year": "2026",
        "month": "08",
        "filename": "AlphaGrep_Flexi_Cap_August_2026.xls",
        "url": f"{BASE_CMS}/uploads/August_2026_47739b8257.xls",
    },
    {
        "scheme": "AlphaGrep Flexi Cap Fund",
        "year": "2026",
        "month": "09",
        "filename": "AlphaGrep_Flexi_Cap_September_2026.xls",
        "url": f"{BASE_CMS}/uploads/September_2026_6166646f5d.xls",
    },
]

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
}


def parse_month_year(title_text):
    text = str(title_text).lower()
    for m_name, m_num in MONTH_MAP.items():
        if m_name in text:
            # Look for 4-digit year
            y_m = re.search(r"20\d{2}", text)
            yr = int(y_m.group(0)) if y_m else 2026
            return yr, m_num
    return None, None


def fetch_live_portfolios():
    found = []
    try:
        req = urllib.request.Request(PORTFOLIOS_API, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("data", []):
            attr = item.get("attributes", item)
            scheme_obj = attr.get("scheme", {})
            scheme_slug = scheme_obj.get("slug") or scheme_obj.get("Name") or ""
            if scheme_slug not in TARGET_SCHEME_SLUGS and scheme_obj.get("Name") not in TARGET_SCHEME_SLUGS.values():
                continue

            scheme_canonical = TARGET_SCHEME_SLUGS.get(scheme_slug, scheme_obj.get("Name"))
            file_obj = attr.get("file", {})
            rel_url = file_obj.get("url")
            if not rel_url:
                continue

            full_url = rel_url if rel_url.startswith("http") else f"{BASE_CMS}{rel_url}"
            title = attr.get("title", "")
            raw_fname = file_obj.get("name", "")
            yr, mo = parse_month_year(f"{title} {raw_fname}")
            if not yr or not mo:
                # default to 2026 and detect from title
                yr = 2026
                mo = 9 if "sep" in title.lower() else (8 if "aug" in title.lower() else 7)

            prefix = "AlphaGrep_Flexi_Cap" if "flexi" in scheme_canonical.lower() else "AlphaGrep_Multi_Asset"
            clean_fname = f"{prefix}_{yr}_{mo:02d}.xls"

            found.append({
                "scheme": scheme_canonical,
                "year": f"{yr:04d}",
                "month": f"{mo:02d}",
                "filename": clean_fname,
                "url": full_url,
            })
    except Exception as e:
        print(f"[WARN] Error fetching live portfolios from CMS: {e}")
    return found


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
    print("ALPHAGREP MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
    print(f"Destination: {RAW_FOLDER}")
    print("=" * 80)

    # Use live CMS discovery with fallback to known portfolio list
    all_dict = {}
    for item in KNOWN_PORTFOLIOS:
        key = (item["scheme"], item["year"], item["month"])
        all_dict[key] = item

    live_items = fetch_live_portfolios()
    for item in live_items:
        key = (item["scheme"], item["year"], item["month"])
        all_dict[key] = item

    items = sorted(all_dict.values(), key=lambda x: (x["scheme"], x["year"], x["month"]))
    print(f"Total fund-month workbooks to download: {len(items)}")

    success_count = 0
    for item in items:
        yr = item["year"]
        mo = item["month"]
        url = item["url"]
        fname = item["filename"]
        dest_path = RAW_FOLDER / yr / mo / fname
        if download_file(url, dest_path):
            success_count += 1
        time.sleep(0.5)

    print("=" * 80)
    print(f"DOWNLOAD COMPLETE: {success_count}/{len(items)} files ready.")
    print("=" * 80)


if __name__ == "__main__":
    main()
