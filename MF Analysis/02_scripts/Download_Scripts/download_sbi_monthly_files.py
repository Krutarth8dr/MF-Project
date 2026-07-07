import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime
import re

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOWNLOAD_FOLDER = PROJECT_ROOT / "01_raw_files" / "SBI"
DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

API_URL = "https://www.sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/137.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.sbimf.com/portfolio-disclosures",
}

PAYLOAD = {
    "FundId": "",
    "PSYear": "",
    "PSMonth": "",
    "PSFrequency": "Monthly",
}


# ==============================================================================
# MAIN
# ==============================================================================
START_DATE = datetime(2024, 4, 1)


def get_file_date(filename):
    """
    Extracts the date from filenames like:
    all-schemes-monthly-portfolio---as-on-30th-sep-2025.xlsx
    all-schemes-monthly-portfolio---as-on-31st-may-2026.xlsx
    """

    match = re.search(r"as-on-(\d+)(?:st|nd|rd|th)-([a-z]+)-(\d{4})", filename.lower())

    if not match:
        return None

    day = match.group(1)
    month = match.group(2).title()
    year = match.group(3)

    date_string = f"{day}-{month}-{year}"

    # Try abbreviated month first (Jan, Feb, Sep...)
    try:
        return datetime.strptime(date_string, "%d-%b-%Y")
    except ValueError:
        pass

    # Try full month (January, February...)
    try:
        return datetime.strptime(date_string, "%d-%B-%Y")
    except ValueError:
        return None


def main():

    print("=" * 90)
    print("Downloading SBI Monthly Portfolio Files")
    print("=" * 90)

    response = requests.post(
        API_URL,
        headers=HEADERS,
        data=PAYLOAD,
        timeout=120,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    links = soup.find_all("a", href=True)


    excel_links = []

    for link in links:

        href = link["href"]

        if ".xlsx" not in href.lower():
            continue

        filename = href.split("/")[-1].split("?")[0]
        print(filename)
        if not (
            filename.lower().startswith("all-schemes-monthly-portfolio")
            or
            filename.lower().startswith("all-scheme-monthly-portfolio")
        ):
            continue

        excel_links.append((filename, href))

    print("\nParsed Dates:\n")

    excel_links.sort(key=lambda x: get_file_date(x[0]))
    print(f"\nFound {len(excel_links)} monthly files.\n")

    downloaded = 0
    skipped = 0

    for filename, url in excel_links:

        output_file = DOWNLOAD_FOLDER / filename

        if output_file.exists():
            print(f"Skipping: {filename}")
            skipped += 1
            continue

        file_date = get_file_date(filename)

        if file_date is None:
            continue

        if file_date < START_DATE:
            continue

        print(f"Downloading: {filename}")

        r = requests.get(url, headers=HEADERS, timeout=300)
        r.raise_for_status()

        output_file.write_bytes(r.content)

        downloaded += 1

    print("\n" + "=" * 90)
    print("Done")
    print("=" * 90)
    print("Downloaded :", downloaded)
    print("Skipped    :", skipped)
    print("Folder     :", DOWNLOAD_FOLDER)


if __name__ == "__main__":
    main()
