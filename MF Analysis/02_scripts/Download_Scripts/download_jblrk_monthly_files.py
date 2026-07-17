import json
import re
import requests

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "JIO_BLACKROCK"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

DISCLOSURE_URL = (
    "https://www.jioblackrockamc.com/"
    "statutory-disclosure/disclosures/monthly-portfolio-disclosure"
)

HEADERS = {
    "Accept": "text/x-component",
    "Content-Type": "text/plain;charset=UTF-8",
    "Next-Action": "70db31784ed96088b0dc652fc7059d2263499a0b2d",
    "Origin": "https://www.jioblackrockamc.com",
    "Referer": DISCLOSURE_URL,
}

START_DATE = datetime(2025, 9, 1)

END_DATE = datetime(2026, 6, 30)

TARGET_TITLE = "JioBlackRock Mutual Fund-Monthly-Portfolio"

DOWNLOAD_PLAN = [
    (
        "FI2025-2026",
        [
            "September",
            "October",
            "November",
            "December",
            "January",
            "February",
            "March",
        ],
    ),
    (
        "FI2026-2027",
        [
            "April",
            "May",
            "June",
        ],
    ),
]


def clean_filename(name):
    """
    Removes characters that are invalid in Windows
    filenames.
    """

    return re.sub(
        r'[<>:"/\\|?*]',
        "",
        name,
    ).strip()

def download_file(url, output_file):
    """
    Downloads a workbook from the CDN.
    """

    response = requests.get(
        url,
        timeout=60,
    )

    response.raise_for_status()

    with open(output_file, "wb") as f:

        f.write(response.content)

def parse_response(response_text):
    """
    Debug parser.
    """

    print("=" * 100)
    print(response_text)
    print("=" * 100)

    return []

def fetch_month(
    session,
    fiscal_year,
    month,
):
    """
    Returns all records for one month.
    """

    response = session.post(
        DISCLOSURE_URL,
        headers=HEADERS,
        data=build_payload(
            fiscal_year,
            month,
        ),
        timeout=60,
    )

    response.raise_for_status()

    return parse_response(
        response.text,
    )

def is_target_record(record):
    """
    Returns True only for the Mutual Fund
    monthly portfolio workbook.
    """

    title = record["title"].lower().replace(" ", "")

    return "jioblackrockmutualfund-monthly-portfolio" in title

def get_output_file(record):
    """
    Returns the output path.
    """

    filename = record["title"] + record["file"]["ext"]

    filename = clean_filename(
        filename,
    )

    return RAW_FOLDER / filename

    browser = p.chromium.launch(
        headless=False,
    )

    page = browser.new_page()

    page.goto(
        DISCLOSURE_URL,
        wait_until="networkidle",
    )

    records = fetch_fiscal_year(
        page,
        "FI2025-2026",
    )

    print()

    print("=" * 100)

    print("Mutual Fund Files")

    print("=" * 100)

    for record in records:

        if is_target_record(record):

            print(record["title"])

            print(record["date"])

            print(record["file"]["url"])

            print()

    browser.close()

def create_session():
    """
    Creates a requests session using cookies
    from a Playwright browser session.
    """

    playwright = sync_playwright().start()

    browser = playwright.chromium.launch(
        headless=True,
    )

    page = browser.new_page()

    page.goto(
        DISCLOSURE_URL,
        wait_until="networkidle",
    )

    session = requests.Session()

    for cookie in page.context.cookies():

        session.cookies.set(
            cookie["name"],
            cookie["value"],
        )

    browser.close()

    playwright.stop()

    return session

def build_payload(
    fiscal_year,
    month,
):
    """
    Returns the payload required by the
    Next.js action.
    """

    return json.dumps(
        [
            "monthly-portfolio-disclosure",
            {
                "year": fiscal_year,
                "month": month,
                "date": "$undefined",
            },
            "MF",
        ]
    )

def parse_response(response_text):
    """
    Extracts the portfolio list from the
    streamed Next.js response.
    """

    for line in response_text.splitlines():

        if line.startswith("1:"):

            payload = json.loads(line[2:])

            return payload["data"]

    return []


def main():

    print("=" * 100)
    print("Jio BlackRock Monthly Portfolio Downloader")
    print("=" * 100)

    session = create_session()

    downloaded = 0

    for fiscal_year, months in DOWNLOAD_PLAN:

        print(f"\n{fiscal_year}")

        for month in months:

            print(f"  {month}")

            records = fetch_month(
                session,
                fiscal_year,
                month,
            )

            for record in records:

                if not is_target_record(record):

                    continue

                portfolio_date = datetime.strptime(
                    record["date"],
                    "%Y-%m-%d",
                )

                if portfolio_date < START_DATE:

                    continue

                output_file = get_output_file(
                    record,
                )

                if output_file.exists():

                    print(f"      Exists : {output_file.name}")

                    continue

                print(f"      Downloading : {output_file.name}")

                download_file(
                    record["file"]["url"],
                    output_file,
                )

                downloaded += 1

    print("\n" + "=" * 100)

    print(f"Downloaded : {downloaded}")

    print(f"Folder     : {RAW_FOLDER}")

    print("=" * 100)

if __name__ == "__main__":
    main()
