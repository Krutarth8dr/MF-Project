import os
import re
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from curl_cffi import requests

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "UNION"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.unionmf.com"
API_ENDPOINT = "https://www.unionmf.com/api/downloads/documents?%24filter=FolderId%20eq%20{guid}"

TARGET_FUNDS = [
    "Union Equity Savings Fund",
    "Union Active Momentum Fund",
    "Union Balanced Advantage Fund",
    "Union ELSS Tax Saver Fund",
    "Union Childrens Fund",
    "Union Midcap Fund",
    "Union Focused Fund",
    "Union Multi Asset Allocation Fund",
    "Union Value Fund",
    "Union Consumption Fund",
    "Union Multicap Fund",
    "Union Flexi Cap Fund",
    "Union Small Cap Fund",
    "Union Large & Midcap Fund",
    "Union Aggressive Hybrid Fund",
    "Union Innovation & Opportunities Fund",
    "Union Largecap Fund",
    "Union Business Cycle Fund",
]

# Month to Folder GUID mapping (Oct 2024 - Aug 2026)
MONTH_FOLDER_GUIDS = [
    ("2024-10", "2647af59-1cb8-4601-b999-7db8d7d674ee"),
    ("2024-11", "c27e1842-7b18-4125-a9ad-010889a1c270"),
    ("2024-12", "93dd7b98-a7e9-4860-8d24-85f88f11ddf4"),
    ("2025-01", "1b7d4fa6-06ff-4f1c-96ea-6d01ddc54bad"),
    ("2025-02", "25f5a8d3-4608-473c-be32-d3300bb36a3e"),
    ("2025-03", "d39c17b9-3da5-4a13-bd4f-5538ff27a376"),
    ("2025-04", "b9d813e3-ad5f-40fe-8026-b2b00fbdf206"),
    ("2025-05", "948f72ff-6aa9-4ed1-8aa4-c0894547e4ed"),
    ("2025-06", "d7184a71-aea6-496b-9768-118f00e8c8d9"),
    ("2025-07", "7b353f71-1c2e-436d-bc47-c744059cb648"),
    ("2025-08", "7de1f489-8b81-4af6-baf5-34c925f033cc"),
    ("2025-09", "3dd070f4-bd3c-40f0-86db-4fe4d5ff8c04"),
    ("2025-10", "17904dea-eceb-4543-b762-684025234c53"),
    ("2025-11", "2985978e-3428-418f-89b5-72fe10ad1aae"),
    ("2025-12", "6b14a299-fd37-41ed-84f7-c35a54df5f21"),
    ("2026-01", "1506abdf-6c38-428e-b7fd-f3d281a660ac"),
    ("2026-02", "b6cafa81-47fb-4935-bc54-b752b9e7d797"),
    ("2026-03", "f6590be0-e035-43c8-a984-e2cdd2370270"),
    ("2026-04", "9b297250-fb6a-438e-88f1-6433bf38f71f"),
    ("2026-05", "35c05df3-b43f-4f9e-849c-538afc5814f7"),
    ("2026-06", "4e8d856a-158b-43a0-bc2f-6e46547ab475"),
    ("2026-07", "5fd732bb-03f5-435c-852b-79218a93d0f3"),
    ("2026-08", "e4709461-3dcd-4a47-8a23-605a090d1eef"),
]

def normalize_text(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())

TARGET_NORM_MAP = {normalize_text(f): f for f in TARGET_FUNDS}

def match_fund_name(title):
    norm_title = normalize_text(title)
    for norm_name, original_name in TARGET_NORM_MAP.items():
        if norm_name in norm_title:
            return original_name
    return None

# ==============================================================================
# MAIN DOWNLOAD PIPELINE
# ==============================================================================

def run_download():
    print("=" * 75)
    print("UNION MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
    print(f"Target Months: {MONTH_FOLDER_GUIDS[0][0]} to {MONTH_FOLDER_GUIDS[-1][0]} ({len(MONTH_FOLDER_GUIDS)} months)")
    print(f"Target Funds: {len(TARGET_FUNDS)} funds")
    print(f"Raw Output Folder: {RAW_FOLDER}")
    print("=" * 75)

    session = requests.Session(impersonate="chrome124")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Referer": "https://www.unionmf.com/about-us/downloads",
    }

    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    for ym, guid in MONTH_FOLDER_GUIDS:
        year_str, month_str = ym.split("-")
        target_dir = RAW_FOLDER / year_str / month_str
        target_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[{ym}] Querying Folder {guid} ...")
        api_url = API_ENDPOINT.format(guid=guid)

        try:
            r = session.get(api_url, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            documents = data.get("value", [])
        except Exception as e:
            print(f"  [ERROR] Failed to query API for {ym}: {e}")
            total_failed += 1
            continue

        matched_docs = []
        for doc in documents:
            title = doc.get("Title", "")
            rel_url = doc.get("Url", "")
            fund_match = match_fund_name(title)
            clean_url = rel_url.split("?")[0].lower()
            if fund_match and (clean_url.endswith(".xlsx") or clean_url.endswith(".xls")):
                matched_docs.append((fund_match, title, rel_url))

        print(f"  Matched {len(matched_docs)} / {len(TARGET_FUNDS)} target fund files.")

        for fund_name, title, rel_url in matched_docs:
            if rel_url.startswith("http"):
                file_url = rel_url
            else:
                file_url = BASE_URL + rel_url

            # Extract clean filename
            url_path = urllib.parse.unquote(rel_url.split("?")[0])
            filename = os.path.basename(url_path)
            target_file = target_dir / filename

            if target_file.exists() and target_file.stat().st_size > 5000:
                print(f"    [SKIPPED] {fund_name} ({filename})")
                total_skipped += 1
                continue

            print(f"    [DOWNLOADING] {fund_name} -> {filename} ... ", end="", flush=True)
            success = False
            for attempt in range(1, 4):
                try:
                    res = session.get(file_url, headers=headers, timeout=60)
                    if res.status_code == 200 and len(res.content) > 5000:
                        with open(target_file, "wb") as f:
                            f.write(res.content)
                        print(f"DONE ({len(res.content):,} bytes)")
                        total_downloaded += 1
                        success = True
                        break
                    else:
                        print(f"[Retry {attempt}] ", end="", flush=True)
                        time.sleep(2)
                except Exception as ex:
                    print(f"[Retry {attempt}: {ex}] ", end="", flush=True)
                    time.sleep(2)

            if not success:
                print("FAILED")
                total_failed += 1

    print("\n" + "=" * 75)
    print("DOWNLOAD SUMMARY:")
    print(f"  Newly downloaded: {total_downloaded}")
    print(f"  Already existed:  {total_skipped}")
    print(f"  Failed:           {total_failed}")
    print("=" * 75)

if __name__ == "__main__":
    run_download()
