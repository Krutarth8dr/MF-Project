import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "SUNDARAM"
RAW_FOLDER.mkdir(parents=True, exist_ok=True)

PAGE_URL = "https://www.sundarammutual.com/monthly-fortnightly-adhoc-portfolios"
AJAX_URL = "https://www.sundarammutual.com/ajax/Modules_Disclosure_Monthly_Fortnightly_Adhoc_Portfolios,App_Web_2fjxvqiq.ashx?_method=GetCategory&_session=no"

START_DATE = datetime(2024, 10, 1)
END_DATE = datetime(2026, 8, 31)

MONTH_MAP = {
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


def fetch_sundaram_monthly_catalog(session):
    print("[1/3] Querying Sundaram AjaxPro endpoint for Monthly Portfolios...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Referer": PAGE_URL,
        "X-AjaxPro-Method": "GetCategory",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    r = session.post(AJAX_URL, data="Catid=Monthly", headers=headers, timeout=30)
    r.raise_for_status()

    res_text = r.text.strip()
    if res_text.startswith("'") and res_text.endswith("';/*"):
        res_text = res_text[1:-4]
    elif res_text.startswith("'") and res_text.endswith("'"):
        res_text = res_text[1:-1]

    res_text = res_text.replace(r"\'", "'").replace(r'\"', '"').replace(r"\\", "\\")

    soup = BeautifulSoup(res_text, "html.parser")
    accordions = soup.find_all(class_="accordion-item")

    catalog = []
    for acc in accordions:
        header = acc.find(class_="accordion-header")
        fin_year = header.text.strip() if header else ""

        tab_panes = acc.find_all(class_="tab-pane")
        for pane in tab_panes:
            pane_id = pane.get("id")
            btn = acc.find("button", attrs={"data-bs-target": f"#{pane_id}"})
            mo_name = btn.text.strip() if btn else ""

            links = pane.find_all("a")
            for a in links:
                title = a.text.strip()
                href = a.get("href", "")

                if "equity" not in title.lower():
                    continue

                mo_num = MONTH_MAP.get(mo_name.lower().strip())
                if not mo_num:
                    m = re.search(r"([a-zA-Z]+)\s*[-_ ]?\s*(\d{4})", title)
                    if m:
                        mo_num = MONTH_MAP.get(m.group(1).lower().strip())
                        yr_val = int(m.group(2))
                    else:
                        continue
                else:
                    try:
                        start_yr, end_yr = [int(y) for y in fin_year.split("-")]
                        yr_val = start_yr if mo_num >= 4 else end_yr
                    except Exception:
                        m = re.search(r"(\d{4})", title)
                        yr_val = int(m.group(1)) if m else 2026

                dt = datetime(yr_val, mo_num, 1)

                if START_DATE <= dt <= END_DATE:
                    full_url = "https://www.sundarammutual.com" + href if not href.startswith("http") else href
                    catalog.append({
                        "dt": dt,
                        "year": yr_val,
                        "month": mo_num,
                        "title": title,
                        "url": full_url,
                    })

    catalog.sort(key=lambda x: x["dt"])
    print(f"[2/3] Found {len(catalog)} monthly equity portfolio workbooks (Oct 2024 - Aug 2026).")
    return catalog


def run_download():
    print("=" * 75)
    print("SUNDARAM MUTUAL FUND - MONTHLY PORTFOLIO DOWNLOADER")
    print(f"Target Date Range: {START_DATE.strftime('%b %Y')} to {END_DATE.strftime('%b %Y')}")
    print(f"Raw Output Folder: {RAW_FOLDER}")
    print("=" * 75)

    session = requests.Session(impersonate="chrome124")
    catalog = fetch_sundaram_monthly_catalog(session)

    downloaded = 0
    skipped = 0
    failed = 0

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Referer": PAGE_URL,
    }

    print("\n[3/3] Downloading monthly consolidated workbooks...")
    for item in catalog:
        dt = item["dt"]
        url = item["url"]
        month_label = dt.strftime("%b %Y")

        y = dt.year
        m = dt.month

        target_dir = RAW_FOLDER / str(y) / f"{m:02d}"
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = os.path.basename(url.split("?")[0])
        target_file = target_dir / filename

        if target_file.exists() and target_file.stat().st_size > 10000:
            print(f"  [SKIPPED] [{month_label}] -> {filename} (size: {target_file.stat().st_size:,} bytes)")
            skipped += 1
            continue

        print(f"  [DOWNLOADING] [{month_label}] -> {filename} ... ", end="", flush=True)

        success = False
        for attempt in range(1, 4):
            try:
                r = session.get(url, headers=headers, timeout=60)
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(target_file, "wb") as f:
                        f.write(r.content)
                    print(f"DONE ({len(r.content):,} bytes)")
                    downloaded += 1
                    success = True
                    break
                else:
                    print(f"[Retry {attempt}: {r.status_code}] ", end="", flush=True)
                    time.sleep(2)
            except Exception as e:
                print(f"[Retry {attempt}: {e}] ", end="", flush=True)
                time.sleep(2)

        if not success:
            print("FAILED")
            failed += 1

    print("\n" + "=" * 75)
    print("DOWNLOAD SUMMARY:")
    print(f"  Total target files: {len(catalog)}")
    print(f"  Newly downloaded:   {downloaded}")
    print(f"  Already existed:    {skipped}")
    print(f"  Failed:             {failed}")
    print("=" * 75)


if __name__ == "__main__":
    run_download()
