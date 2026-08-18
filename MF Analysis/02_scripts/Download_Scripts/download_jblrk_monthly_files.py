import argparse
import calendar
import re
import requests
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "JIO_BLACKROCK"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

DISCLOSURE_URL = (
    "https://www.jioblackrockamc.com/"
    "statutory-disclosure/disclosures/monthly-portfolio-disclosure"
)

TARGET_TITLE = "Jio BlackRock Mutual Fund-Monthly-Portfolio-31-07-2025"
TARGET_FILE_HINT = "Jio BlackRock Mutual Fund-Monthly-Portfolio-31-07-2025"

# Some months are published on the Jio site under a visible link title that
# doesn't match our standard "Jio BlackRock Mutual Fund-Monthly-Portfolio-
# DD-MM-YYYY" naming (e.g. a lowercase, date-less title). Add an entry here
# ("YYYY-MM": "<exact on-page title text>") to search for that title while
# still saving the file under our normal dated filename.
TARGET_TITLE_OVERRIDES = {
    "2025-08": "jioblackrock-mutual-fund-monthly-portfolio",
}

MONTH_NAMES = {
    "01": "January",
    "02": "February",
    "03": "March",
    "04": "April",
    "05": "May",
    "06": "June",
    "07": "July",
    "08": "August",
    "09": "September",
    "10": "October",
    "11": "November",
    "12": "December",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 60


def clean_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "", name).strip()


def download_file(url: str, output_path: Path) -> None:
    response = requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT)
    response.raise_for_status()
    with open(output_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)


