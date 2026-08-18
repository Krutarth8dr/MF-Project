"""Download monthly portfolio files from Quant Mutual.

This script downloads files from the QUANT monthly portfolio fund-wise
section on https://quantmutual.com/statutory-disclosures.
"""

from pathlib import Path
import argparse
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://quantmutual.com"
PAGE_URL = f"{BASE_URL}/statutory-disclosures"
SELECT_YEAR_URL = f"{BASE_URL}/statutorydisclosures.aspx/displaydisclouser1"
SELECT_MONTH_URL = f"{BASE_URL}/statutorydisclosures.aspx/displaydisclouser2"
CATEGORY_NAME = "MONTHLY PORTFOLIO - FUND - WISE"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MONTH_NAMES = [
    None,
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

FUND_CANONICAL = {
    "quant multi asset allocation fund",
    "quant multi cap fund",
    "quant large & mid cap fund",
    "quant small cap fund",
    "quant infrastructure fund",
    "quant flexi cap fund",
    "quant elss tax saver fund",
    "quant quantamental fund",
    "quant value fund",
    "quant large cap fund",
    "quant business cycle fund",
    "quant bfsi fund",
    "quant healthcare fund",
    "quant manufacturing fund",
    "quant teck fund",
    "quant momentum fund",
}

FUND_ALIASES = {
    "quant multi asset fund": "quant multi asset allocation fund",
    "quant mid cap fund": "quant multi cap fund",
}


def fetch_month_tabs(session: requests.Session, year: int) -> BeautifulSoup:
    payload = f"{{id:'{year}',cat:'{CATEGORY_NAME}'}}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json; charset=utf-8",
        "Referer": PAGE_URL,
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    response = session.post(SELECT_YEAR_URL, headers=headers, data=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    html = data.get("d", "")
    return BeautifulSoup(html, "html.parser")


def fetch_file_list(session: requests.Session, year: int, month: int) -> BeautifulSoup:
    payload = f"{{id:'{month}',cat:'{CATEGORY_NAME}',tab:'{year}'}}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json; charset=utf-8",
        "Referer": PAGE_URL,
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    response = session.post(SELECT_MONTH_URL, headers=headers, data=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    html = data.get("d", "")
    return BeautifulSoup(html, "html.parser")


def download_file(session: requests.Session, url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        print(f"Skipping existing file: {destination.name}")
        return
    response = session.get(url, timeout=120)
    response.raise_for_status()
    with open(destination, "wb") as f:
        f.write(response.content)
    print(f"Downloaded: {destination.name}")


def clean_filename(filename: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    cleaned = "".join(ch for ch in filename if ch not in invalid_chars)
    return cleaned.strip()


def download_monthly_files(output_dir: Path, year: int, month: int) -> None:
    output_root = output_dir / "QUANT" / f"{year}" / f"{month:02d}"
    output_root.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    print(f"Loading Quant Mutual page: {PAGE_URL}")
    page = session.get(PAGE_URL, timeout=60)
    page.raise_for_status()

    print(f"Fetching month tabs for year {year}...")
    month_soup = fetch_month_tabs(session, year)
    month_items = month_soup.find_all("li")
    if not month_items:
        raise RuntimeError("Unable to parse month tabs from Quant Mutual response.")

    available_months = {int(item.get('id')): item.get_text(strip=True) for item in month_items if item.get('id')}
    if month not in available_months:
        raise ValueError(
            f"Month {month} is not available for year {year}. Available months: {', '.join(available_months.values())}"
        )

    print(f"Selected month: {available_months[month]} {year}")

    print("Fetching file list...")
    file_soup = fetch_file_list(session, year, month)
    file_links = file_soup.find_all("a", href=True)
    if not file_links:
        raise RuntimeError("No files found for the selected Quant Mutual month.")

    downloaded = 0
    skipped = 0
    total_found = 0
    download_items: dict[str, dict[str, str]] = {}

    for link in file_links:
        href = link["href"].strip()
        title = link.get_text(strip=True) or Path(href).name
        if not href.lower().endswith(".xlsx"):
            continue

        normalized_title = title.strip().lower()
        if normalized_title in FUND_CANONICAL:
            canonical_title = normalized_title
        elif normalized_title in FUND_ALIASES:
            canonical_title = FUND_ALIASES[normalized_title]
        else:
            continue

        total_found += 1

        existing = download_items.get(canonical_title)
        if existing is not None:
            if normalized_title in FUND_CANONICAL and existing["normalized_title"] in FUND_ALIASES:
                download_items[canonical_title] = {
                    "href": href,
                    "title": title,
                    "normalized_title": normalized_title,
                }
            continue

        download_items[canonical_title] = {
            "href": href,
            "title": title,
            "normalized_title": normalized_title,
        }

    for item in download_items.values():
        href = item["href"]
        title = item["title"]

        if href.startswith(":"):
            href = href[1:]
        if href.startswith("/"):
            href = BASE_URL + href
        elif href.startswith("http"):
            pass
        else:
            href = f"{BASE_URL}/{href.lstrip('/')}"

        filename = clean_filename(title)
        if not filename.lower().endswith(".xlsx"):
            filename += ".xlsx"

        destination = output_root / filename
        if destination.exists():
            print(f"Already exists: {filename}")
            skipped += 1
            continue

        download_file(session, href, destination)
        downloaded += 1

    print("\nDownload summary")
    print("==============")
    print(f"Files found on page: {total_found}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped existing: {skipped}")
    print(f"Destination: {output_root}")


def download_range(output_dir: Path, start_year: int, start_month: int, end_year: int, end_month: int) -> None:
    current_year = start_year
    current_month = start_month
    while current_year < end_year or (current_year == end_year and current_month <= end_month):
        print("\n" + "#" * 60)
        print(f"Processing {MONTH_NAMES[current_month]} {current_year}")
        print("#" * 60)
        try:
            download_monthly_files(output_dir, current_year, current_month)
        except Exception as exc:
            print(f"Failed to download {MONTH_NAMES[current_month]} {current_year}: {exc}")

        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download selected Quant Mutual monthly portfolio files",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2026,
        help="Start year for download range",
    )
    parser.add_argument(
        "--start-month",
        type=int,
        default=7,
        help="Start month for download range (1-12)",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        default=2026,
        help="End year for download range",
    )
    parser.add_argument(
        "--end-month",
        type=int,
        default=7,
        help="End month for download range (1-12)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "01_raw_files",
        help="Base output directory for downloaded files",
    )
    args = parser.parse_args()
    download_range(
        args.output_dir,
        args.start_year,
        args.start_month,
        args.end_year,
        args.end_month,
    )
