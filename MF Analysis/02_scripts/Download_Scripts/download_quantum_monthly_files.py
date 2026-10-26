"""
Download monthly combined portfolio disclosure files for Quantum Mutual Fund (Quantum MF).

Source:
    Website: https://www.quantumamc.com/portfolio/combined/-1/1/0/0
    API Endpoint: https://www.quantumamc.com/ProductPortfolio/GetProductPortfolioPaginatedList

Target Funds (6 funds inside combined workbooks):
    1. QLTEVF   -> Quantum Value Fund
    2. QTSF     -> Quantum ELSS Tax Saver Fund
    3. QSCAPF   -> Quantum Small Cap Fund
    4. QMULTI   -> Quantum Multi Asset Allocation Fund
    5. QETHICAL -> Quantum Ethical Fund
    6. QFLEXI   -> Quantum Flexi Cap Fund

Target Period:
    October 2024 to September 2026 (24 consecutive months).

Stores raw files in:
    01_raw_files/Quantum_MF/<YYYY>/<MM>/Quantum_Combined_Portfolio_<YYYY>_<MM>.xlsx
"""

import os
import sys
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "Quantum_MF"
RAW_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "https://www.quantumamc.com/ProductPortfolio/GetProductPortfolioPaginatedList"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.quantumamc.com/portfolio/combined/-1/1/0/0",
    "X-Requested-With": "XMLHttpRequest",
}

# Explicit verified mapping of all 24 months for guaranteed reproducibility
KNOWN_MONTHLY_FILES = {
    ("2024", "10"): "https://www.quantumamc.com/FileCDN/FactSheet/1dda8689-fa86-4e7c-829f-8276c0cee191.xlsx",
    ("2024", "11"): "https://www.quantumamc.com/FileCDN/FactSheet/05bd3499-1f25-481a-ac0a-fede6af148e8.xlsx",
    ("2024", "12"): "https://www.quantumamc.com/FileCDN/FactSheet/0339bffa-1064-4110-a309-5a08b304bf54.xlsx",
    ("2025", "01"): "https://www.quantumamc.com/FileCDN/FactSheet/0de9ed96-b41f-4bbc-b624-da5f7e959c9d.xlsx",
    ("2025", "02"): "https://www.quantumamc.com/FileCDN/FactSheet/767b9bf3-1f14-40ba-8146-e12eea5bdad7.xlsx",
    ("2025", "03"): "https://www.quantumamc.com/FileCDN/FactSheet/7fa56d03-0c61-4321-8c50-88b708bb1f12.xlsx",
    ("2025", "04"): "https://www.quantumamc.com/FileCDN/FactSheet/d613c204-c40a-4424-99c1-c126637106ef.xlsx",
    ("2025", "05"): "https://www.quantumamc.com/FileCDN/FactSheet/4453306a-8a56-4883-a298-9110c434b0a0.xlsx",
    ("2025", "06"): "https://www.quantumamc.com/FileCDN/FactSheet/bfcb6fe4-d521-47f0-b9fd-d6f0918671e0.xlsx",
    ("2025", "07"): "https://www.quantumamc.com/FileCDN/FactSheet/f22c3932-34a1-441d-8fba-6a02fb6e0506.xlsx",
    ("2025", "08"): "https://www.quantumamc.com/FileCDN/FactSheet/3c1c097c-80af-4f65-9070-06fc9b89d37b.xlsx",
    ("2025", "09"): "https://www.quantumamc.com/FileCDN/FactSheet/53b808a8-2646-4dff-af72-e56558d5587f.xlsx",
    ("2025", "10"): "https://www.quantumamc.com/FileCDN/FactSheet/63507f28-a2c3-4f65-bedc-fe8ce162bf65.xlsx",
    ("2025", "11"): "https://www.quantumamc.com/FileCDN/FactSheet/0ea2bc67-bfa9-4672-8acb-4a57ab794212.xlsx",
    ("2025", "12"): "https://www.quantumamc.com/FileCDN/FactSheet/d3cb2692-3209-4fe9-8ee6-078502b2828f.xlsx",
    ("2026", "01"): "https://www.quantumamc.com/FileCDN/FactSheet/b6f73754-008a-48df-98cf-7e387bd02e47.xlsx",
    ("2026", "02"): "https://www.quantumamc.com/FileCDN/FactSheet/62cd6b26-9cea-480d-8de1-bd331661c6b9.xlsx",
    ("2026", "03"): "https://www.quantumamc.com/FileCDN/FactSheet/3ef1f1c6-99f0-4251-97aa-4e6f770bf6f2.xlsx",
    ("2026", "04"): "https://www.quantumamc.com/FileCDN/FactSheet/67126745-1c42-42c8-967f-87bf24b05981.xlsx",
    ("2026", "05"): "https://www.quantumamc.com/FileCDN/FactSheet/cb50090a-93af-4863-a4cb-18ef81c6b14c.xlsx",
    ("2026", "06"): "https://www.quantumamc.com/FileCDN/FactSheet/83d3ddb2-d731-4039-9884-8159ee1976ff.xlsx",
    ("2026", "07"): "https://www.quantumamc.com/FileCDN/FactSheet/d701fe6a-e00f-4291-a9f3-47e40f4946da.xlsx",
    ("2026", "08"): "https://www.quantumamc.com/FileCDN/FactSheet/f616b3fb-f263-439d-81da-d4663a287aed.xlsx",
    ("2026", "09"): "https://www.quantumamc.com/FileCDN/FactSheet/18650bf5-c7b8-47b1-a725-78a86416c1a5.xlsx",
}


