import re
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

import requests

# ==============================================================================
# CONFIGURATION
# ==============================================================================

OUTPUT_DIR = Path(r"D:\MF Project\MF Analysis\01_raw_files\Aditya Birla")

TEMP_DIR = OUTPUT_DIR / "_temp"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

TEMP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

API_URL = (
    "https://mutualfund.adityabirlacapital.com/"
    "postlogin/CustomApi/Resources/FactsheetAccordionById"
)

PARAMS = {
    "id": "3ccab227-9de5-4494-b78d-2b4f7c0c054a",
    "ctype": "/sitecore/content/Root/BSL/Library/Lists/FAQ/Customer Types/Individual",
    "month": "",
    "year": "0",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36",
    "Referer": "https://mutualfund.adityabirlacapital.com/forms-and-downloads/portfolio",
}


# ==============================================================================
# FETCH PORTFOLIO LIST
# ==============================================================================


def get_portfolios():

    print("=" * 100)
    print("Fetching Portfolio List")
    print("=" * 100)

    response = requests.get(
        API_URL,
        params=PARAMS,
        headers=HEADERS,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    portfolios = data["AccordionList"]

    print(f"Found {len(portfolios)} portfolios.\n")

    return portfolios


# ==============================================================================
# DOWNLOAD ZIP
# ==============================================================================


def download_zip(url):

    # Replace dead Azure CDN hostname
    url = url.replace(
        "https://abcscprod.azureedge.net", "https://mutualfund.adityabirlacapital.com"
    )

    print("Downloading:")
    print(url)

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=120,
        stream=True,
    )

    response.raise_for_status()

    zip_path = OUTPUT_DIR / "temp.zip"

    with open(zip_path, "wb") as file:

        for chunk in response.iter_content(8192):

            if chunk:
                file.write(chunk)

    return zip_path


# ==============================================================================
# EXTRACT EXCEL FILE
# ==============================================================================


def extract_excel(zip_path):

    shutil.rmtree(
        TEMP_DIR,
        ignore_errors=True,
    )

    TEMP_DIR.mkdir(exist_ok=True)

    with zipfile.ZipFile(zip_path) as zip_file:

        zip_file.extractall(TEMP_DIR)

    excel_files = []

    for file in TEMP_DIR.rglob("*"):

        if file.suffix.lower() in [ 
            ".xls", 
            ".xlsx", 
            ".xlsm" 
            ]:

            excel_files.append(file)

    if not excel_files:

        return None

    # Prefer files beginning with SEBI

    for file in excel_files:

        if file.name.upper().startswith("SEBI"):

            return file

    # Otherwise return first Excel file

    return excel_files[0]


# ==============================================================================
# OUTPUT FILE NAME
# ==============================================================================


def output_filename(title, extension):

    date_text = title.replace("Monthly Portfolios as on ", "")

    date_text = date_text.replace(",", "")

    date_text = date_text.replace(" ", "-")

    return f"Aditya_Birla_Monthly_Portfolio_{date_text}" f"{extension}"


# ==============================================================================
# MAIN
# ==============================================================================


def main():

    portfolios = get_portfolios()

    print("=" * 100)
    print("Downloading Files")
    print("=" * 100)

    START_DATE = datetime(2024, 10, 1)

    for portfolio in portfolios:

        title = portfolio["ResourceLink"]

        date_text = title.replace("Monthly Portfolios as on ", "")

        portfolio_date = datetime.strptime(date_text, "%B %d, %Y")

        if portfolio_date < START_DATE:

            print("\nReached October 2024. Stopping download.")
            break

        destination_xls = OUTPUT_DIR / output_filename(title, ".xls")
        destination_xlsx = OUTPUT_DIR / output_filename(title, ".xlsx")
        destination_xlsm = OUTPUT_DIR / output_filename(title, ".xlsm")

        if (
            destination_xls.exists()
            or destination_xlsx.exists()
            or destination_xlsm.exists()
        ):

            print(f"{title}")
            print("Already downloaded. Skipping.\n")
            continue

        print(title)

        try:

            zip_path = download_zip(portfolio["pdfUrl"])

            excel_file = extract_excel(zip_path)

            if excel_file is None:

                print("No Excel file found.\n")
                continue

            destination = OUTPUT_DIR / output_filename(
                title,
                excel_file.suffix,
            )

            shutil.move(
                excel_file,
                destination,
            )

            print(f"Saved -> {destination.name}\n")

        except Exception as e:

            print(f"ERROR : {e}\n")

        finally:

            temp_zip = OUTPUT_DIR / "temp.zip"

            if temp_zip.exists():
                temp_zip.unlink()

            shutil.rmtree(
                TEMP_DIR,
                ignore_errors=True,
            )




if __name__ == "__main__":

    main()
