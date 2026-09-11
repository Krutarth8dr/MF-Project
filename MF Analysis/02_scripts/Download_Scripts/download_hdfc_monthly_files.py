import os
import sys
import time
import re
from pathlib import Path
import requests

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_HDFC_FOLDER = BASE_DIR / "01_raw_files" / "HDFC"

FUNDS = [
    {
        "search_query": ["HDFC Large Cap Fund", "Large Cap"],
        "name_match": ["hdfc large cap fund", "large cap fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Large Cap Fund",
    },
    {
        "search_query": ["HDFC Value Fund", "HDFC Capital Builder Value Fund", "Capital Builder"],
        "name_match": ["hdfc value fund", "hdfc capital builder value fund", "capital builder"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Value Fund",
    },
    {
        "search_query": ["HDFC Technology Fund"],
        "name_match": ["hdfc technology fund", "technology fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Technology Fund",
    },
    {
        "search_query": ["HDFC Small Cap Fund"],
        "name_match": ["hdfc small cap fund", "small cap fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Small Cap Fund",
    },
    {
        "search_query": ["HDFC Transportation and Logistics Fund", "Transportation"],
        "name_match": ["hdfc transportation and logistics fund", "transportation and logistics"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Transportation And Logistics Fund",
    },
    {
        "search_query": ["HDFC Pharma and Healthcare Fund", "Pharma"],
        "name_match": ["hdfc pharma and healthcare fund", "pharma and healthcare"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Pharma And Healthcare Fund",
    },
    {
        "search_query": ["HDFC Multi Asset Allocation Fund", "HDFC Multi-Asset Allocation Fund", "Multi Asset"],
        "name_match": ["hdfc multi-asset allocation fund", "hdfc multi asset allocation fund", "multi asset allocation"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Multi-Asset Allocation Fund",
    },
    {
        "search_query": ["HDFC Multi Cap Fund"],
        "name_match": ["hdfc multi cap fund", "multi cap fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Multi Cap Fund",
    },
    {
        "search_query": ["HDFC MNC Fund", "MNC"],
        "name_match": ["hdfc mnc fund", "mnc fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC MNC Fund",
    },
    {
        "search_query": ["Monthly HDFC Mid Cap Fund", "HDFC Mid-Cap Opportunities Fund", "Mid Cap"],
        "name_match": ["hdfc mid cap fund", "hdfc mid-cap opportunities fund", "mid-cap opportunities", "mid cap fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Mid Cap Fund",
    },
    {
        "search_query": ["HDFC Manufacturing Fund"],
        "name_match": ["hdfc manufacturing fund", "manufacturing fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Manufacturing Fund",
    },
    {
        "search_query": ["HDFC Large and Mid Cap Fund", "HDFC Large Mid Cap Fund", "Large Mid Cap"],
        "name_match": ["hdfc large and mid cap fund", "hdfc large mid cap fund", "large mid cap fund", "large  mid cap"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Large and Mid Cap Fund",
    },
    {
        "search_query": ["HDFC Innovation Fund"],
        "name_match": ["hdfc innovation fund", "innovation fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Innovation Fund",
    },
    {
        "search_query": ["HDFC Infrastructure Fund"],
        "name_match": ["hdfc infrastructure fund", "infrastructure fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Infrastructure Fund",
    },
    {
        "search_query": ["HDFC Hybrid Equity Fund", "HDFC Aggressive Hybrid Fund", "Aggressive Hybrid"],
        "name_match": ["hdfc hybrid equity fund", "hdfc aggressive hybrid fund", "aggressive hybrid fund", "hybrid equity fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Hybrid Equity Fund",
    },
    {
        "search_query": ["HDFC Housing Opportunities Fund"],
        "name_match": ["hdfc housing opportunities fund", "housing opportunities"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Housing Opportunities Fund",
    },
    {
        "search_query": ["HDFC Focused Fund", "HDFC Focused 30 Fund"],
        "name_match": ["hdfc focused fund", "hdfc focused 30 fund", "focused 30", "focused fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Focused Fund",
    },
    {
        "search_query": ["HDFC Flexi Cap Fund"],
        "name_match": ["hdfc flexi cap fund", "flexi cap fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Flexi Cap Fund",
    },
    {
        "search_query": ["HDFC Equity Savings Fund"],
        "name_match": ["hdfc equity savings fund", "equity savings fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Equity Savings Fund",
    },
    {
        "search_query": ["HDFC ELSS Tax Saver Fund", "HDFC ELSS - Tax Saver", "ELSS Tax Saver"],
        "name_match": ["hdfc elss tax saver", "hdfc elss - tax saver", "elss - tax saver", "elss tax saver"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC ELSS Tax Saver Fund",
    },
    {
        "search_query": ["HDFC Dividend Yield Fund"],
        "name_match": ["hdfc dividend yield fund", "dividend yield fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Dividend Yield Fund",
    },
    {
        "search_query": ["HDFC Defence Fund"],
        "name_match": ["hdfc defence fund", "defence fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Defence Fund",
    },
    {
        "search_query": ["HDFC Consumption Fund"],
        "name_match": ["hdfc consumption fund", "consumption fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Consumption Fund",
    },
    {
        "search_query": ["HDFC Business Cycle Fund"],
        "name_match": ["hdfc business cycle fund", "business cycle fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Business Cycle Fund",
    },
    {
        "search_query": ["HDFC Banking Financial Services Fund", "Banking Financial Services"],
        "name_match": ["hdfc banking financial services fund", "banking financial services", "banking  financial services"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Banking Financial Services Fund",
    },
    {
        "search_query": ["HDFC Balanced Advantage Fund", "Balanced Advantage"],
        "name_match": ["hdfc balanced advantage fund", "balanced advantage fund"],
        "output_folder": RAW_HDFC_FOLDER / "HDFC Balanced Advantage Fund",
    },
]

# Date Range Configuration
START_YEAR, START_MONTH = 2026, 8
END_YEAR, END_MONTH = 2026, 8

MONTH_NUM = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
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
    match = re.search(r"(\d{1,2})[\s\-]+([A-Za-z]+)[\s\-]+(\d{4})", display_name)
    if not match:
        return None, None
    day_str, month_str, year_str = match.groups()
    month = MONTH_NUM.get(month_str.strip().lower())
    if month is None:
        return None, None
    return int(year_str), month

def download_file(href, display_name, dest_folder):
    filename = sanitize_filename(Path(display_name).name)
    dest_folder.mkdir(parents=True, exist_ok=True)
    dest_path = dest_folder / filename

    if dest_path.exists():
        print(f"  [SKIP] Already downloaded: {filename}")
        return dest_path, False

    response = requests.get(href, headers=REQUEST_HEADERS, timeout=60)
    response.raise_for_status()

    dest_path.write_bytes(response.content)
    print(f"  [OK] Downloaded: {filename}")
    return dest_path, True

def main():
    URL = "https://www.hdfcfund.com/statutory-disclosure/portfolio/monthly-portfolio"

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument(f"user-agent={REQUEST_HEADERS['User-Agent']}")

    driver = webdriver.Chrome(options=options)

    try:
        print("=" * 90)
        print("DOWNLOADING HDFC MONTHLY PORTFOLIO FILES")
        print("=" * 90)
        print(f"Target Range : {START_MONTH}/{START_YEAR} to {END_MONTH}/{END_YEAR}")
        print("Navigating to:", URL)
        driver.get(URL)
        time.sleep(3)

        print("Scanning portal and loading all files on page...")
        last_count = 0
        for i in range(35):
            anchors = driver.find_elements(By.CSS_SELECTOR, "a[class*='listdiv'], a[class*='style_listdiv']")
            if len(anchors) == last_count and i > 4:
                break
            last_count = len(anchors)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)

        anchors = driver.find_elements(By.CSS_SELECTOR, "a[class*='listdiv'], a[class*='style_listdiv']")
        print(f"Loaded {len(anchors)} file entries from portal.")

        all_files = []
        for a in anchors:
            text = a.text.strip().replace("\n", " ")
            href = a.get_attribute("href")
            if href and (href.endswith(".xlsx") or href.endswith(".xls")):
                all_files.append((text, href))

        downloaded_count = 0
        already_had_count = 0
        not_found = []

        for fund in FUNDS:
            name_matches = fund["name_match"]
            folder = fund["output_folder"]
            matched_file = None

            for text, href in all_files:
                text_lower = text.lower()
                if any(m in text_lower for m in name_matches):
                    yr, mo = parse_date_from_display_name(text)
                    if yr is not None and mo is not None and in_target_range(yr, mo):
                        matched_file = (text, href)
                        break

            if matched_file:
                text, href = matched_file
                print(f"\n[+] {folder.name}: {text}")
                dest_path, is_new = download_file(href, text, folder)
                if is_new:
                    downloaded_count += 1
                else:
                    already_had_count += 1
            else:
                print(f"\n[-] {folder.name}: NOT FOUND in target range")
                not_found.append(folder.name)

        print("\n" + "=" * 90)
        print("HDFC DOWNLOAD SUMMARY")
        print("=" * 90)
        print(f"Total Funds Configured : {len(FUNDS)}")
        print(f"Newly Downloaded       : {downloaded_count}")
        print(f"Already Present        : {already_had_count}")
        print(f"Total Found & Verified : {downloaded_count + already_had_count} / {len(FUNDS)}")
        print(f"Not Found              : {len(not_found)} {not_found}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
