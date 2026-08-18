import re
import time
from pathlib import Path

import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ==============================================================================
# SETTINGS
# ==============================================================================

URL = "https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio"

# Each entry: what to type into the search bar for that year (returns every
# file for the selected YEAR whose name contains this text, across all
# months, in one go), a stricter case-insensitive match applied to each
# result's <p> text as a safety check on top of the search bar's own
# filtering, and where to save matching files.
FUNDS = [
    # {
    #     "search_query": "HDFC Large Cap Fund",
    #     "name_match": "hdfc large cap fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Large Cap Fund"
    #     ),
    # },
    # {
    #     # This fund was renamed at some point -- "HDFC Value Fund" was
    #     # called "HDFC Capital Builder Fund" back in 2024.
    #     #
    #     # "search_query" is the DEFAULT query used for any year not listed
    #     # in "search_query_by_year" below. "search_query_by_year" lets you
    #     # pin an exact query (or list of queries) to specific years, so we
    #     # don't waste a search -- or risk a false match -- searching an old
    #     # name against years it was never used in.
    #     #
    #     # "name_match" still lists every historical name, since it's just
    #     # used to confirm a found file actually belongs to this fund; it
    #     # doesn't drive which search gets run for which year.
    #     "search_query": "HDFC Value Fund",
    #     "search_query_by_year": {
    #         2024: ["HDFC Capital Builder Value Fund"],
    #         2025: ["HDFC Capital Builder Value Fund", "HDFC Value Fund"],
    #         2026: "HDFC Value Fund",
    #     },
    #     "name_match": ["hdfc value fund", "hdfc capital builder value fund"],
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Value Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Technology Fund",
    #     "name_match": "hdfc technology fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Technology Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Small Cap Fund",
    #     "name_match": "hdfc small cap fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Small Cap Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Transportation And Logistics Fund",
    #     "name_match": "hdfc transportation and logistics fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Transportation And Logistics Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Pharma And Healthcare Fund",
    #     "name_match": "hdfc pharma and healthcare fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Pharma And Healthcare Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Multi-Asset Allocation Fund",
    #     "search_query_by_year": {
    #         2025: "HDFC Multi-Asset Allocation Fund",
    #         2026: "HDFC Multi-Asset Allocation Fund",
    #     },
    #     "name_match": "hdfc multi-asset allocation fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Multi-Asset Allocation Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Multi Cap Fund",
    #     "name_match": "hdfc multi cap fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Multi Cap Fund"
    #     ),
    # },
    # {
    #     "search_query": "MNC",
    #     "name_match": "hdfc mnc fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC MNC Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Mid Cap Fund",
    #     "search_query_by_year": {
    #         2024: "Monthly HDFC Mid-Cap Opportunities Fund",
    #         2025: [
    #             "Monthly HDFC Mid Cap Fund",
    #             "Monthly HDFC Mid-Cap Opportunities Fund",
    #         ],
    #         2026: "Monthly HDFC Mid Cap Fund",
    #     },
    #     "name_match": ["hdfc mid cap fund", "hdfc mid-cap opportunities fund"],
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Mid Cap Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Manufacturing Fund",
    #     "name_match": "hdfc manufacturing fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Manufacturing Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Large Cap Fund",
    #     "name_match": "hdfc large cap fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Large Cap Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Large and Mid Cap Fund",
    #     "name_match": "hdfc large and mid cap fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Large and Mid Cap Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Innovation Fund",
    #     "name_match": "monthly hdfc innovation fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Innovation Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Infrastructure Fund",
    #     "name_match": "hdfc infrastructure fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Infrastructure Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Hybrid Equity Fund",
    #     "name_match": "hdfc hybrid equity fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Hybrid Equity Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Housing Opportunities Fund",
    #     "name_match": "hdfc housing opportunities fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Housing Opportunities Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Focused Fund",
    #     "search_query_by_year": {
    #         2024: "Monthly HDFC Focused 30 Fund",
    #         2025: [
    #             "Monthly HDFC Focused Fund",
    #             "Monthly HDFC Focused 30 Fund",
    #         ],
    #         2026: "Monthly HDFC Focused Fund",
    #     },
    #     "name_match": ["monthly hdfc focused fund", "monthly hdfc focused 30 fund"],
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Focused Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Flexi Cap Fund",
    #     "name_match": "hdfc flexi cap fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Flexi Cap Fund"
    #     ),
    # },
    # {
    #     "search_query": "Monthly HDFC Equity Savings Fund",
    #     "name_match": "monthly hdfc equity savings fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Equity Savings Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC ELSS Tax saver",
    #     "name_match": "hdfc elss tax saver",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC ELSS Tax Saver Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Dividend Yield Fund",
    #     "name_match": "hdfc dividend yield fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Dividend Yield Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Defence Fund",
    #     "name_match": "hdfc defence fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Defence Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Consumption Fund",
    #     "name_match": "hdfc consumption fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Consumption Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Business Cycle Fund",
    #     "name_match": "hdfc business cycle fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Business Cycle Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Banking Financial Services Fund",
    #     "name_match": "hdfc banking financial services fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Banking Financial Services Fund"
    #     ),
    # },
    # {
    #     "search_query": "HDFC Balanced Advantage Fund",
    #     "search_query_by_year": {
    #         2024: "HDFC Balanced Advantage Fund",
    #         2025: "HDFC Balanced Advantage Fund",
    #         2026: "Balanced Advantage",
    #     },
    #     "name_match": "Monthly HDFC Balanced Advantage Fund",
    #     "output_folder": Path(
    #         r"D:\MF Project\MF Analysis\01_raw_files\HDFC\HDFC Balanced Advantage Fund"
    #     ),
    # },
]

