"""
Download monthly portfolio disclosure files for ITI Mutual Fund (ITI MF).

Source:
    Website: https://www.itiamc.com/statuory-disclosure?type=Portfolio%20Disclosures
    API:     https://itiamc.com/jeeth/api/v1/catalog/getPartnerDocumentByType

Encryption Details:
    AES-128-CBC with PKCS7 padding.
    Key: b"aar6tzij8o1snaar"
    IV:  b"0123456789ABCDEF"

Stores raw files in:
    01_raw_files/ITI_MF/<YYYY>/<MM>/<filename>
"""

import base64
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "ITI_MF"

KEY = b"aar6tzij8o1snaar"
IV = b"0123456789ABCDEF"

API_URL = "https://itiamc.com/jeeth/api/v1/catalog/getPartnerDocumentByType"

MONTHS_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

def encrypt_data(plain_text: str) -> str:
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plain_text.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(KEY), modes.CBC(IV))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")

def decrypt_data(b64_cipher: str) -> str:
    encrypted = base64.b64decode(b64_cipher)
    cipher = Cipher(algorithms.AES(KEY), modes.CBC(IV))
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return data.decode("utf-8")

def generate_guid() -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "".join(random.choice(chars) for _ in range(32))

def call_iti_api(url: str, payload_dict: dict) -> dict:
    payload = dict(payload_dict)
    payload["guid"] = generate_guid()
    payload["timeStamp"] = int(time.time() * 1000)

    edata = encrypt_data(json.dumps(payload))
    body = {"eData": edata}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.itiamc.com/statuory-disclosure?type=Portfolio%20Disclosures"
    }

    res = requests.post(url, headers=headers, json=body, timeout=30)
    res.raise_for_status()
    res_json = res.json()
    if "eData" in res_json:
        decrypted = decrypt_data(res_json["eData"])
        return json.loads(decrypted)
    return res_json

def parse_file_month_year(f: dict):
    fname = f.get("fileName", "").strip()
    url = f.get("url", "").strip()

    # Try parsing month and year from fileName e.g. "Monthly Portfolio - September 2026"
    m = re.search(r'([A-Za-z]+)\s+(\d{4})', fname)
    if m:
        month_name = m.group(1).lower()
        year = int(m.group(2))
        month = MONTHS_MAP.get(month_name)
        if month:
            return year, month, fname, url

    # Try parsing from URL e.g. 30092026 or 31.07.2026
    m2 = re.search(r'(\d{2})[._](\d{2})[._](\d{4})', url)
    if m2:
        return int(m2.group(3)), int(m2.group(2)), fname, url

    return None

def download_file(url: str, dest_path: Path):
    if dest_path.exists() and dest_path.stat().st_size > 10000:
        print(f"  [SKIPPED] Already exists: {dest_path.name} ({dest_path.stat().st_size} bytes)")
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Referer": "https://www.itiamc.com/statuory-disclosure?type=Portfolio%20Disclosures"
    }

    try:
        r = requests.get(url, headers=headers, timeout=60)
        r.raise_for_status()
        if len(r.content) < 5000:
            print(f"  [ERROR] File too small ({len(r.content)} bytes): {url}")
            return False
        dest_path.write_bytes(r.content)
        print(f"  [SAVED] {dest_path.name} ({len(r.content)} bytes)")
        return True
    except Exception as e:
        print(f"  [ERROR] Failed to download {url}: {e}")
        return False

def main():
    print("=" * 80)
    print("ITI MF - Monthly Portfolio Downloader")
    print("=" * 80)

    print("Fetching disclosures catalog from ITI AMC API...")
    data = call_iti_api(API_URL, {"type": "Disclosure"})

    monthly_files = []
    for item in data.get("data", {}).get("typeList", []):
        if item.get("subType") == "Portfolio Disclosures":
            for topic_obj in item.get("subTypesList", []):
                if topic_obj.get("topic") == "Monthly":
                    monthly_files = topic_obj.get("topicsList", [])
                    break

    print(f"Total Monthly disclosures reported by API: {len(monthly_files)}")

    target_files = []
    for f in monthly_files:
        info = parse_file_month_year(f)
        if info:
            year, month, fname, url = info
            # Keep Oct 2024 to Sep 2026
            if (year == 2024 and month >= 10) or (year == 2025) or (year == 2026 and month <= 9):
                target_files.append((year, month, fname, url))

    # Sort chronologically
    target_files.sort(key=lambda x: (x[0], x[1]))
    print(f"Found {len(target_files)} target monthly files (Oct 2024 - Sep 2026):")

    success_count = 0
    for year, month, fname, url in target_files:
        filename = url.split("/")[-1]
        dest_path = RAW_DIR / str(year) / f"{month:02d}" / filename
        print(f"\nProcessing {year}-{month:02d}: {fname}")
        if download_file(url, dest_path):
            success_count += 1

    print("\n" + "=" * 80)
    print(f"Download complete: {success_count}/{len(target_files)} files saved to {RAW_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()