def resolve_url(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "https://www.jioblackrockamc.com" + url


def title_key(title: str) -> str:
    return re.sub(r"\s+", "", title).strip().lower()


def find_doc_links(page, target_title: str, search_title: str = None) -> list:
    """
    Parse workstation-rendered hrefs after the month filter has been selected.
    The docs appear in the body of the page and are anchor elements with direct file URLs.

    `search_title` is the text to look for among the page's anchor titles
    (defaults to `target_title`). `target_title` is always what the saved
    filename is derived from, even when the two differ (see
    TARGET_TITLE_OVERRIDES) -- so a differently-titled page link still gets
    saved under our standard dated filename.
    """

    target_key = title_key(search_title if search_title else target_title)
    links = []
    anchors = page.locator("a[href]")
    for i in range(anchors.count()):
        anchor = anchors.nth(i)
        title = anchor.inner_text().strip()
        href = anchor.get_attribute("href")
        if not href:
            continue
        href = href.strip()
        lowered = href.lower()
        if any(
            ext in lowered for ext in [".xlsx", ".xls", ".xlsm", ".csv", ".pdf", ".zip"]
        ):
            if title_key(title) != target_key:
                continue
            if not href.startswith("http"):
                href = resolve_url(href)
            file_name = Path(urlparse(href).path).name
            ext = Path(file_name).suffix
            display_filename = clean_filename(target_title) + ext
            links.append(
                {
                    "title": target_title,
                    "url": href,
                    "filename": display_filename,
                }
            )
    # dedupe
    seen = set()
    unique = []
    for link in links:
        if link["title"] not in seen:
            seen.add(link["title"])
            unique.append(link)
    return unique


def parse_target_month(target_title: str) -> str:
    match = re.search(r"Monthly-Portfolio-(\d{2})-(\d{2})-(\d{4})", target_title)
    if not match:
        raise ValueError(
            "Could not infer month from target title. Use a title like: "
            "Jio BlackRock Mutual Fund-Monthly-Portfolio-31-01-2026"
        )
    month_number = match.group(2)
    if month_number not in MONTH_NAMES:
        raise ValueError(f"Unsupported month value in target title: {month_number}")
    return MONTH_NAMES[month_number]


def parse_month_spec(month_spec: str) -> tuple[int, int]:
    """
    Accepts strings like 2026-06, 2026/06, or 06-2026.
    Returns (year, month_number).
    """

    text = month_spec.strip()
    if re.fullmatch(r"\d{4}-\d{1,2}", text):
        year_str, month_str = text.split("-", 1)
        return int(year_str), int(month_str)
    if re.fullmatch(r"\d{1,2}-\d{4}", text):
        month_str, year_str = text.split("-", 1)
        return int(year_str), int(month_str)
    if re.fullmatch(r"\d{4}/\d{1,2}", text):
        year_str, month_str = text.split("/", 1)
        return int(year_str), int(month_str)
    raise ValueError(f"Unsupported month spec: {month_spec}")


def build_target_titles(start_month: str, end_month: str) -> list[str]:
    start_year, start_month_no = parse_month_spec(start_month)
    end_year, end_month_no = parse_month_spec(end_month)

    if (start_year, start_month_no) > (end_year, end_month_no):
        raise ValueError("Start month must be earlier than or equal to end month.")

    target_titles = []
    current_year = start_year
    current_month = start_month_no

    while (current_year, current_month) <= (end_year, end_month_no):
        month_padded = f"{current_month:02d}"
        last_day = calendar.monthrange(current_year, current_month)[1]
        target_titles.append(
            f"Jio BlackRock Mutual Fund-Monthly-Portfolio-{last_day}-{month_padded}-{current_year}"
        )
        current_month += 1
        if current_month == 13:
            current_month = 1
            current_year += 1

    return target_titles


def year_selector_for_target(target_title: str) -> str:
    """
    Maps a target title back to the Jio financial-year selector value it needs
    in the browser UI. Indian mutual fund financial years run April -> March,
    so this is computed generically instead of hardcoded per calendar year.
    """

    match = re.search(r"Monthly-Portfolio-\d{2}-(\d{2})-(\d{4})", target_title)
    if not match:
        raise ValueError(
            f"Cannot derive a month/year from target title: {target_title}"
        )

    month_number = int(match.group(1))
    year_number = int(match.group(2))

    if month_number >= 4:
        fy_start = year_number
    else:
        fy_start = year_number - 1
    return f"{fy_start}-{fy_start + 1}"


def search_title_for_target(target_title: str) -> str:
    """
    Returns the title text to search for on the page for a given canonical
    target_title. Normally identical to target_title, but a handful of
    months are published under a different visible title on the Jio site
    (see TARGET_TITLE_OVERRIDES) even though we still want to save the file
    under our standard dated name.
    """

    match = re.search(r"Monthly-Portfolio-\d{2}-(\d{2})-(\d{4})", target_title)
    if match:
        month_number, year_number = match.group(1), match.group(2)
        key = f"{year_number}-{month_number}"
        if key in TARGET_TITLE_OVERRIDES:
            return TARGET_TITLE_OVERRIDES[key]
    return target_title


def download_target(page, target_title: str, state: dict) -> int:
    target_month_name = parse_target_month(target_title)
    target_year_selector = year_selector_for_target(target_title)
    search_title = search_title_for_target(target_title)

    print("=" * 100)
    print(f"Target title : {target_title}")
    print(f"Target month : {target_month_name}")
    print(f"Target selector year : {target_year_selector}")
    if search_title != target_title:
        print(f"Search title override : {search_title}")

    selectors = page.locator("div.ant-select-selector")
    if selectors.count() < 2:
        raise RuntimeError("Expected a year and month selector on the Jio page.")

    if not target_year_selector:
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    else:
        # Always click through the year selector, even if it's already
        # showing the right FY. The site's month list isn't a static set
        # fetched once per year -- it only reflects whatever was last
        # actually selected, so skipping this on later iterations (as a
        # prior version did, to dodge an Ant Design "already selected"
        # dropdown-stuck-open bug) left the month list stale and silently
        # missing months that hadn't been in view yet (e.g. Jan-Mar when
        # a run started earlier in the same FY).
        selectors.nth(0).click()
        page.wait_for_timeout(500)
        year_options = page.locator("div.ant-select-item-option-content")
        found_year = False
        for i in range(year_options.count()):
            opt_text = year_options.nth(i).inner_text().strip().lower()
            if opt_text == target_year_selector.lower():
                year_options.nth(i).click()
                found_year = True
                break
        if not found_year:
            print(f"Year selector not available in DOM: {target_year_selector}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            return 0
        # The click above may not close the dropdown if the value didn't
        # change (no "change" event fires), so force it closed regardless.
        page.keyboard.press("Escape")
        page.wait_for_timeout(1500)
        state["year"] = target_year_selector

    selectors.nth(1).click()
    page.wait_for_timeout(500)

    month_options = page.locator("div.ant-select-item-option-content")
    found_month = False
    for i in range(month_options.count()):
        option_text = month_options.nth(i).inner_text().strip().lower()
        if option_text == target_month_name.lower():
            month_options.nth(i).click()
            found_month = True
            break

    if not found_month:
        print(
            f"Skip {target_title}: month {target_month_name} is not visible in the current Jio selector."
        )
        return 0

    page.wait_for_timeout(2000)

    doc_links = find_doc_links(page, target_title, search_title)
    if not doc_links:
        print(
            f"No document links found for '{search_title}' ({target_month_name} / "
            f"{target_year_selector}). The page is still unavailable or the filter "
            "is not returning rows."
        )
        return 0

    print(f"Found {len(doc_links)} Jio portfolio workbook links for {target_title}.")

    downloaded = 0
    skipped = 0
    for idx, doc in enumerate(doc_links, start=1):
        output_path = RAW_FOLDER / doc["filename"]
        if output_path.exists():
            print(f"Exists     : {output_path.name}")
            skipped += 1
            continue

        print(f"{idx:02d} Downloading : {output_path.name}")
        try:
            download_file(doc["url"], output_path)
            downloaded += 1
            print("      Complete")
        except Exception as exc:
            print(f'      Failed : {doc["url"]} -> {exc}')

    print("\n" + "=" * 100)
    print(f"Downloaded : {downloaded}")
    print(f"Skipped     : {skipped}")
    print(f"Folder      : {RAW_FOLDER}")
    print("=" * 100)
    return downloaded


def main():
    parser = argparse.ArgumentParser(
        description="Download Jio BlackRock monthly portfolio workbooks by visible title for a month range."
    )
    parser.add_argument(
        "--start",
        default="2026-01",
        help="Inclusive start month in YYYY-MM format, e.g. 2025-07",
    )
    parser.add_argument(
        "--end",
        default="2026-03",
        help="Inclusive end month in YYYY-MM format, e.g. 2026-07",
    )
    parser.add_argument(
        "--target-title",
        default=None,
        help="Optional single title override. If supplied it ignores --start/--end.",
    )
    args = parser.parse_args()

    if args.target_title:
        target_titles = [args.target_title]
    else:
        target_titles = build_target_titles(args.start, args.end)

    print("=" * 100)
    print("Jio BlackRock Monthly Portfolio Downloader")
    print("=" * 100)
    print(f"Requested range : {args.start} -> {args.end}")
    print(f"Total target titles : {len(target_titles)}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        try:
            print("Opening Jio BlackRock disclosure page...")
            page.goto(DISCLOSURE_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1000)

            state = {"year": None}
            for target_title in target_titles:
                try:
                    download_target(page, target_title, state)
                except Exception as exc:
                    print(f"Downloader failed for {target_title}: {exc}")
                    continue

        finally:
            browser.close()


if __name__ == "__main__":
    main()
