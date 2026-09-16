import os
import re
import sys
import time
import shutil
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# ==============================================================================
# SETTINGS & CONFIGURATION
# ==============================================================================

# Windows console cp1252 handling
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
RAW_BASE_DIR = PROJECT_ROOT / "01_raw_files" / "TRUST_MF"
RAW_BASE_DIR.mkdir(parents=True, exist_ok=True)

TEMP_DOWNLOAD_DIR = RAW_BASE_DIR / "_temp_dl"
TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

DISCLOSURES_URL = "https://www.trustmf.com/disclosures?activeTab=portfolio-disclosures"

START_MONTH = "2024-10"
END_MONTH = "2026-08"

# Optional: also download 2024-08 if available
EXTRA_MONTHS = ["2024-08"]


def init_driver(download_path: Path):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1050")
    options.add_experimental_option("prefs", {
        "download.default_directory": str(download_path),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    })
    return webdriver.Chrome(options=options)


def wait_for_download(download_path: Path, timeout: int = 20):
    start = time.time()
    while time.time() - start < timeout:
        files = [f for f in os.listdir(download_path) if not f.endswith(".crdownload") and not f.endswith(".tmp")]
        if files:
            return download_path / files[0]
        time.sleep(0.5)
    return None


def run_download():
    print("=" * 75)
    print("TRUST MF - MONTHLY PORTFOLIO DISCLOSURES DOWNLOADER")
    print(f"Target URL:    {DISCLOSURES_URL}")
    print(f"Target Range:  {START_MONTH} to {END_MONTH}")
    print(f"Destination:   {RAW_BASE_DIR}")
    print("=" * 75)

    driver = init_driver(TEMP_DOWNLOAD_DIR)

    try:
        print("\nNavigating to disclosures page...")
        driver.get(DISCLOSURES_URL)
        time.sleep(5)

        buttons = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label*="TRUSTMF Monthly Portfolio Report as on"]')
        print(f"Found {len(buttons)} monthly report download buttons on page.")

        download_targets = []
        for btn in buttons:
            label = btn.get_attribute("aria-label") or ""
            m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", label)
            if not m:
                continue

            day_str, mo_str, yr_str = m.group(1), m.group(2), m.group(3)
            month_key = f"{yr_str}-{mo_str}"

            if (START_MONTH <= month_key <= END_MONTH) or (month_key in EXTRA_MONTHS):
                download_targets.append({
                    "month_key": month_key,
                    "year": yr_str,
                    "month": mo_str,
                    "day": day_str,
                    "label": label,
                    "button": btn,
                })

        print(f"Matched {len(download_targets)} monthly disclosure targets for download.")

        # Sort chronologically
        download_targets.sort(key=lambda x: x["month_key"])

        success_count = 0
        skip_count = 0

        for target in download_targets:
            yr = target["year"]
            mo = target["month"]
            mo_key = target["month_key"]
            target_dir = RAW_BASE_DIR / yr / mo
            target_dir.mkdir(parents=True, exist_ok=True)

            # Check if file already exists in target_dir
            existing = list(target_dir.glob("*.*"))
            if existing:
                print(f"  [{mo_key}] Already exists: {existing[0].name} (skipping)")
                skip_count += 1
                continue

            # Clear temp directory
            for f in TEMP_DOWNLOAD_DIR.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass

            print(f"  [{mo_key}] Downloading: {target['label']}...")
            btn = target["button"]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.5)
            btn.click()

            downloaded_file = wait_for_download(TEMP_DOWNLOAD_DIR, timeout=20)
            if not downloaded_file:
                print(f"    ⚠️ Timeout waiting for download of {mo_key}")
                continue

            # Keep original extension or determine from filename
            ext = downloaded_file.suffix or ".xls"
            dest_file = target_dir / f"TRUSTMF_Monthly_Portfolio_{yr}_{mo}{ext}"
            shutil.move(str(downloaded_file), str(dest_file))
            print(f"    [OK] Saved: {dest_file.name} ({dest_file.stat().st_size:,} bytes)")
            success_count += 1
            time.sleep(1)

        print("\n" + "=" * 75)
        print(f"DOWNLOAD COMPLETE: {success_count} downloaded, {skip_count} skipped.")
        print("=" * 75)

    finally:
        driver.quit()
        if TEMP_DOWNLOAD_DIR.exists():
            shutil.rmtree(TEMP_DOWNLOAD_DIR, ignore_errors=True)


if __name__ == "__main__":
    run_download()