for _fund in FUNDS:
    _fund["output_folder"].mkdir(parents=True, exist_ok=True)
    # Normalize to lists internally so downstream code never has to check
    # "is this a string or a list" itself.
    if isinstance(_fund["search_query"], str):
        _fund["search_query"] = [_fund["search_query"]]
    if isinstance(_fund["name_match"], str):
        _fund["name_match"] = [_fund["name_match"]]
    if "search_query_by_year" in _fund:
        for _yr, _q in _fund["search_query_by_year"].items():
            if isinstance(_q, str):
                _fund["search_query_by_year"][_yr] = [_q]


def get_queries_for_year(fund, year):
    """
    Resolve which search quer(ies) to run for a given fund in a given year:
    - if the fund has a per-year override for this exact year, use that
    - elif the fund has a per-year map but this year isn't in it, fall back
      to the fund's default "search_query" (still useful if e.g. the rename
      map only covers a couple of transition years and everything else uses
      the current name)
    - else just use the fund's default "search_query" for every year
    """
    by_year = fund.get("search_query_by_year")
    if by_year and year in by_year:
        return by_year[year]
    return fund["search_query"]


# Inclusive range
START_YEAR, START_MONTH = 2026, 7  # July 2026
END_YEAR, END_MONTH = 2026, 7  # July 2026

# Set to True once you've watched it run correctly a couple of times and
# want it to run without popping up a visible Chrome window.
HEADLESS = False

MONTH_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def in_target_range(year, month):
    return (START_YEAR, START_MONTH) <= (year, month) <= (END_YEAR, END_MONTH)


def parse_date_from_display_name(display_name):
    """
    Extracts the date from strings like:
      "Monthly HDFC Large Cap Fund - 31 December 2025.xlsx"
    Returns (year, month) or (None, None) if it can't be parsed.
    """
    match = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
        display_name,
    )
    if not match:
        return None, None

    day_str, month_str, year_str = match.groups()
    month = MONTH_NUM.get(month_str.strip().lower())

    if month is None:
        return None, None

    return int(year_str), month


# ==============================================================================
# BROWSER SETUP
# ==============================================================================


def build_driver():
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    return driver


def safe_click(driver, element):
    """
    Try a normal click first. If it's intercepted (e.g. the element is
    scrolled off-screen due to leftover scroll position from a previous
    action, or something is momentarily overlapping it), scroll it into
    view and fall back to a JS-dispatched click, which doesn't care about
    viewport position/overlap the way a native click does.
    """
    try:
        element.click()
    except Exception:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", element
        )
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", element)


# ==============================================================================
# DATE PICKER INTERACTION
# ==============================================================================


