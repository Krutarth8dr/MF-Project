import os
import re
import sys
import time
import shutil
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Force UTF-8 output on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# ==============================================================================
# CONFIGURATION
# ==============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
RAW_BASE_DIR = PROJECT_ROOT / "01_raw_files" / "BANDHAN_MF"
RAW_BASE_DIR.mkdir(parents=True, exist_ok=True)

TEMP_DL_DIR = RAW_BASE_DIR / "_temp_dl"
TEMP_DL_DIR.mkdir(parents=True, exist_ok=True)

DISCLOSURES_URL = "https://bandhanmutual.com/statutory-disclosures/scheme-portfolios/monthly-half-yearly"

TARGET_FUNDS = [
    "Bandhan Large and Mid Cap Fund",
    "Bandhan ELSS - Tax Saver Fund",
    "Bandhan Healthcare Fund",
    "Bandhan Balanced Advantage Fund",
    "Bandhan Multi-Factor Fund",
    "Bandhan Transportation And Logistics Fund",
    "Bandhan Business Cycle Fund",
    "Bandhan Long Term Fund",
    "Bandhan Large Cap Fund",



    "Bandhan Infrastructure Fund",
    "Bandhan Innovation Fund",
    "Bandhan Small Cap Fund",
    "Bandhan Financial Services Fund",
    "Bandhan Value Fund",
    "Bandhan Flexi Cap Fund",
    "Bandhan Multi Cap Fund",
    "Bandhan Mid Cap Fund",
]

MONTH_MAP = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}

# Target Months: 2024-10 through 2026-08
MONTH_SCHEDULE = [
    (2024, m) for m in range(10, 13)
] + [
    (2025, m) for m in range(1, 13)
] + [
    (2026, m) for m in range(1, 9)
]

# ==============================================================================
# SELENIUM DRIVER SETUP
# ==============================================================================

def init_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1050")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("prefs", {
        "download.default_directory": str(TEMP_DL_DIR),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    })

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": str(TEMP_DL_DIR)
    })
    return driver


def wait_for_spinner(driver, timeout=12):
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((
                By.XPATH, "//div[contains(@class, 'z-[9999]') or contains(@class, 'backdrop-blur')]"
            ))
        )
    except Exception:
        pass
    time.sleep(0.4)


def select_dropdown_item(driver, button_index: int, target_text: str) -> bool:
    wait_for_spinner(driver)
    buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'border-gray-300')]")
    if button_index >= len(buttons):
        return False
    btn = buttons[button_index]
    if btn.text.strip().lower() == target_text.lower():
        return True

    # Click to open dropdown
    driver.execute_script("arguments[0].click();", btn)
    time.sleep(0.3)

    # Locate option by normalized text
    matches = driver.find_elements(
        By.XPATH, f"//ul//li[normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))='{target_text.lower()}']"
    )
    if not matches:
        matches = [
            li for li in driver.find_elements(By.XPATH, "//ul//li")
            if target_text.lower() in li.text.strip().lower()
        ]

    if not matches:
        driver.execute_script("arguments[0].click();", btn)
        return False

    driver.execute_script("arguments[0].click();", matches[0])
    wait_for_spinner(driver)
    time.sleep(0.4)
    return True


