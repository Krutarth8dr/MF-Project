import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "INVESCO"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

CLASSIFICATION = "equity"
START_YEAR = 2024
START_MONTH = 10
END_YEAR = datetime.now().year
TIMEOUT = 60
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}

MONTH_FIELDS = [
    ("Jan", "JanUrl", "JanName", 1),
    ("Feb", "FebUrl", "FebName", 2),
    ("Mar", "MarUrl", "MarName", 3),
    ("Apr", "AprUrl", "AprName", 4),
    ("May", "MayUrl", "MayName", 5),
    ("Jun", "JunUrl", "JunName", 6),
    ("Jul", "JulUrl", "JulName", 7),
    ("Aug", "AugUrl", "AugName", 8),
    ("Sep", "SepUrl", "SepName", 9),
    ("Oct", "OctUrl", "OctName", 10),
    ("Nov", "NovUrl", "NovName", 11),
    ("Dec", "DecUrl", "DecName", 12),
]

API_URL = "https://invescomutualfund.com/api/CompleteMonthlyHoldings"


# ============================================================================
# HELPERS
# ============================================================================


def print_separator(character="=", width=100):
    print(character * width)


def sanitize_filename(value: str) -> str:
    value = unquote(value)
    for invalid in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
        value = value.replace(invalid, "-")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def get_api_url(year: int) -> str:
    return f"{API_URL}?year={year}&classification={CLASSIFICATION}"


def fetch_year_data(year: int):
    print(f"Fetching Invesco equity holdings data for {year}...")
    response = requests.get(get_api_url(year), headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected API response for year {year}: expected list, got {type(data)}")
    return data


def build_save_path(year: int, month: int, fund_name: str, url: str) -> Path:
    folder = RAW_FOLDER / str(year) / f"{month:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    extension = Path(urlparse(url).path).suffix or ".xlsx"
    filename = sanitize_filename(f"{fund_name} - {year}-{month:02d}{extension}")
    return folder / filename


def get_file_entries(year: int, fund_record: dict):
    entries = []
    fund_name = fund_record.get("Name") or "Unknown Fund"
    fund_name = re.sub(r"\s+", " ", fund_name).strip()
    for _, url_key, name_key, month_number in MONTH_FIELDS:
        file_url = fund_record.get(url_key, "")
        month_name = fund_record.get(name_key, "")
        if not file_url or not month_name or month_name.strip() == "-":
            continue
        entries.append((fund_name, month_number, month_name.strip(), file_url))
    return entries


def download_file(url: str, save_path: Path) -> bool:
    if save_path.exists():
        print(f"Skipping existing file: {save_path}")
        return False
    print(f"Downloading {save_path.name}")
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
    response.raise_for_status()
    with open(save_path, "wb") as output_file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                output_file.write(chunk)
    return True


# ============================================================================
# MAIN
# ============================================================================


def main():
    print_separator()
    print("Downloading Invesco Equity Monthly Holdings Files")
    print_separator()

    downloaded_count = 0
    skipped_count = 0
    total_candidates = 0

    for year in range(START_YEAR, END_YEAR + 1):
        try:
            records = fetch_year_data(year)
        except Exception as error:
            print(f"Failed to fetch year {year}: {error}")
            continue

        if not records:
            print(f"No equity records found for {year}")
            continue

        for record in records:
            entries = get_file_entries(year, record)
            for fund_name, month_number, month_name, file_url in entries:
                if year == START_YEAR and month_number < START_MONTH:
                    continue

                total_candidates += 1
                save_path = build_save_path(year, month_number, fund_name, file_url)
                try:
                    if download_file(file_url, save_path):
                        downloaded_count += 1
                    else:
                        skipped_count += 1
                except Exception as error:
                    print(f"ERROR downloading {fund_name} {year}-{month_number:02d}: {error}")

    print_separator()
    print(f"Total files found  : {total_candidates}")
    print(f"Downloaded         : {downloaded_count}")
    print(f"Skipped existing   : {skipped_count}")
    print(f"Output root        : {RAW_FOLDER}")
    print_separator()


if __name__ == "__main__":
    main()