ALL_MONTH_ABBRS = [
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


def select_year(driver, year):
    """
    Opens the year/month dropdown and clicks the requested year (which flips
    the panel to a month grid for that year), then clicks WHICHEVER month
    cell is actually present -- the exact month doesn't matter here, since
    the search bar (used afterward) returns every matching file for the
    whole year regardless of which month was clicked to "enter" that year.

    Important: for the CURRENT year, the month grid only lists months that
    have actually been published so far (e.g. only Jan-Jun if it's currently
    July) -- there is no fixed Jan-Dec grid. So we can't hardcode a specific
    month like "Dec"; we search for any of the 12 possible abbreviations and
    click the first one found in the DOM.
    """
    # A previous year's load_all_results() scrolls the page way down to load
    # every month. If we don't scroll back up before opening the dropdown
    # again, the dropdown button can end up off-screen (negative viewport
    # coordinates) and the click gets intercepted. Reset scroll position first.
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.3)

    dropdown_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "div[class*='style_dropdowndiv'] button")
        )
    )
    safe_click(driver, dropdown_button)

    calendar_el = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "div[class*='style_calenderbg']")
        )
    )

    def find_year_btn(d):
        cal = d.find_element(By.CSS_SELECTOR, "div[class*='style_calenderbg']")
        return cal.find_element(By.XPATH, f".//*[normalize-space(text())='{year}']")

    try:
        year_btn = WebDriverWait(driver, 7).until(find_year_btn)
        safe_click(driver, year_btn)
    except TimeoutException:
        # If `year` is the current year, the calendar may open straight into
        # that year's MONTH view (skipping the year grid), since it's
        # already the active selection -- there'd be no year-grid cell with
        # this text to find. Check whether we already appear to be on the
        # right year's month view before giving up.
        header_text = (
            calendar_el.text.strip().splitlines()[0] if calendar_el.text.strip() else ""
        )
        if str(year) in header_text:
            print(
                f"  [INFO] Calendar opened directly into {year}'s month view "
                f"(year grid was skipped); continuing to month selection."
            )
        else:
            raise

    month_condition = " or ".join(
        f"normalize-space(text())='{m}'" for m in ALL_MONTH_ABBRS
    )

    def find_any_month_btn(d):
        cal = d.find_element(By.CSS_SELECTOR, "div[class*='style_calenderbg']")
        return cal.find_element(By.XPATH, f".//*[{month_condition}]")

    month_btn = WebDriverWait(driver, 10).until(find_any_month_btn)
    clicked_month_abbr = month_btn.text.strip()
    safe_click(driver, month_btn)

    # Confirm the button label updated to reflect the target year (we don't
    # know in advance which month got clicked, only that it's in `year`).
    WebDriverWait(driver, 15).until(lambda d: str(year) in dropdown_button.text)

    time.sleep(1.5)
    return clicked_month_abbr


