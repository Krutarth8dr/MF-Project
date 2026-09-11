import argparse
import calendar
import re
import time
from pathlib import Path
from urllib.parse import urlparse
import requests

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "JIO_BLACKROCK"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

DISCLOSURE_URL = (
    "https://www.jioblackrockamc.com/"
    "statutory-disclosure/disclosures/monthly-portfolio-disclosure"
)

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

MONTH_NUMBERS = {name.lower(): num for num, name in MONTH_NAMES.items()}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
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
    return re.sub(r"[\s\-_]+", "", title).strip().lower()


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
            f"Jio BlackRock Mutual Fund-Monthly-Portfolio-{last_day:02d}-{month_padded}-{current_year}"
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
    (see TARGET_TITLE_OVERRIDES).
    """
    match = re.search(r"Monthly-Portfolio-\d{2}-(\d{2})-(\d{4})", target_title)
    if match:
        month_number, year_number = match.group(1), match.group(2)
        key = f"{year_number}-{month_number}"
        if key in TARGET_TITLE_OVERRIDES:
            return TARGET_TITLE_OVERRIDES[key]
    return target_title


def select_ant_dropdown_option(driver, selector_index: int, target_text: str) -> bool:
    """
    Safely clicks an Ant Design dropdown and selects an option, handling
    virtual scrolling (rc-virtual-list) across long lists.
    """
    selectors = driver.find_elements(By.CSS_SELECTOR, "div.ant-select-selector")
    if len(selectors) <= selector_index:
        return False

    target_clean = title_key(target_text)

    # Click to open dropdown
    selectors[selector_index].click()
    time.sleep(0.4)

    vholders = driver.find_elements(By.CSS_SELECTOR, ".rc-virtual-list-holder")
    scroll_positions = [0.0, 0.5, 1.0] if vholders else [0.0]

    for pos in scroll_positions:
        if vholders:
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight * arguments[1];",
                vholders[0],
                pos,
            )
            time.sleep(0.2)

        options = driver.find_elements(
            By.CSS_SELECTOR, "div.ant-select-item-option-content"
        )
        for opt in options:
            opt_text = opt.text.strip()
            if not opt_text:
                continue
            if title_key(opt_text) == target_clean or opt_text.lower() == target_text.lower():
                opt.click()
                time.sleep(0.4)
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                time.sleep(0.2)
                return True

    ActionChains(driver).send_keys(Keys.ESCAPE).perform()
    time.sleep(0.2)
    return False


def find_doc_links(driver, target_title: str, search_title: str = None) -> list:
    """
    Finds the matching master monthly portfolio file link on the rendered page.
    """
    search_key = title_key(search_title if search_title else target_title)
    target_key = title_key(target_title)

    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
    links = []

    for anchor in anchors:
        title = anchor.text.strip()
        href = anchor.get_attribute("href")
        if not href:
            continue
        href = href.strip()
        lowered = href.lower()
        if any(ext in lowered for ext in [".xlsx", ".xls", ".xlsm", ".csv"]):
            clean_t = title_key(title)
            clean_h = title_key(href)

            # Match exact search key OR standard mutual fund monthly portfolio patterns
            is_match = (
                clean_t == search_key
                or clean_t == target_key
                or "jioblackrockmutualfundmonthlyportfolio" in clean_t
                or "jioblackrockmutualfund" in clean_t
                or "jioblackrock-mutual-fund-monthly-portfolio" in lowered
            )

            # Avoid matching single-scheme specific files if looking for the combined file
            if is_match and search_key == target_key and "mutualfund" not in clean_t and "mutualfund" not in clean_h:
                is_match = False

            if not is_match:
                continue

            if not href.startswith("http"):
                href = resolve_url(href)
            file_name = Path(urlparse(href).path).name
            ext = Path(file_name).suffix or ".xlsx"
            display_filename = clean_filename(target_title) + ext
            links.append(
                {
                    "title": target_title,
                    "url": href,
                    "filename": display_filename,
                }
            )

    # Deduplicate
    seen = set()
    unique = []
    for link in links:
        if link["filename"] not in seen:
            seen.add(link["filename"])
            unique.append(link)
    return unique


def download_target(driver, target_title: str, state: dict) -> int:
    target_month_name = parse_target_month(target_title)
    target_year_selector = year_selector_for_target(target_title)
    search_title = search_title_for_target(target_title)

    print("=" * 100)
    print(f"Target title         : {target_title}")
    print(f"Target month         : {target_month_name}")
    print(f"Target selector year : {target_year_selector}")
    if search_title != target_title:
        print(f"Search title override: {search_title}")

    # Select Year
    if state.get("year") != target_year_selector:
        success = select_ant_dropdown_option(driver, 0, target_year_selector)
        if not success:
            print(f"Year selector not available in DOM: {target_year_selector}")
            return 0
        state["year"] = target_year_selector
        time.sleep(1.0)

    # Select Month
    success = select_ant_dropdown_option(driver, 1, target_month_name)
    if not success:
        print(
            f"Skip {target_title}: month {target_month_name} is not visible in the current Jio selector."
        )
        return 0

    time.sleep(2.0)

    doc_links = find_doc_links(driver, target_title, search_title)
    if not doc_links:
        print(
            f"No document links found for '{search_title}' ({target_month_name} / "
            f"{target_year_selector}). The disclosure may not be published yet."
        )
        return 0

    print(f"Found {len(doc_links)} Jio portfolio workbook link(s) for {target_title}.")

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
            print(f"      Complete ({output_path.stat().st_size} bytes)")
        except Exception as exc:
            print(f'      Failed : {doc["url"]} -> {exc}')

    print(f"Downloaded : {downloaded}, Skipped : {skipped}")
    return downloaded


def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    return webdriver.Chrome(options=chrome_options)


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
        default="2026-08",
        help="Inclusive end month in YYYY-MM format, e.g. 2026-08",
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

    driver = create_driver()
    try:
        print("Opening Jio BlackRock disclosure page...")
        driver.get(DISCLOSURE_URL)
        time.sleep(4)

        state = {"year": None}
        total_downloaded = 0
        for target_title in target_titles:
            try:
                dl = download_target(driver, target_title, state)
                total_downloaded += dl
            except Exception as exc:
                print(f"Downloader error for {target_title}: {exc}")
                continue

        print("\n" + "=" * 100)
        print("Jio BlackRock Download Summary")
        print("=" * 100)
        print(f"Total downloaded : {total_downloaded}")
        print(f"Destination      : {RAW_FOLDER}")
        print("=" * 100)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
