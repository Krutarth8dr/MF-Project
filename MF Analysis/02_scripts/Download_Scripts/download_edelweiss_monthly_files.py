import os
import sys
import time
import json
import base64
import hashlib
import hmac
import urllib.parse
from datetime import datetime
from pathlib import Path
from curl_cffi import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "Edelweiss"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.edelweissmf.com"
API_URL = "https://api.edelweissmf.com/edelweissmf/api/v1/mf/statutory-menus/single"

SECRET_KEY = "5b6714126d3149fbab994747b2633287"
HASH_KEY = "r4vcos0ejvndsow95n"

START_DATE = datetime(2024, 10, 1)
END_DATE = datetime(2026, 8, 31)

MONTH_MAP = {
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
    "dec": 12, "december": 12
}

# ==============================================================================
# CRYPTO & API HELPERS
# ==============================================================================

def bytes_to_key(data, salt, key_len=32, iv_len=16):
    dt = b''
    d = b''
    while len(dt) < key_len + iv_len:
        d = hashlib.md5(d + data + salt).digest()
        dt += d
    return dt[:key_len], dt[key_len:key_len + iv_len]


def decrypt_cryptojs(encrypted_b64, passphrase):
    raw = base64.b64decode(encrypted_b64)
    if raw[:8] != b'Salted__':
        raise ValueError('Invalid Salted__ prefix in ciphertext')
    salt = raw[8:16]
    ciphertext = raw[16:]
    key, iv = bytes_to_key(passphrase.encode('utf-8'), salt, 32, 16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode('utf-8')


def fetch_statutory_files():
    """Queries Edelweiss statutory API and returns decrypted file list."""
    try:
        ip = requests.get('https://api.ipify.org?format=json', timeout=5).json().get('ip', '103.0.123.175')
    except Exception:
        ip = '103.0.123.175'

    ts = str(int(time.time() * 1000))
    msg = (SECRET_KEY + ip + ts).encode('utf-8')
    key = HASH_KEY.encode('utf-8')
    dt_hex = hmac.new(key, msg, hashlib.sha256).hexdigest()

    headers = {
        'Origin': BASE_URL,
        'Referer': f"{BASE_URL}/",
        'Accept': 'application/json, text/plain, */*',
        'x-timestamp': ts,
        'x-ip-address': ip
    }

    params = {
        'type': 'STATUTORY',
        'fundType': 'MF',
        'menuName': 'Portfolio of scheme(s)'
    }

    session = requests.Session(impersonate='chrome124')
    response = session.get(API_URL, headers=headers, params=params, timeout=30)
    response.raise_for_status()

    body_enc = response.json().get('body', '')
    decrypted = decrypt_cryptojs(body_enc, dt_hex)
    data = json.loads(decrypted)
    return data.get('files', [])

# ==============================================================================
# MAIN DOWNLOAD PIPELINE
# ==============================================================================

def run_download():
    print("=" * 70)
    print("EDELWEISS MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
    print(f"Target Date Range: {START_DATE.strftime('%b %Y')} to {END_DATE.strftime('%b %Y')}")
    print(f"Raw Output Folder: {RAW_FOLDER}")
    print("=" * 70)

    print("\n[Step 1/3] Fetching file catalog from Edelweiss API...")
    files = fetch_statutory_files()
    print(f"Total files returned by API: {len(files)}")

    # Filter monthly files
    monthly_files = []
    for f in files:
        path = str(f.get('filePath', ''))
        filename = str(f.get('fileName', ''))
        path_lower = path.lower()

        # Must be monthly portfolio and not weekly/fortnightly/annual
        if ('monthly' in path_lower or 'monthly' in filename.lower()) and \
           ('weekly' not in path_lower) and ('fortnightly' not in path_lower) and \
           ('half' not in path_lower) and ('annual' not in path_lower):

            yr_str = str(f.get('year', '')).strip()
            mo_str = str(f.get('month', '')).strip().lower()

            try:
                yr = int(yr_str)
                mo = MONTH_MAP.get(mo_str)
                if yr and mo:
                    f_date = datetime(yr, mo, 1)
                    if START_DATE <= f_date <= END_DATE:
                        monthly_files.append((f_date, f))
            except Exception:
                continue

    # Sort chronologically
    monthly_files.sort(key=lambda x: x[0])
    print(f"Found {len(monthly_files)} monthly files matching target date range (Oct 2024 - Aug 2026).")

    print("\n[Step 2/3] Downloading monthly workbooks...")
    download_session = requests.Session(impersonate='chrome124')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Referer': f"{BASE_URL}/statutory/portfolio-of-schemes"
    }

    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    for f_date, f_meta in monthly_files:
        yr = f_date.year
        mo = f_date.month
        rel_path = f_meta.get('filePath', '')

        # Construct target directory: 01_raw_files/Edelweiss/<YYYY>/<MM>/
        target_dir = RAW_FOLDER / str(yr) / f"{mo:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = os.path.basename(rel_path)
        target_file = target_dir / filename

        month_label = f_date.strftime("%b %Y")

        if target_file.exists() and target_file.stat().st_size > 10000:
            print(f"  [SKIPPED] {month_label}: {filename} (Already exists, size: {target_file.stat().st_size:,} bytes)")
            skipped_count += 1
            continue

        file_url = BASE_URL + urllib.parse.quote(rel_path)
        print(f"  [DOWNLOADING] {month_label} -> {filename} ...", end="", flush=True)

        success = False
        for attempt in range(1, 4):
            try:
                r = download_session.get(file_url, headers=headers, timeout=60)
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(target_file, "wb") as out_f:
                        out_f.write(r.content)
                    print(f" DONE ({len(r.content):,} bytes)")
                    downloaded_count += 1
                    success = True
                    break
                else:
                    print(f" [Retry {attempt}: status {r.status_code}]", end="", flush=True)
                    time.sleep(2)
            except Exception as e:
                print(f" [Retry {attempt}: {e}]", end="", flush=True)
                time.sleep(2)

        if not success:
            print(" FAILED")
            failed_count += 1

    print("\n[Step 3/3] Download Summary:")
    print(f"  Total target months: {len(monthly_files)}")
    print(f"  Newly downloaded:    {downloaded_count}")
    print(f"  Already existed:     {skipped_count}")
    print(f"  Failed:              {failed_count}")
    print("=" * 70)

if __name__ == "__main__":
    run_download()
