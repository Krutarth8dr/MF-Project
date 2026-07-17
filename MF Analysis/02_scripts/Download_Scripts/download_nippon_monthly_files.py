import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
import re
import pandas as pd

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "NIPPON"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://mf.nipponindiaim.com"

DISCLOSURE_PAGE = (
    "https://mf.nipponindiaim.com/"
    "investor-service/downloads/"
    "factsheet-portfolio-and-other-disclosures"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    )
}
# ==============================================================================
# GET MONTHLY PORTFOLIO LINKS
# ==============================================================================

# ==============================================================================
# GET MONTHLY PORTFOLIO LINKS
# ==============================================================================


def get_monthly_portfolio_links():
    """
    Reads the Nippon disclosures page and returns only the
    Monthly Portfolio files from October 2024 onwards.
    """

    print("=" * 90)
    print("Reading Nippon Disclosures Page")
    print("=" * 90)

    response = requests.get(
        DISCLOSURE_PAGE,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    portfolio_links = []

    TARGET_START = pd.Timestamp("2024-10-01")

    month_pattern = re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
        re.IGNORECASE,
    )

    labels = soup.find_all("label", class_="lhsLbl")

    for label in labels:

        title = label.get_text(" ", strip=True)

        if not title:
            continue

        title_upper = title.upper()

        # ------------------------------------------------------------
        # Ignore unwanted disclosures
        # ------------------------------------------------------------

        if "FORTNIGHTLY" in title_upper:
            continue

        if "MONTHLY PORTFOLIO" not in title_upper:
            continue

        match = month_pattern.search(title)

        if not match:
            continue

        month_name, year = match.groups()

        portfolio_date = pd.to_datetime(
            f"1 {month_name} {year}",
            errors="coerce",
        )

        if pd.isna(portfolio_date):
            continue

        if portfolio_date < TARGET_START:
            continue

        rhs_label = label.find_next_sibling(
            "label",
            class_="rhsLbl",
        )

        if rhs_label is None:
            continue

        link = rhs_label.find(
            "a",
            class_="xls",
        )

        if link is None:
            continue

        href = link.get("href")

        if not href:
            continue

        file_url = urljoin(
            BASE_URL,
            href,
        )

        file_name = Path(href).name

        portfolio_links.append(
            (
                portfolio_date,
                file_name,
                file_url,
            )
        )

    portfolio_links.sort(key=lambda x: x[0])

    print(f"Found {len(portfolio_links)} monthly portfolio files.\n")

    return [(file_name, file_url) for _, file_name, file_url in portfolio_links]


# ==============================================================================
# DOWNLOAD FILES
# ==============================================================================


def download_monthly_portfolios():

    portfolio_links = get_monthly_portfolio_links()

    downloaded = 0
    skipped = 0
    broken = 0

    print("=" * 90)
    print("Downloading Monthly Portfolio Files")
    print("=" * 90)

    for file_name, file_url in portfolio_links:

        output_file = RAW_FOLDER / file_name

        if output_file.exists():

            print(f"Skipping : {file_name}")

            skipped += 1
            continue

        print(f"Downloading : {file_name}")

        response = requests.get(
            file_url,
            headers=HEADERS,
            timeout=60,
        )

        if response.status_code != 200:
            print(f"broken Link : {file_name}")
            broken += 1
            continue

        with open(output_file, "wb") as file:

            file.write(response.content)

        downloaded += 1

    print()
    print("=" * 90)
    print("Download Summary")
    print("=" * 90)
    print(f"New Files Downloaded : {downloaded}")
    print(f"Already Present      : {skipped}")
    print(f"Broken Links         : {broken}")
    print(f"Total Files Found    : {len(portfolio_links)}")

    return downloaded
# ==============================================================================
# MAIN
# ==============================================================================


def main():

    print()
    print("=" * 90)
    print("NIPPON MONTHLY PORTFOLIO DOWNLOADER")
    print("=" * 90)
    print()

    try:

        downloaded = download_monthly_portfolios()

        print()

        if downloaded == 0:

            print("No new monthly portfolio files found.")
            print("Your local folder is already up to date.")

        else:

            print("Download completed successfully.")

        print()
        print(f"Output Folder : {RAW_FOLDER}")

    except Exception as e:

        print()
        print("=" * 90)
        print("ERROR")
        print("=" * 90)
        print(e)

        raise


# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":
    main()
