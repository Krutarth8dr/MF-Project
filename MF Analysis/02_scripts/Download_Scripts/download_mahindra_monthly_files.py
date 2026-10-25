"""
Download monthly portfolio disclosure files for Mahindra Manulife Mutual Fund (Mahindra Manulife MF).

Source:
    Website: https://www.mahindramanulife.com/downloads#disclosures-portfolio-disclosure-monthly-portfolio-disclosure
    API:     https://investorapi.mahindramanulife.com/api/v1/web/preLogin/downloads

Structure:
    Single workbook per month containing all scheme sheets (MMF01, MMF02, ...).

Target Period:
    October 2024 to September 2026 (24 months).

Stores raw files in:
    01_raw_files/Mahindra_Manulife_MF/<YYYY>/<MM>/Monthly_Portfolio_Disclosure_<YYYY>_<MM>.xlsx
"""

import sys
import os
import base64
import json
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "Mahindra_Manulife_MF"

API_URL = "https://investorapi.mahindramanulife.com/api/v1/web/preLogin/downloads"

# AES-256-CBC credentials extracted from index bundle
AES_KEY = b"mahindra2024mahindra2024mahindra"
AES_IV = b"hasnainsheikh202"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def decrypt_payload(b64_str):
    """Decrypts base64 AES-256-CBC encrypted payload."""
    cipher_bytes = base64.b64decode(b64_str)
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV))
    decryptor = cipher.decryptor()
    padded_plain = decryptor.update(cipher_bytes) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    plain = unpadder.update(padded_plain) + unpadder.finalize()
    return json.loads(plain.decode("utf-8"))


def fetch_and_parse_downloads_tree():
    """Fetches the downloads tree from Mahindra Manulife API and extracts monthly files."""
    r = requests.get(API_URL, headers=HEADERS, timeout=25)
    r.raise_for_status()
    payload = r.json().get("payload")
    if not payload:
        raise ValueError("Missing payload in API response")

    data = decrypt_payload(payload).get("data", [])

    monthly_files = {}

    def walk_tree(node):
        if isinstance(node, dict):
            for f in node.get("files", []):
                title = f.get("title") or f.get("documentName") or ""
                file_url = f.get("fileUrl") or f.get("url") or ""
                if "monthly" in title.lower() and "portfolio" in title.lower() and file_url:
                    m_match = re.search(
                        r"(January|February|March|April|May|June|July|August|September|October|November|December)[\s,]+(202[0-9])",
                        title,
                        re.I,
                    )
                    if m_match:
                        m_name = m_match.group(1).lower()
                        m_num = MONTH_NAMES.get(m_name)
                        year = int(m_match.group(2))
                        if (year == 2024 and m_num >= 10) or (year == 2025) or (year == 2026 and m_num <= 9):
                            monthly_files[(year, m_num)] = (title, file_url)
            for sub in node.get("subcategories", []):
                walk_tree(sub)

    for item in data:
        walk_tree(item)

    return monthly_files


def download_single_file(item):
    """Downloads one monthly portfolio workbook."""
    (year, month), (title, file_url) = item
    target_dir = RAW_DIR / str(year) / f"{month:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"Monthly_Portfolio_Disclosure_{year}_{month:02d}.xlsx"

    if target_file.exists() and target_file.stat().st_size > 10000:
        return year, month, target_file, True, f"Already exists ({target_file.stat().st_size:,} bytes)"

    temp_file = target_file.with_suffix(".tmp")
    for attempt in range(3):
        try:
            r = requests.get(file_url, headers=HEADERS, timeout=60)
            if r.status_code == 200 and len(r.content) > 10000:
                with open(temp_file, "wb") as f:
                    f.write(r.content)
                temp_file.replace(target_file)
                return year, month, target_file, True, f"Downloaded ({len(r.content):,} bytes)"
            time.sleep(1)
        except Exception as e:
            if attempt == 2:
                return year, month, target_file, False, str(e)
            time.sleep(1)

    if temp_file.exists():
        temp_file.unlink()
    return year, month, target_file, False, "Download failed after 3 attempts"


def main():
    print("=" * 80)
    print("Mahindra Manulife Mutual Fund - Monthly Portfolio Downloader")
    print("=" * 80)

    print("Fetching and decrypting downloads structure from API...")
    monthly_files = fetch_and_parse_downloads_tree()
    print(f"Discovered {len(monthly_files)} target monthly files for Oct 2024 - Sep 2026.")

    if not monthly_files:
        print("❌ No monthly files found. Please check API structure.")
        sys.exit(1)

    print(f"\nDownloading {len(monthly_files)} files into {RAW_DIR}...\n")

    successful = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(download_single_file, item): item for item in monthly_files.items()}
        for fut in as_completed(futures):
            year, month, target_file, ok, msg = fut.result()
            if ok:
                successful += 1
                print(f"[OK] {year}-{month:02d} -> {msg}")
            else:
                errors += 1
                print(f"[FAIL] {year}-{month:02d} -> {msg}")

    print("\n" + "=" * 80)
    print("Download Summary")
    print("=" * 80)
    print(f"Total Target Months : {len(monthly_files)}")
    print(f"Downloaded / Valid  : {successful}")
    print(f"Failed              : {errors}")
    print(f"Output Directory    : {RAW_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
