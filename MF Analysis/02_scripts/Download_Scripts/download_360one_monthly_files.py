"""
Download monthly portfolio disclosure files for 360 ONE Mutual Fund.
Historical scope: October 2024 through August 2026 (23 files).
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

RAW_DIR = Path(__file__).resolve().parents[2] / "01_raw_files" / "360_ONE"
RAW_DIR.mkdir(parents=True, exist_ok=True)

SCRATCH_JSON = Path(r"C:\Users\Krutarth\.gemini\antigravity\brain\db78f6aa-4677-4939-948c-dab195a25360\scratch\360_monthly_portfolio.json")

def get_target_files():
    with open(SCRATCH_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    yearly = data.get("yearlyData", [])
    month_order = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12
    }

    all_monthly_files = []
    for y_item in yearly:
        y_str = y_item.get("year", "")
        m_yr = re.search(r"(\d{4})", y_str)
        yr = int(m_yr.group(1)) if m_yr else 0

        m_data = y_item.get("monthlyData", [])
        for md in m_data:
            d_groups = md.get("documentGroups", [])
            for dg in d_groups:
                docs = dg.get("documents", [])
                for doc in docs:
                    fname = doc.get("fileName", "")
                    furl = doc.get("fileUrl", "")
                    if furl.endswith(".xls") or furl.endswith(".xlsx"):
                        m_num = 0
                        for m_name, num in month_order.items():
                            if m_name in fname.lower() or m_name in furl.lower():
                                m_num = num
                                break
                        all_monthly_files.append({
                            "year": yr,
                            "month_name": fname,
                            "month_num": m_num,
                            "url": furl,
                            "file_name": furl.split("/")[-1]
                        })

    target_files = []
    for f in all_monthly_files:
        yr = f["year"]
        m = f["month_num"]
        if (yr == 2024 and m >= 10) or (yr == 2025) or (yr == 2026 and m <= 8):
            target_files.append(f)

    target_files.sort(key=lambda x: (x["year"], x["month_num"]))
    return target_files

def main():
    targets = get_target_files()
    print("=" * 80)
    print(f"360 ONE Monthly Portfolio Downloader - Found {len(targets)} target files")
    print("=" * 80)

    for idx, item in enumerate(targets, 1):
        yr = item["year"]
        m = item["month_num"]
        fname = item["file_name"]
        url = item["url"]
        dest = RAW_DIR / fname

        if dest.exists() and dest.stat().st_size > 50000:
            print(f"[{idx:02d}/{len(targets)}] Already exists: {fname} ({dest.stat().st_size:,} bytes)")
            continue

        success = False
        for attempt in range(1, 6):
            print(f"[{idx:02d}/{len(targets)}] Downloading {yr}-{m:02d} (attempt {attempt}): {fname}...")
            res = subprocess.run(
                ["curl.exe", "-s", "-f", "--ssl-no-revoke", "-o", str(dest), url],
                capture_output=True,
                text=True
            )

            if res.returncode == 0 and dest.exists() and dest.stat().st_size > 50000:
                print(f"    [OK] Saved {fname} ({dest.stat().st_size:,} bytes)")
                success = True
                break
            else:
                print(f"    [RETRY] Attempt {attempt} failed (code {res.returncode}). Retrying in 1s...")
                time.sleep(1)

        if not success:
            print(f"    [FATAL] Failed to download {fname} after 5 attempts.")

    print("\n" + "=" * 80)
    downloaded = list(RAW_DIR.glob("*.*"))
    print(f"Total files in {RAW_DIR}: {len(downloaded)}")
    print("=" * 80)

if __name__ == "__main__":
    main()
