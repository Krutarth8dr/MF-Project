from pathlib import Path
from urllib import response
import requests
import uuid
import shutil
import json


# ==============================================================================
# CONFIGURATION
# ==============================================================================

RAW_FOLDER = Path(__file__).resolve().parents[2] / "01_raw_files" / "AXIS"

RAW_FOLDER.mkdir(
    parents=True,
    exist_ok=True,
)

TOKEN_URL = "https://www.axismf.com/cms/token"

DOCUMENT_URL = "https://www.axismf.com/cms/get-scheme-documents"

MONTHS = [
    (1, "January"),
    (2, "February"),
    (3, "March"),
    (4, "April"),
    (5, "May"),
    (6, "June"),
    (7, "July"),
    (8, "August"),
    (9, "September"),
    (10, "October"),
    (11, "November"),
    (12, "December"),
]

YEARS = [
    2024,
    2025,
    2026,
]

START_YEAR = 2026
START_MONTH = 7  # July

END_YEAR = 2026
END_MONTH = 7  # July
TIMEOUT = 60
# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def print_separator(character="=", width=100):
    print(character * width)


# ==============================================================================
# GET JWT TOKEN
# ==============================================================================


def get_token():
    """
    Requests a fresh Bearer token from Axis Mutual Fund.
    """

    print()
    print_separator()
    print("REQUESTING AUTH TOKEN")
    print_separator()

    response = requests.post(
        TOKEN_URL,
        json={},
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    response_json = response.json()
    

    if response_json.get("status") != "success":
        raise RuntimeError("Token request failed.")

    token = response_json["data"]["token"]

    print("Token received successfully.")

    return token


# ==============================================================================
# CREATE REQUEST HEADERS
# ==============================================================================


def create_headers(token):
    """
    Creates request headers for the document API.
    """

    browser_id = "ee45d65c-c79b-45a0-b463-2b228ee0c827"

    headers = {
        "Authorization": token,
        "Browser-Id": browser_id,
        "Content-Type": "application/json",
        "Accept": "*/*",
    }

    return headers
# ==============================================================================
# GET DOCUMENT LIST
# ==============================================================================


def get_document_list(token, year, month):
    """
    Fetches all documents available for a given month/year.
    """

    headers = create_headers(token)

    payload = {
        "sdType": "yearMonthSchemeDocs",
        "sdID": "sdMonthSchemePortfolio",
        "year": str(year),
        "month": month,
        "schemeCode": "Consolidated",
    }

    response = requests.post(
        DOCUMENT_URL,
        headers=headers,
        json=payload,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    response_json = response.json()

    documents = response_json["data"].get("documentList", [])

    documents = response_json["data"]["documentList"]

    for i, doc in enumerate(documents, 1):

        print()
        print(f"Document {i}")

        print(json.dumps(doc, indent=4))

        if response_json.get("status") != "success":
            raise RuntimeError(f"Axis API returned status '{response_json.get('status')}'")

    return response_json["data"]["documentList"]


# ==============================================================================
# FIND MONTHLY PORTFOLIO FILE
# ==============================================================================


def find_monthly_portfolio(document_list):
    """
    Returns the Monthly Portfolio Excel file from the document list.
    """

    for document in document_list:

        document_name = document.get("documentName", "").strip()

        if "Monthly Portfolio" not in document_name:
            continue

        download_url = document.get("documentURL") or document.get("docuementURL")

        if not download_url:
            continue

        return {
            "name": document_name,
            "url": download_url,
            "date": document.get("documentPostedDate"),
        }

    return None


# ==============================================================================
# DOWNLOAD FILE
# ==============================================================================


def download_file(document):
    """
    Downloads a Monthly Portfolio workbook.
    """

    file_url = document["url"]

    file_name = file_url.split("/")[-1]

    output_file = RAW_FOLDER / file_name

    if output_file.exists():

        print(f"Already Exists : {file_name}")

        return False

    print(f"Downloading : {file_name}")

    response = requests.get(
        file_url,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    with open(output_file, "wb") as file:

        file.write(response.content)

    return True


# ==============================================================================
# MAIN
# ==============================================================================


def main():

    print_separator()
    print("Downloading Axis Monthly Portfolio Files")
    print_separator()

    token = get_token()

    downloaded = 0
    skipped = 0

    for year in YEARS:

        for month_number, month_name in MONTHS:

            # ----------------------------------------------------------
            # Respect configured date range
            # ----------------------------------------------------------

            if year == START_YEAR and month_number < START_MONTH:
                continue

            if year == END_YEAR and month_number > END_MONTH:
                continue

            print()
            print("-" * 100)
            print(f"{month_name} {year}")
            print("-" * 100)

            try:

                document_list = get_document_list(
                    token,
                    year,
                    month_name,
                )

                document = find_monthly_portfolio(document_list)

                if document is None:

                    print("No Monthly Portfolio found.")

                    continue

                if download_file(document):
                    downloaded += 1
                else:
                    skipped += 1

            except Exception as error:

                print(f"ERROR : {month_name} {year}")
                print(error)

    print()
    print_separator()
    print("DOWNLOAD SUMMARY")
    print_separator()

    print(f"Downloaded : {downloaded}")
    print(f"Skipped    : {skipped}")
    print(f"Folder     : {RAW_FOLDER}")

    print()
    print("Done.")


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    main()