def download_active_file(driver, dest_file: Path, timeout=15) -> bool:
    wait_for_spinner(driver)
    rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'flex items-center') and contains(@class, 'border-b')]")
    valid_rows = [r for r in rows if "bandhan" in r.text.strip().lower()]
    if not valid_rows:
        return False

    # Clear temp download dir
    for f in TEMP_DL_DIR.glob("*"):
        try:
            f.unlink()
        except Exception:
            pass

    row = valid_rows[0]
    btn = row.find_element(By.TAG_NAME, "button")
    driver.execute_script("arguments[0].click();", btn)

    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.5)
        files = [
            f for f in TEMP_DL_DIR.glob("*")
            if not f.name.endswith(".crdownload") and not f.name.endswith(".tmp")
        ]
        if files:
            dl_file = files[0]
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            if dest_file.exists():
                dest_file.unlink()
            shutil.move(str(dl_file), str(dest_file))
            return True

    return False


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    print("=" * 80)
    print("BANDHAN MF - MONTHLY DISCLOSURES DOWNLOADER")
    print(f"Target URL:    {DISCLOSURES_URL}")
    print(f"Funds to fetch: {len(TARGET_FUNDS)}")
    print(f"Months range:  {MONTH_SCHEDULE[0]} to {MONTH_SCHEDULE[-1]} ({len(MONTH_SCHEDULE)} months)")
    print(f"Destination:   {RAW_BASE_DIR}")
    print("=" * 80)

    driver = init_driver()

    try:
        print("\nNavigating to Bandhan disclosures page...")
        driver.get(DISCLOSURES_URL)
        time.sleep(5)
        wait_for_spinner(driver)

        total_downloaded = 0
        total_skipped = 0
        total_not_found = 0
        total_tasks = len(MONTH_SCHEDULE) * len(TARGET_FUNDS)
        task_idx = 0

        for year, month_num in MONTH_SCHEDULE:
            year_str = str(year)
            month_name = MONTH_MAP[month_num]
            target_month_dir = RAW_BASE_DIR / year_str / f"{month_num:02d}"
            target_month_dir.mkdir(parents=True, exist_ok=True)

            print(f"\n[{year_str}-{month_num:02d}] {month_name} {year_str}", flush=True)

            # Select Year & Month
            if not select_dropdown_item(driver, 0, year_str):
                print(f"  ❌ Failed to select Year: {year_str}", flush=True)
                continue

            if not select_dropdown_item(driver, 1, month_name):
                print(f"  ❌ Failed to select Month: {month_name}", flush=True)
                continue

            for fund_name in TARGET_FUNDS:
                task_idx += 1
                dest_file = target_month_dir / f"{fund_name} - {year_str}-{month_num:02d}.xlsx"

                # Check if already downloaded
                if dest_file.exists() and dest_file.stat().st_size > 1000:
                    print(f"  [{task_idx}/{total_tasks}] (SKIP) {fund_name}", flush=True)
                    total_skipped += 1
                    continue

                try:
                    # Select scheme
                    if not select_dropdown_item(driver, 2, fund_name):
                        print(f"  [{task_idx}/{total_tasks}] (NOT FOUND in dropdown) {fund_name}", flush=True)
                        total_not_found += 1
                        continue

                    # Download file
                    success = download_active_file(driver, dest_file)
                    if success:
                        print(f"  [{task_idx}/{total_tasks}] (DONE) {fund_name} -> {dest_file.name} ({dest_file.stat().st_size:,} bytes)", flush=True)
                        total_downloaded += 1
                    else:
                        print(f"  [{task_idx}/{total_tasks}] (NO FILE) {fund_name}", flush=True)
                        total_not_found += 1

                except Exception as err:
                    print(f"  [{task_idx}/{total_tasks}] (EXCEPTION) {fund_name}: {err}", flush=True)
                    total_not_found += 1
                    # Attempt recovery to keep session alive
                    try:
                        driver.get(DISCLOSURES_URL)
                        time.sleep(4)
                        wait_for_spinner(driver)
                        select_dropdown_item(driver, 0, year_str)
                        select_dropdown_item(driver, 1, month_name)
                    except Exception:
                        pass

        print("\n" + "=" * 80, flush=True)
        print("DOWNLOAD SUMMARY", flush=True)
        print(f"Total Downloaded : {total_downloaded}", flush=True)
        print(f"Total Skipped    : {total_skipped}", flush=True)
        print(f"Not Available    : {total_not_found}", flush=True)
        print(f"Files in storage : {len(list(RAW_BASE_DIR.glob('**/*.xlsx')))}", flush=True)
        print("=" * 80, flush=True)

    finally:
        driver.quit()
        # Remove temp download dir
        shutil.rmtree(TEMP_DL_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
