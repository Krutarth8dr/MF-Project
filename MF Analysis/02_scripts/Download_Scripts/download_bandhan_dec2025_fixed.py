import sys
import time
import shutil
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


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

RAW_BASE_DIR = Path(r"d:\MF Project\MF Analysis\01_raw_files\BANDHAN_MF")
TARGET_DIR = RAW_BASE_DIR / "2025" / "12"
TARGET_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DL_DIR = RAW_BASE_DIR / "_temp_dl_dec2025"
TEMP_DL_DIR.mkdir(parents=True, exist_ok=True)

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

    driver.execute_script("arguments[0].click();", btn)
    time.sleep(0.3)

    # First try exact match (ignoring case)
    matches = [
        li for li in driver.find_elements(By.XPATH, "//ul//li")
        if li.text.strip().lower() == target_text.lower()
    ]
    
    # Second try normalized (without hyphens / spaces)
    if not matches:
        def norm(s): return s.lower().replace("-", " ").replace("  ", " ").strip()
        matches = [
            li for li in driver.find_elements(By.XPATH, "//ul//li")
            if norm(li.text.strip()) == norm(target_text)
        ]

    # Third try substring match
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
        try: f.unlink()
        except Exception: pass

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
            if dest_file.exists():
                dest_file.unlink()
            shutil.move(str(dl_file), str(dest_file))
            return True

    return False

def main():
    print("=" * 80)
    print("BANDHAN MF - DOWNLOADING DECEMBER 2025 FILES (From 2026/December Section)")
    print(f"Target Directory: {TARGET_DIR}")
    print("=" * 80)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1050")
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

    try:
        url = "https://bandhanmutual.com/statutory-disclosures/scheme-portfolios/monthly-half-yearly"
        print("Navigating to URL...")
        driver.get(url)
        time.sleep(5)
        wait_for_spinner(driver)

        # Select Year 2026
        print("Selecting Year: 2026...")
        if not select_dropdown_item(driver, 0, "2026"):
            print("[FAIL] Failed to select Year 2026")
            return

        # Select Month December
        print("Selecting Month: December...")
        if not select_dropdown_item(driver, 1, "December"):
            print("[FAIL] Failed to select Month December")
            return

        success_count = 0
        skip_count = 0
        fail_count = 0

        for idx, fund_name in enumerate(TARGET_FUNDS, 1):
            dest_file = TARGET_DIR / f"{fund_name} - 2025-12.xlsx"
            if dest_file.exists() and dest_file.stat().st_size > 1000:
                print(f"[{idx}/{len(TARGET_FUNDS)}] (SKIP - exists) {fund_name}")
                skip_count += 1
                continue

            print(f"[{idx}/{len(TARGET_FUNDS)}] Querying: {fund_name}...", end=" ", flush=True)
            if not select_dropdown_item(driver, 2, fund_name):
                print("[NOT FOUND] Not found in scheme dropdown")
                fail_count += 1
                continue

            ok = download_active_file(driver, dest_file)
            if ok:
                size_kb = dest_file.stat().st_size / 1024
                print(f"[OK] Downloaded ({size_kb:.1f} KB)")
                success_count += 1
            else:
                print("[FAIL] No file button or download timed out")
                fail_count += 1


        print("\n" + "=" * 80)
        print(f"SUMMARY: {success_count} downloaded, {skip_count} skipped, {fail_count} failed")
        print("=" * 80)

    finally:
        driver.quit()
        shutil.rmtree(TEMP_DL_DIR, ignore_errors=True)

if __name__ == "__main__":
    main()