def download_single_file(year, month, file_url, session=None):
    """Download single combined monthly workbook."""
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)

    dest_filename = f"Quantum_Combined_Portfolio_{year}_{month}.xlsx"
    target_dir = RAW_DIR / year / month
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / dest_filename

    if target_path.exists() and target_path.stat().st_size > 1024:
        return {
            "year": year,
            "month": month,
            "path": target_path,
            "size": target_path.stat().st_size,
            "status": "EXISTS",
            "url": file_url,
        }

    for attempt in range(1, 4):
        try:
            resp = session.get(file_url, headers=HEADERS, timeout=45)
            if resp.status_code == 200 and len(resp.content) > 1024:
                with open(target_path, "wb") as f:
                    f.write(resp.content)
                return {
                    "year": year,
                    "month": month,
                    "path": target_path,
                    "size": len(resp.content),
                    "status": "DOWNLOADED",
                    "url": file_url,
                }
            else:
                if attempt == 3:
                    return {
                        "year": year,
                        "month": month,
                        "path": None,
                        "size": len(resp.content) if resp.status_code == 200 else 0,
                        "status": f"FAILED (HTTP {resp.status_code})",
                        "url": file_url,
                    }
                time.sleep(2)
        except Exception as e:
            if attempt == 3:
                return {
                    "year": year,
                    "month": month,
                    "path": None,
                    "size": 0,
                    "status": f"ERROR: {e}",
                    "url": file_url,
                }
            time.sleep(2)


def main():
    print("=" * 80)
    print("Quantum MF Monthly Portfolio Downloader")
    print(f"Target Directory: {RAW_DIR}")
    print(f"Total files to process: {len(KNOWN_MONTHLY_FILES)}")
    print("=" * 80)

    session = requests.Session()
    session.headers.update(HEADERS)

    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(download_single_file, yr, mo, url, session): (yr, mo)
            for (yr, mo), url in KNOWN_MONTHLY_FILES.items()
        }
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            print(f"[{res['status']:10}] {res['year']}-{res['month']} | {res['size']:,} bytes -> {res['url'].split('/')[-1]}")

    print("\n" + "=" * 80)
    success = [r for r in results if r["status"] in ("DOWNLOADED", "EXISTS")]
    failed = [r for r in results if r["status"] not in ("DOWNLOADED", "EXISTS")]
    print(f"SUMMARY: {len(success)} succeeded, {len(failed)} failed out of {len(KNOWN_MONTHLY_FILES)} total files.")
    if failed:
        print("Failed files:")
        for r in failed:
            print(f"  - {r['year']}-{r['month']}: {r['status']} ({r['url']})")
    print("=" * 80)


if __name__ == "__main__":
    main()
