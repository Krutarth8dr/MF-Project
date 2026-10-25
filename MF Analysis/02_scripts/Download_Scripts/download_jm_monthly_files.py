"""
Download monthly portfolio disclosure files for JM Financial Mutual Fund (JM Financial MF).

Source:
    Website: https://www.jmfinancialmf.com/downloads/Portfolio-Disclosure/Monthly-Portfolio-of-Schemes
    API:     https://jmmfapi.jmfinancialmf.com/api/GetDownloadNew

Target Funds (10 funds):
    1. JM Aggressive Hybrid Fund
    2. JM Small Cap Fund
    3. JM Multi Asset Allocation Fund
    4. JM Mid Cap Fund
    5. JM Large Cap Fund
    6. JM Large and Mid Cap Fund
    7. JM Focused Fund
    8. JM Flexicap Fund
    9. JM ELSS Tax Saver Fund
    10. JM Value Fund

Target Period:
    October 2024 to September 2026 (or from inception for newer funds).

Stores raw files in:
    01_raw_files/JM_Financial_MF/<YYYY>/<MM>/<filename>
"""

import base64
import json
import re
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "JM_Financial_MF"

API_URL = "https://jmmfapi.jmfinancialmf.com/api/GetDownloadNew"
BASE_FILE_URL = "https://www.jmfinancialmf.com/"

KEY = b"6fa979f20126cb08aa645a8f495f6d85"
IV = b"I8zyA4lVhMCaJ5Kg"

TARGET_FUNDS = {
    "JM Aggressive Hybrid Fund": [r"aggressive\s*hybrid"],
    "JM Small Cap Fund": [r"small\s*cap"],
    "JM Multi Asset Allocation Fund": [r"multi\s*asset"],
    "JM Mid Cap Fund": [r"mid\s*cap"],
    "JM Large Cap Fund": [r"large\s*cap"],
    "JM Large and Mid Cap Fund": [r"large\s*(?:and|&)\s*mid"],
    "JM Focused Fund": [r"focused"],
    "JM Flexicap Fund": [r"flexi\s*cap"],
    "JM ELSS Tax Saver Fund": [r"elss", r"tax\s*saver"],
    "JM Value Fund": [r"value\s*fund"]
}

MONTHS_PREFIX = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

def decrypt_data(b64_cipher: str):
    encrypted = base64.b64decode(b64_cipher)
    cipher = Cipher(algorithms.AES(KEY), modes.CBC(IV))
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return json.loads(data.decode("latin1"))

def extract_month_year(text: str):
    m_num = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](\d{4})', text)
    if m_num:
        return int(m_num.group(3)), int(m_num.group(2))

    m_word = re.search(r'([A-Za-z]+)\s*(?:\d{1,2})?\s*,?\s*(\d{4})', text)
    if m_word:
        w = m_word.group(1).lower()
        y = int(m_word.group(2))
        for pfx, m_val in MONTHS_PREFIX.items():
            if w.startswith(pfx):
                return y, m_val
    return None

def fetch_monthly_catalog():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.jmfinancialmf.com",
        "Referer": "https://www.jmfinancialmf.com/"
    }
    payload = {"IICategoryID": "2", "IISubCategoryID": "4", "IVsearch": ""}
    res = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    res.raise_for_status()
    data = res.json()
    if "data" in data and data["data"]:
        return decrypt_data(data["data"])
    return []

def download_file(relative_url: str, dest_path: Path):
    if dest_path.exists() and dest_path.stat().st_size > 10000:
        print(f"    [SKIPPED] Already exists: {dest_path.name} ({dest_path.stat().st_size} bytes)")
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    full_url = urllib.parse.urljoin(BASE_FILE_URL, urllib.parse.quote(relative_url))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    }

    try:
        r = requests.get(full_url, headers=headers, timeout=60)
        r.raise_for_status()
        if len(r.content) < 5000:
            print(f"    [ERROR] File too small ({len(r.content)} bytes): {full_url}")
            return False
        dest_path.write_bytes(r.content)
        print(f"    [SAVED] {dest_path.name} ({len(r.content)} bytes)")
        return True
    except Exception as e:
        print(f"    [ERROR] Failed to download {full_url}: {e}")
        return False

def main():
    print("=" * 80)
    print("JM Financial MF - Monthly Portfolio Downloader")
    print("=" * 80)

    print("Fetching disclosures catalog from API...")
    items = fetch_monthly_catalog()
    print(f"Total Monthly disclosures reported by API: {len(items)}")

    # Map items to target funds and dates
    matched_by_fund = {k: {} for k in TARGET_FUNDS}

    for item in items:
        title = item.get("Title", "")
        fname = item.get("FileName", "")
        comb = f"{title} {fname}".lower()

        matched_fund = None
        if re.search(r"large\s*(?:and|&)\s*mid", comb):
            matched_fund = "JM Large and Mid Cap Fund"
        else:
            for fund_name, patterns in TARGET_FUNDS.items():
                if fund_name == "JM Large and Mid Cap Fund":
                    continue
                for pat in patterns:
                    if re.search(pat, comb):
                        matched_fund = fund_name
                        break
                if matched_fund:
                    break

        if not matched_fund:
            continue

        dt = extract_month_year(title) or extract_month_year(fname)
        if not dt:
            doc_date = item.get("DocumentDate", "")
            if doc_date and len(doc_date) >= 7:
                dt = int(doc_date[:4]), int(doc_date[5:7])

        if dt:
            y, m = dt
            if (y == 2024 and m >= 10) or (y == 2025) or (y == 2026 and m <= 9):
                matched_by_fund[matched_fund][(y, m)] = item

    total_downloads = sum(len(m) for m in matched_by_fund.values())
    print(f"\nIdentified {total_downloads} monthly files across {len(TARGET_FUNDS)} funds:")
    for fname, m_dict in matched_by_fund.items():
        print(f"  - {fname:<32}: {len(m_dict):2d} files")

    print("\nStarting downloads...")
    success_count = 0
    total_count = 0

    for fund_name, months_dict in matched_by_fund.items():
        print(f"\n>>> Fund: {fund_name} ({len(months_dict)} files)")
        for (year, month) in sorted(months_dict.keys()):
            item = months_dict[(year, month)]
            fname = item.get("FileName", "")
            clean_filename = Path(fname).name
            dest_path = RAW_DIR / str(year) / f"{month:02d}" / clean_filename

            total_count += 1
            if download_file(fname, dest_path):
                success_count += 1

    print("\n" + "=" * 80)
    print(f"Download complete: {success_count}/{total_count} files saved to {RAW_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()
