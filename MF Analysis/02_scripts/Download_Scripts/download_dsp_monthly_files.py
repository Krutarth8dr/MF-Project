import requests
import zipfile
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "DSP"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

DISCLOSURE_URL = "https://www.dspim.com/mandatory-disclosures/portfolio-disclosures"

START_DATE = datetime(2026, 6, 30)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 60

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def print_separator(title=None):

    print("\n" + "=" * 100)

    if title:
        print(title)
        print("=" * 100)

def download_file(url, output_path):
    """
    Downloads a file from the given URL.
    """

    response = requests.get(
        url,
        headers=HEADERS,
        stream=True,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    with open(output_path, "wb") as file:

        for chunk in response.iter_content(chunk_size=8192):

            if chunk:

                file.write(chunk)

def extract_zip(zip_path):
    """
    Extracts a ZIP into a folder with the same name
    and deletes the ZIP afterwards.
    """

    zip_path = Path(zip_path)

    extract_folder = zip_path.with_suffix("")

    if extract_folder.exists():

        print(f"Already extracted : {extract_folder.name}")

        if zip_path.exists():
            zip_path.unlink()

        return

    extract_folder.mkdir()

    with zipfile.ZipFile(zip_path, "r") as zip_ref:

        zip_ref.extractall(extract_folder)

    zip_path.unlink()

    print(f"Extracted : {extract_folder.name}")

def already_downloaded(zip_filename):
    """
    Returns True if the ZIP has already been
    extracted.
    """

    folder = RAW_FOLDER / Path(zip_filename).stem

    return folder.exists()

# ==============================================================================
# MAIN
# ==============================================================================

def main():

    print_separator("DSP Monthly Portfolio Downloader")

    print("Downloading disclosure page...")

    response = requests.get(
        DISCLOSURE_URL,
        headers=HEADERS,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )
    # --------------------------------------------------------------------------
    # Locate Month End Portfolio Disclosures section
    # --------------------------------------------------------------------------

    month_end_section = None

    for section in soup.find_all("details", class_="pd-section-details"):

        summary = section.find("summary")

        if summary is None:
            continue

        if "Month End Portfolio Disclosures" in summary.get_text(strip=True):

            month_end_section = section
            break

    if month_end_section is None:
        raise ValueError(
            "Could not locate the 'Month End Portfolio Disclosures' section."
        )

    print("Month End Portfolio section found.")

    # --------------------------------------------------------------------------
    # Locate portfolio links
    # --------------------------------------------------------------------------

    body = month_end_section.find(
        "div",
        class_="pd-section-body",
    )

    if body is None:
        raise ValueError("Could not locate the portfolio disclosure body.")

    portfolio_links = []

    for link in body.find_all("a"):

        text = link.get_text(strip=True)

        if not text.startswith("Portfolio Details as on"):
            continue

        url = link.get("href")

        if not url:
            continue

        date_text = text.replace(
            "Portfolio Details as on",
            "",
        ).strip()

        parsed = False

        for fmt in ("%B %d, %Y", "%B %d %Y"):

            try:

                portfolio_date = datetime.strptime(
                    date_text,
                    fmt,
                )

                parsed = True
                break

            except ValueError:
                pass

        if not parsed:
            raise ValueError(f"Could not parse portfolio date: {date_text}")

        # Website is sorted newest -> oldest.
        # Stop once we reach months before October 2024.
        if portfolio_date < START_DATE:
            break

        portfolio_links.append(
            {
                "title": text,
                "url": url,
                "date": portfolio_date,
            }
        )

    print(f"Found {len(portfolio_links)} monthly portfolio files.")

    portfolio_links = sorted(
        portfolio_links,
        key=lambda x: x["date"],
        reverse=True,
    )

    # --------------------------------------------------------------------------
    # Download monthly portfolio files
    # --------------------------------------------------------------------------

    downloaded = 0
    skipped = 0

    for portfolio in portfolio_links:

        title = portfolio["title"]
        url = portfolio["url"]

        zip_filename = Path(url).name
        zip_path = RAW_FOLDER / zip_filename

        print("\n" + "-" * 100)
        print(title)

        if already_downloaded(zip_filename):

            print("Already downloaded.")

            skipped += 1

            continue

        print("Downloading...")

        try:

            download_file(
                url,
                zip_path,
            )

            print("Download complete.")

            print("Extracting...")

            extract_zip(zip_path)

            downloaded += 1

        except Exception as e:

            print(f"ERROR : {e}")

            if zip_path.exists():
                zip_path.unlink()

            continue

    print_separator("Download Complete")

    print(f"Downloaded : {downloaded}")
    print(f"Skipped     : {skipped}")
    print(f"Location    : {RAW_FOLDER}")

# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":

    main()
