"""
Download monthly portfolio disclosure files for Old Bridge Mutual Fund (Old Bridge MF).

Source:
    Website: https://oldbridgemf.com/statutory-disclosures.html
    Base URL: https://oldbridgemf.com

Target Funds (2 funds):
    1. Old Bridge Focused Fund (launched in early 2024)
    2. Old Bridge Flexi Cap Fund (launched in March 2026)

Target Period:
    October 2024 to September 2026 (24 months or from fund inception).

Note:
    - Old Bridge Focused Fund has monthly portfolio disclosures from Oct 2024 to Sep 2026.
      In earlier months (Oct 2024 - Oct 2025), disclosures were published as consolidated
      monthly portfolio files ('OBMF_Monthly_Portfolio_OCT_24', 'Monthly_Portfolio_DEC_24', etc.).
      From Nov 2025 onwards, fund-specific files ('Old_Bridge_Focused_Fund_...') were published.
    - Old Bridge Flexi Cap Fund was launched in March 2026, with disclosures from Mar 2026 to Sep 2026.

Stores raw files in:
    01_raw_files/Old_Bridge_MF/<YYYY>/<MM>/<prefix>_<original_filename>.xlsx
"""

import os
import sys
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "Old_Bridge_MF"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PORTAL_URL = "https://oldbridgemf.com/statutory-disclosures.html"
BASE_URL = "https://oldbridgemf.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://oldbridgemf.com/statutory-disclosures.html",
}