def search_fund(driver, query):
    """Types into the search bar, which live-filters the file list to every
    file (across all months of the currently selected year) matching query.

    Called once per fund per year, so a previous fund's load_all_results()
    may have scrolled the page down -- reset scroll first so the search box
    is actually interactable, with a JS fallback if a native click/send_keys
    still doesn't work for some reason.
    """

    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.3)

    search_box = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder='Search']"))
    )

    try:
        search_box.clear()
        search_box.send_keys(query)
    except Exception:
        driver.execute_script(
            """
            const el = arguments[0];
            const value = arguments[1];
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, value);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            search_box,
            query,
        )

    # Wait for the filtered results to actually reflect the query -- i.e. at
    # least one result whose text contains it -- rather than a fixed sleep.
    WebDriverWait(driver, 15).until(
        lambda d: any(
            query.lower() in a.text.lower()
            for a in d.find_elements(By.CSS_SELECTOR, "a[class*='style_listdiv']")
        )
    )
    time.sleep(1)


def _try_click_load_more(driver):
    """If the page uses an explicit 'Load More' / 'View More' button rather
    than pure infinite scroll, click it. Returns True if something was
    clicked."""
    xpaths = [
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view more')]",
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'load more')]",
        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'view more')]",
    ]
    for xp in xpaths:
        try:
            btn = driver.find_element(By.XPATH, xp)
            if btn.is_displayed():
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", btn
                )
                time.sleep(0.2)
                btn.click()
                return True
        except Exception:
            continue
    return False


def load_all_results(driver, max_rounds=40, pause=0.7):
    """
    The site only renders a first batch of results and loads more as you
    scroll (or via a 'Load More' button) -- scanning right after the search
    filter applies only sees whatever's rendered at that instant. This keeps
    scrolling / clicking "load more" until the number of file-list anchors
    on the page stops growing for two checks in a row.
    """
    last_count = -1
    stable_rounds = 0

    for _ in range(max_rounds):
        anchors = driver.find_elements(By.CSS_SELECTOR, "a[class*='style_listdiv']")
        count = len(anchors)

        if count == last_count:
            stable_rounds += 1
            if stable_rounds >= 2:
                break
        else:
            stable_rounds = 0
        last_count = count

        clicked = _try_click_load_more(driver)

        if not clicked:
            if anchors:
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'end'});", anchors[-1]
                    )
                except Exception:
                    driver.execute_script(
                        "window.scrollTo(0, document.body.scrollHeight);"
                    )
            else:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        time.sleep(pause)


# ==============================================================================
# FILE LIST SCANNING
# ==============================================================================


def find_all_matching_links(driver, fund_match):
    """
    Scan every file-list anchor currently on the page (after search-bar
    filtering, this should span every month of the selected year that
    matches the search query) for ones whose visible text contains ANY of
    fund_match (case-insensitive). fund_match can be a single string or a
    list of strings -- useful for funds that were renamed at some point
    (e.g. "HDFC Value Fund" was "HDFC Capital Builder Fund" in 2024), where
    a file's actual name in the list depends on which year it's from.
    Returns a list of (href, display_name), de-duplicated by display_name.
    """

    if isinstance(fund_match, str):
        fund_match = [fund_match]
    fund_match_lower = [m.lower() for m in fund_match]

    anchors = driver.find_elements(By.CSS_SELECTOR, "a[class*='style_listdiv']")

    results = []
    seen_names = set()

    for a in anchors:
        try:
            p_text = a.find_element(By.TAG_NAME, "p").text.strip()
        except Exception:
            continue

        if not any(m in p_text.lower() for m in fund_match_lower):
            continue

        if p_text in seen_names:
            continue
        seen_names.add(p_text)

        href = a.get_attribute("href")
        results.append((href, p_text))

    return results


def dump_diagnostics(driver, year):
    """
    Called when select_year()/search_fund() fails. Saves a screenshot and
    prints whatever text is currently visible in the dropdown button and
    calendar container, so a failure can actually be diagnosed instead of
    just showing a bare exception.
    """
    debug_dir = Path(r"D:\MF Project\MF Analysis\01_raw_files\HDFC\_debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = debug_dir / f"error_{year}.png"

    try:
        driver.save_screenshot(str(screenshot_path))
        print(f"  [DEBUG] Screenshot saved: {screenshot_path}")
    except Exception as exc:
        print(f"  [DEBUG] Could not save screenshot -> {exc}")

    try:
        button = driver.find_element(
            By.CSS_SELECTOR, "div[class*='style_dropdowndiv'] button"
        )
        print(
            f"  [DEBUG] Dropdown button text/state: {button.text!r} "
            f"aria-expanded={button.get_attribute('aria-expanded')!r}"
        )
    except Exception as exc:
        print(f"  [DEBUG] Could not read dropdown button -> {exc}")

    try:
        cal = driver.find_element(By.CSS_SELECTOR, "div[class*='style_calenderbg']")
        print(f"  [DEBUG] Calendar container text: {cal.text!r}")
    except Exception as exc:
        print(f"  [DEBUG] Calendar container not found/visible -> {exc}")

    try:
        print(f"  [DEBUG] Current URL: {driver.current_url}")
    except Exception:
        pass


# ==============================================================================
# DOWNLOAD
# ==============================================================================


def download_file(href, display_name, dest_folder):
    filename = sanitize_filename(Path(display_name).name)
    dest_path = dest_folder / filename

    if dest_path.exists():
        print(f"  [SKIP] Already downloaded: {filename}")
        return dest_path, False

    response = requests.get(href, headers=REQUEST_HEADERS, timeout=60)
    response.raise_for_status()

    dest_path.write_bytes(response.content)
    print(f"  [OK] Downloaded: {filename}")
    return dest_path, True


# ==============================================================================
# MAIN
# ==============================================================================


def main():
    # A hashable label per fund (name_match is now a list, can't be a dict
    # key directly) -- used for stats and log lines.
    for f in FUNDS:
        f["label"] = " / ".join(f["name_match"])

    print("=" * 90)
    print("Downloading HDFC monthly portfolios")
    print("=" * 90)
    print(f"Range  : {START_MONTH}/{START_YEAR} to {END_MONTH}/{END_YEAR}")
    for f in FUNDS:
        print(f"  -> {f['label']:<40} saves to {f['output_folder']}")
        print(f"     default query : {f['search_query']}")
        if "search_query_by_year" in f:
            for yr in sorted(f["search_query_by_year"]):
                print(f"     {yr} query    : {f['search_query_by_year'][yr]}")
    print()

    years = sorted(set(range(START_YEAR, END_YEAR + 1)))

    driver = build_driver()

    stats = {
        f["label"]: {"downloaded": 0, "already_had": 0, "skipped_out_of_range": 0}
        for f in FUNDS
    }
    unparseable = []
    errors = []

    try:
        driver.get(URL)

        for year in years:
            print(f"[{year}] Selecting year...")

            try:
                select_year(driver, year)
            except Exception as exc:
                print(f"  ERROR: Could not select {year}")
                print(f"  Exception type : {type(exc).__name__}")
                print(f"  Exception msg  : {exc}")
                dump_diagnostics(driver, year)
                errors.append(f"{year} (year selection)")
                continue

            for fund in FUNDS:
                label = fund["label"]

                # A renamed fund needs a separate search per historical name
                # (the search bar only takes one query at a time), then the
                # results get merged/de-duplicated below.
                combined_matches = {}  # display_name -> href

                for query in get_queries_for_year(fund, year):
                    print(f"  [{year}] Searching '{query}' (fund: {label})...")

                    try:
                        search_fund(driver, query)
                        load_all_results(driver)
                    except Exception as exc:
                        print(
                            f"    ERROR: Search failed for '{query}' ({label}) in {year}"
                        )
                        print(f"    Exception type : {type(exc).__name__}")
                        print(f"    Exception msg  : {exc}")
                        safe_label = f"{year}_{query}".replace(" ", "_")
                        dump_diagnostics(driver, safe_label)
                        errors.append(f"{year} {label} query='{query}' (search)")
                        continue

                    query_matches = find_all_matching_links(driver, fund["name_match"])

                    for href, display_name in query_matches:
                        combined_matches[display_name] = href

                if not combined_matches:
                    print(f"    [NOT FOUND] No files matched for {label} in {year}.")
                    continue

                print(
                    f"    Found {len(combined_matches)} unique file(s) for {label} in {year}."
                )

                for display_name, href in combined_matches.items():
                    file_year, file_month = parse_date_from_display_name(display_name)

                    if file_year is None:
                        print(f"    [SKIP] Could not parse a date from: {display_name}")
                        unparseable.append(display_name)
                        continue

                    if not in_target_range(file_year, file_month):
                        stats[label]["skipped_out_of_range"] += 1
                        continue

                    try:
                        _, was_new = download_file(
                            href, display_name, fund["output_folder"]
                        )
                        if was_new:
                            stats[label]["downloaded"] += 1
                        else:
                            stats[label]["already_had"] += 1
                    except Exception as exc:
                        print(f"    ERROR: Download failed for {display_name} -> {exc}")
                        errors.append(display_name)

    finally:
        driver.quit()

    print()
    print("=" * 90)
    print("Done")
    print("=" * 90)
    for f in FUNDS:
        s = stats[f["label"]]
        print(f"{f['label']}:")
        print(f"  Newly downloaded         : {s['downloaded']}")
        print(f"  Already present (skipped): {s['already_had']}")
        print(f"  Outside target range     : {s['skipped_out_of_range']}")
        print(f"  Output folder            : {f['output_folder']}")
    print()
    print(f"Unparseable filenames : {len(unparseable)} {unparseable}")
    print(f"Errors                : {len(errors)} {errors}")


if __name__ == "__main__":
    main()
