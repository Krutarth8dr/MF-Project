import os
import zipfile
import subprocess
from urllib.parse import quote
import sys
from pathlib import Path

import requests


# =========================
# SETTINGS
# =========================

BASE_DOWNLOAD_URL = "https://www.icicipruamc.com"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ICICI_FOLDER = str(PROJECT_ROOT / "01_raw_files" / "ICICI")

PYTHON_EXE = sys.executable

CLEAN_SCRIPT = str(PROJECT_ROOT / "02_scripts" / "clean_icici_all_funds.py")
MATRIX_SCRIPT = str(PROJECT_ROOT / "02_scripts" / "create_icici_matrix.py")

# Change this every month
TARGET_MONTH = "April"
TARGET_YEAR = 2026

# If folder already exists, skip download/extract and directly refresh matrix
SKIP_IF_ALREADY_EXTRACTED = True


# =========================
# MONTH MAP
# =========================

MONTH_SHORT = {
    "January": "Jan",
    "February": "Feb",
    "March": "Mar",
    "April": "Apr",
    "May": "May",
    "June": "Jun",
    "July": "Jul",
    "August": "Aug",
    "September": "Sep",
    "October": "Oct",
    "November": "Nov",
    "December": "Dec",
}


# =========================
# HELPER FUNCTIONS
# =========================

def build_icici_zip_url(month_name, year):
    month_short = MONTH_SHORT[month_name]

    relative_path = (
        f"/downloads/Files/Monthly Portfolio Disclosures/"
        f"{year}/{month_short}/"
        f"Monthly-Portfolio-Disclosure-{month_name}-{year}.zip"
    )

    encoded_path = quote(relative_path, safe="/-.")
    return BASE_DOWNLOAD_URL + encoded_path


def download_file(url, save_path):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/zip,application/octet-stream,*/*",
    }

    print("Downloading ZIP:")
    print(url)

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=180,
            allow_redirects=True
        )

        response.raise_for_status()

        print("Final URL:")
        print(response.url)

        content_type = response.headers.get("Content-Type", "")
        print("Content-Type:", content_type)

        with open(save_path, "wb") as f:
            f.write(response.content)

        print("Saved ZIP:")
        print(save_path)

        return True

    except requests.exceptions.ConnectionError:
        print()
        print("ERROR: Could not connect to ICICI archive/download server.")
        print("ICICI is redirecting this file to archive.icicipruamc.com,")
        print("but your PC/DNS cannot resolve that domain.")
        print()
        print("URL tried:")
        print(url)
        print()
        print("You can manually download the ZIP and keep it here:")
        print(save_path)
        return False

    except requests.exceptions.HTTPError as e:
        print()
        print("ERROR: ICICI returned HTTP error.")
        print("URL tried:")
        print(url)
        print("Error:", e)
        return False


def extract_zip(zip_path, extract_folder):
    print()
    print("Extracting ZIP to:")
    print(extract_folder)

    os.makedirs(extract_folder, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_folder)

    print("Extraction completed.")


def run_script(script_path, description):
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    print()
    print(description)
    print("-" * 90)

    subprocess.run([PYTHON_EXE, script_path], check=True)


# =========================
# MAIN PROCESS
# =========================

def main():
    os.makedirs(RAW_ICICI_FOLDER, exist_ok=True)

    if TARGET_MONTH not in MONTH_SHORT:
        print("ERROR: Invalid TARGET_MONTH:", TARGET_MONTH)
        print("Use full month name like April, May, June.")
        return

    folder_name = f"Monthly-Portfolio-Disclosure-{TARGET_MONTH}-{TARGET_YEAR}"
    extract_folder = os.path.join(RAW_ICICI_FOLDER, folder_name)

    zip_filename = f"{folder_name}.zip"
    zip_path = os.path.join(RAW_ICICI_FOLDER, zip_filename)

    print("=" * 90)
    print("ICICI Monthly Portfolio Download + Matrix Refresh")
    print("=" * 90)
    print("Target Month :", TARGET_MONTH)
    print("Target Year  :", TARGET_YEAR)
    print("ZIP Path     :", zip_path)
    print("Extract To   :", extract_folder)
    print("=" * 90)

    # CASE 1: Extracted folder already exists
    if os.path.exists(extract_folder) and SKIP_IF_ALREADY_EXTRACTED:
        print()
        print("Folder already exists. Skipping download/extract:")
        print(extract_folder)

    else:
        # CASE 2: ZIP already exists locally
        if os.path.exists(zip_path):
            print()
            print("ZIP already exists locally. Skipping download:")
            print(zip_path)
            extract_zip(zip_path, extract_folder)

        else:
            # CASE 3: Need to download ZIP
            zip_url = build_icici_zip_url(TARGET_MONTH, TARGET_YEAR)

            download_success = download_file(zip_url, zip_path)

            if not download_success:
                print()
                print("Download failed. Cleaning/matrix refresh stopped.")
                print()
                print("Manual workaround:")
                print("1. Download ZIP manually from ICICI website.")
                print("2. Save it as:")
                print(zip_path)
                print("3. Run this script again.")
                return

            extract_zip(zip_path, extract_folder)

    run_script(
        CLEAN_SCRIPT,
        "Step 1: Cleaning ICICI all funds"
    )

    run_script(
        MATRIX_SCRIPT,
        "Step 2: Creating ICICI final matrix"
    )

    print()
    print("=" * 90)
    print("ICICI download, extraction, cleaning, and matrix refresh completed successfully.")
    print("=" * 90)


if __name__ == "__main__":
    main()