# Explicit mapping of known verified monthly files for maximum reliability
KNOWN_MONTHLY_FILES = {
    # Old Bridge Focused Fund (24 months: Oct 2024 to Sep 2026)
    ("Focused", "2024", "10"): "https://oldbridgemf.com/uploads/OBMF_Monthly_Portfolio_OCT_24_804605b1e9.xlsx",
    ("Focused", "2024", "11"): "https://oldbridgemf.com/uploads/OB_Monthly_Portfolio_Nov_24_f335ac6f6f.xlsx",
    ("Focused", "2024", "12"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_DEC_24_13314acb34.xlsx",
    ("Focused", "2025", "01"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_JAN_2025_462e5feb59.xlsx",
    ("Focused", "2025", "02"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_Feb_25_b4c801986c.xlsx",
    ("Focused", "2025", "03"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_March_25_cc03a804c5.xlsx",
    ("Focused", "2025", "04"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_April_25_eefd569ac4.xlsx",
    ("Focused", "2025", "05"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_May_2025_eccc7aa77b.xlsx",
    ("Focused", "2025", "06"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_June_25_61180f7b5e.xlsx",
    ("Focused", "2025", "07"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_July_25_xls_66fe9c7c39.xlsx",
    ("Focused", "2025", "08"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_Final_174b126654.xlsx",
    ("Focused", "2025", "09"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_Sep2025_df5535812a.xlsx",
    ("Focused", "2025", "10"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_October_25_3b7098f9c1.xlsx",
    ("Focused", "2025", "11"): "https://oldbridgemf.com/uploads/Focused_Fund_Monthly_Portfolio_Nov_25_10a5645f6e.xlsx",
    ("Focused", "2025", "12"): "https://oldbridgemf.com/uploads/Monthly_Portfolio_FE_Dec2025_ef99c4d3f6.xlsx",
    ("Focused", "2026", "01"): "https://oldbridgemf.com/uploads/Old_Bridge_Focused_Fund_January_2026_b7c100a811.xlsx",
    ("Focused", "2026", "02"): "https://oldbridgemf.com/uploads/Old_Bridge_Focused_Fund_Monthly_Portfolio_Feb_26_4211b7c07a.xlsx",
    ("Focused", "2026", "03"): "https://oldbridgemf.com/uploads/Old_Bridge_Focused_Fund_467af9ee4f.xlsx",
    ("Focused", "2026", "04"): "https://oldbridgemf.com/uploads/Old_Bridge_Focused_Fund_Apr_26_Portfolio_b11198e4a9.xlsx",
    ("Focused", "2026", "05"): "https://oldbridgemf.com/uploads/Old_Bridge_Focused_Fund_Portfolio_May_26_5ab6ef467e.xlsx",
    ("Focused", "2026", "06"): "https://oldbridgemf.com/uploads/OBFE_9d7d1d029f.xlsx",
    ("Focused", "2026", "07"): "https://oldbridgemf.com/uploads/Old_Bridge_Focused_Fund_Portfolio_July_26_1729091a89.xlsx",
    ("Focused", "2026", "08"): "https://oldbridgemf.com/uploads/OBMF_Focused_Portfolio_Aug_26_f450e08d0d.xlsx",
    ("Focused", "2026", "09"): "https://oldbridgemf.com/uploads/OBMF_Focused_Portfolio_Sept_26_ffe4009490.xlsx",

    # Old Bridge Flexi Cap Fund (7 months: Mar 2026 to Sep 2026)
    ("FlexiCap", "2026", "03"): "https://oldbridgemf.com/uploads/Flexi_Cap_Monthly_Portfolio_March_26_1d35b5e950.xlsx",
    ("FlexiCap", "2026", "04"): "https://oldbridgemf.com/uploads/Old_Bridge_Flexi_Cap_Fund_Apr_26_Portfolio_c8f7d14649.xlsx",
    ("FlexiCap", "2026", "05"): "https://oldbridgemf.com/uploads/Old_Bridge_Flexi_Cap_Fund_Portfolio_May_26_20e8c1644b.xlsx",
    ("FlexiCap", "2026", "06"): "https://oldbridgemf.com/uploads/OBFX_c2050b88e7.xlsx",
    ("FlexiCap", "2026", "07"): "https://oldbridgemf.com/uploads/Old_Bridge_Flexi_Cap_Fund_Portfolio_July_26_ca0b230896.xlsx",
    ("FlexiCap", "2026", "08"): "https://oldbridgemf.com/uploads/OBMF_Flexi_Cap_Portfolio_Aug_26_361398e946.xlsx",
    ("FlexiCap", "2026", "09"): "https://oldbridgemf.com/uploads/OBMF_Flexi_Cap_Portfolio_Sept_26_0cfdd46aac.xlsx",
}


def download_single_file(scheme_key, year, month, file_url, session=None):
    """Download a single monthly file and save into structured directory."""
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    filename = file_url.split("/")[-1].split("?")[0]
    # Prefix with scheme key for easy identification
    dest_filename = f"{scheme_key}_{filename}"
    target_dir = RAW_DIR / year / month
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / dest_filename

    # If already downloaded and valid size, skip
    if target_path.exists() and target_path.stat().st_size > 1024:
        return {
            "scheme": scheme_key,
            "year": year,
            "month": month,
            "path": target_path,
            "size": target_path.stat().st_size,
            "status": "EXISTS",
            "url": file_url,
        }

    for attempt in range(1, 4):
        try:
            resp = session.get(file_url, headers=HEADERS, timeout=45)
            if resp.status_code == 200 and len(resp.content) > 1024:
                with open(target_path, "wb") as f:
                    f.write(resp.content)
                return {
                    "scheme": scheme_key,
                    "year": year,
                    "month": month,
                    "path": target_path,
                    "size": len(resp.content),
                    "status": "DOWNLOADED",
                    "url": file_url,
                }
            else:
                if attempt == 3:
                    return {
                        "scheme": scheme_key,
                        "year": year,
                        "month": month,
                        "path": None,
                        "size": len(resp.content) if resp.status_code == 200 else 0,
                        "status": f"FAILED (HTTP {resp.status_code}, len={len(resp.content)})",
                        "url": file_url,
                    }
                time.sleep(2)
        except Exception as e:
            if attempt == 3:
                return {
                    "scheme": scheme_key,
                    "year": year,
                    "month": month,
                    "path": None,
                    "size": 0,
                    "status": f"ERROR: {e}",
                    "url": file_url,
                }
            time.sleep(2)


def main():
    print("=" * 80)
    print("Old Bridge MF Monthly Portfolio Downloader")
    print(f"Target Directory: {RAW_DIR}")
    print(f"Total files to process: {len(KNOWN_MONTHLY_FILES)}")
    print("=" * 80)

    session = requests.Session()
    session.headers.update(HEADERS)

    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {}
        for (scheme_key, year, month), url in KNOWN_MONTHLY_FILES.items():
            f = executor.submit(download_single_file, scheme_key, year, month, url, session)
            futures[f] = (scheme_key, year, month)

        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            print(f"[{res['status']}] {res['scheme']} | {res['year']}-{res['month']} | {res['size']:,} bytes -> {res['url'].split('/')[-1]}")

    print("\n" + "=" * 80)
    success = [r for r in results if r["status"] in ("DOWNLOADED", "EXISTS")]
    failed = [r for r in results if r["status"] not in ("DOWNLOADED", "EXISTS")]
    print(f"SUMMARY: {len(success)} succeeded, {len(failed)} failed out of {len(KNOWN_MONTHLY_FILES)} total files.")
    if failed:
        print("Failed files:")
        for r in failed:
            print(f"  - {r['scheme']} {r['year']}-{r['month']}: {r['status']} ({r['url']})")
    print("=" * 80)


if __name__ == "__main__":
    main()
