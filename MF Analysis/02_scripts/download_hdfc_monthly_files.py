import os
import json
import re
import subprocess
from urllib.parse import unquote
from pathlib import Path
from wsgiref import headers
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# =========================
# SETTINGS
# =========================

HDFC_MONTHLY_URL = "https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BAT_FILE = str(PROJECT_ROOT / "run_hdfc_refresh.bat")

# Set the month-end date you want to download
TARGET_DATE_TEXT = "31 May 2026"

day, month_name, year = TARGET_DATE_TEXT.split()

month_map = {
    "January": "1",
    "February": "2",
    "March": "3",
    "April": "4",
    "May": "5",
    "June": "6",
    "July": "7",
    "August": "8",
    "September": "9",
    "October": "10",
    "November": "11",
    "December": "12",
}

FUNDS = {
    "Balanced Advantage Fund": {
        "match": "HDFC Balanced Advantage Fund",
        "folder": str(PROJECT_ROOT / "01_raw_files" / "HDFC" / "HDFC Balanced Advantage Fund")
    },
    "Focused Fund": {
        "match": "HDFC Focused Fund",
        "folder": str(PROJECT_ROOT / "01_raw_files" / "HDFC" / "HDFC Focused Fund")
    },
    "Flexi Cap Fund": {
        "match": "HDFC Flexi Cap Fund",
        "folder": str(PROJECT_ROOT / "01_raw_files" / "HDFC" / "HDFC Flexi Cap")
    },
    "Multi Cap Fund": {
        "match": "HDFC Multi Cap Fund",
        "folder": str(PROJECT_ROOT / "01_raw_files" / "HDFC" / "HDFC Multi Cap")
    },
    "Large Cap Fund": {
        "match": "HDFC Large Cap Fund",
        "folder": str(PROJECT_ROOT / "01_raw_files" / "HDFC" / "HDFC Large Cap")
    },
}


# =========================
# FUNCTIONS
# =========================

def clean_filename(filename):
    filename = unquote(filename)
    filename = filename.replace("/", "-").replace("\\", "-")
    return filename.strip()


def get_hdfc_files_from_page_old():
    print("Opening HDFC monthly portfolio page...")

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(HDFC_MONTHLY_URL, headers=headers, timeout=60)
    # response.raise_for_status()
    print(response.text[:1000])
    soup = BeautifulSoup(response.text, "html.parser")

    next_data_script = soup.find("script", id="__NEXT_DATA__")

    if not next_data_script:
        raise Exception("Could not find __NEXT_DATA__ JSON in HDFC page.")

    data = json.loads(next_data_script.string)

    files = (
        data
        .get("props", {})
        .get("pageProps", {})
        .get("portfolioDataResponse", {})
        .get("data", {})
        .get("files", [])
    )

    if not files:
        raise Exception("No monthly portfolio files found in HDFC page JSON.")

    return files


def get_hdfc_files_from_page():
    print("Getting HDFC monthly portfolio files...")

    url = "https://cms.hdfcfund.com/en/hdfc/api/v2/disclosures/monthfortportfolio"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0.0.0 Safari/537.36"
        ),
        "Origin": "https://www.hdfcfund.com",
        "Referer": "https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio",
        "X-Requested-With": "XMLHttpRequest",
    }

    target_date = datetime.strptime(TARGET_DATE_TEXT, "%d %B %Y")

    payload = {
        "year": str(target_date.year),
        "month": str(target_date.month),
        "type": "monthly"
    }

    response = requests.post(url, headers=headers, data=payload, timeout=60)

    print(response.status_code)
    print(response.text[:1000])

    response.raise_for_status()

    data = response.json()

    files = data["data"]["files"]

    return files


def find_required_file(files, fund_match_text, target_date_text):
    matches = []

    for item in files:
        title = item.get("title", "")
        file_info = item.get("file", {})
        filename = file_info.get("filename", "")
        url = file_info.get("url", "")
        extension = item.get("extension", "")

        check_text = f"{title} {filename}"

        if extension.lower() != "xlsx":
            continue

        if fund_match_text.lower() in check_text.lower() and target_date_text.lower() in check_text.lower():
            matches.append({
                "title": title,
                "filename": clean_filename(filename or title),
                "url": url
            })

    return matches


def download_file(url, save_path):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers, timeout=120)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        f.write(response.content)


# =========================
# MAIN
# =========================

def main():
    files = get_hdfc_files_from_page()

    print(f"Total files found on HDFC page: {len(files)}")
    print()
    print("Searching required files for:", TARGET_DATE_TEXT)
    print("=" * 80)

    selected_files = {}

    for fund_display_name, info in FUNDS.items():
        matches = find_required_file(
            files,
            info["match"],
            TARGET_DATE_TEXT
        )

        if len(matches) == 0:
            print(f"❌ Missing: {fund_display_name}")
            selected_files[fund_display_name] = None

        elif len(matches) > 1:
            print(f"⚠ Multiple matches found for: {fund_display_name}")
            for m in matches:
                print("   ", m["filename"])
            selected_files[fund_display_name] = None

        else:
            selected_files[fund_display_name] = matches[0]
            print(f"✅ {fund_display_name}: {matches[0]['filename']}")

    print("=" * 80)

    missing_or_problem = [
        fund for fund, selected in selected_files.items()
        if selected is None
    ]

    if missing_or_problem:
        print()
        print("Download stopped because some files are missing or unclear.")
        print("Please check these funds:")
        for fund in missing_or_problem:
            print("-", fund)
        return

    print()
    confirm = input("All 5 files found. Download now? Type YES to continue: ")

    if confirm.strip().upper() != "YES":
        print("Download cancelled.")
        return

    downloaded = 0
    skipped = 0

    for fund_display_name, selected in selected_files.items():
        folder_path = FUNDS[fund_display_name]["folder"]
        os.makedirs(folder_path, exist_ok=True)

        filename = selected["filename"]
        save_path = os.path.join(folder_path, filename)

        print()
        print(f"Fund: {fund_display_name}")
        print(f"File: {filename}")

        if os.path.exists(save_path):
            print("Already exists. Skipping.")
            skipped += 1
            continue

        download_file(selected["url"], save_path)
        print(f"Downloaded to: {save_path}")
        downloaded += 1

    print()
    print("=" * 80)
    print("Download Summary")
    print("=" * 80)
    print(f"Downloaded: {downloaded}")
    print(f"Skipped existing: {skipped}")

    print()
    confirm_refresh = input("Run HDFC matrix refresh BAT now? Type YES to continue: ")

    if confirm_refresh.strip().upper() == "YES":
        subprocess.run(BAT_FILE, shell=True, check=True)
        print("HDFC matrix refreshed successfully.")
    else:
        print("BAT refresh skipped.")


if __name__ == "__main__":
    main()
