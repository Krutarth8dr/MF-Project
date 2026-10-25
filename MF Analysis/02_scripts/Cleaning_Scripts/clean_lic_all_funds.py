"""
Clean all downloaded monthly portfolio files for LIC Mutual Fund (LIC MF).

Process:
    - Reads all files in 01_raw_files/LIC_MF/<YYYY>/<MM>/
    - Stops immediately upon encountering 'Sub Total', '(b)Unlisted', '(b) Unlisted', or 'Total'
    - Filters for valid listed Indian equities (ISIN starts with INE, length 12, quantity > 0)
    - Generates 03_clean_data/LIC_MF/LIC_MF_All_Funds_Cleaned.xlsx
"""

import sys
import os
import calendar
from datetime import datetime
from pathlib import Path
import openpyxl
import pandas as pd

# Windows consoles default to cp1252, force UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "01_raw_files" / "LIC_MF"
CLEAN_DIR = PROJECT_ROOT / "03_clean_data" / "LIC_MF"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = CLEAN_DIR / "LIC_MF_All_Funds_Cleaned.xlsx"

FUND_CODE_MAP = {
    "LEULIS": "LIC MF Unit Linked Insurance Scheme",
    "LEEQTF": "LIC MF Flexi Cap Fund",
    "LEMIDF": "LIC MF Large & Mid Cap Fund",
    "LEBFSF": "LIC MF Banking and Financial Services Fund",
    "LEMUCF": "LIC MF Multi Cap Fund",
    "LEDDYF": "LIC MF Dividend Yield Fund",
    "LEFE30": "LIC MF Focused Fund",
    "LEEMCF": "LIC MF Mid Cap Fund",
    "LEDHCF": "LIC MF Healthcare Fund",
    "LEESCF": "LIC MF Small Cap Fund",
    "LEGROW": "LIC MF Large Cap Fund",
    "LELTVF": "LIC MF Value Fund",
    "LEMFGF": "LIC MF Manufacturing Fund",
    "LECOSF": "LIC MF Consumption Fund",
    "LETECF": "LIC MF Technology Fund",
    "LETAXP": "LIC MF ELSS Tax Saver Fund",
    "LEINFA": "LIC MF Infrastructure Fund",
}

STOP_TERMS = ["sub total", "(b)unlisted", "(b) unlisted", "total"]

STANDARD_COLUMNS = [
    "AMC",
    "Fund_Name",
    "Portfolio_Date",
    "Month",
    "Security_Name",
    "ISIN",
    "Industry_Rating",
    "Quantity",
]


def clean_file(file_path):
    """Parses a single LIC MF portfolio file and extracts listed equity holdings."""
    holdings = []
    try:
        # Determine year and month from directory structure: LIC_MF/<YYYY>/<MM>/...
        month = int(file_path.parent.name)
        year = int(file_path.parent.parent.name)

        last_day = calendar.monthrange(year, month)[1]
        portfolio_date = f"{year}-{month:02d}-{last_day:02d}"
        month_str = datetime.strptime(f"{year}-{month:02d}-01", "%Y-%m-%d").strftime("%b-%Y")

        prefix = file_path.name.split("_")[0].strip()
        fund_name = FUND_CODE_MAP.get(prefix, prefix)

        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active

        # Locate header row and column mapping
        header_row = None
        col_map = {}
        for r in range(1, 15):
            row_vals = [str(ws.cell(row=r, column=c).value or "").strip() for c in range(1, ws.max_column + 1)]
            lower_vals = [v.lower() for v in row_vals]
            if any("isin" in v for v in lower_vals) and any("instrument" in v or "name" in v for v in lower_vals):
                header_row = r
                for c_idx, val in enumerate(lower_vals, 1):
                    if "isin" in val:
                        col_map["isin"] = c_idx
                    elif ("instrument" in val or "name" in val) and "yield" not in val:
                        col_map["name"] = c_idx
                    elif "rating" in val or "industry" in val:
                        col_map["rating"] = c_idx
                    elif "quantity" in val or "qty" in val:
                        col_map["qty"] = c_idx
                break

        if not header_row or "isin" not in col_map or "name" not in col_map or "qty" not in col_map:
            return []

        for r in range(header_row + 1, ws.max_row + 1):
            name_val = str(ws.cell(row=r, column=col_map["name"]).value or "").strip()
            isin_val = str(ws.cell(row=r, column=col_map["isin"]).value or "").strip()

            name_lower = name_val.lower()
            isin_lower = isin_val.lower()

            # Immediate stop condition
            if any(term in name_lower or term in isin_lower for term in STOP_TERMS):
                break

            # Filter for listed equity
            if not (isin_val.startswith("INE") and len(isin_val) == 12):
                continue

            qty_val = ws.cell(row=r, column=col_map["qty"]).value
            try:
                qty = float(qty_val)
            except (ValueError, TypeError):
                continue

            if qty <= 0:
                continue

            rating_val = ""
            if "rating" in col_map:
                rating_val = str(ws.cell(row=r, column=col_map["rating"]).value or "").strip()

            holdings.append({
                "AMC": "LIC MF",
                "Fund_Name": fund_name,
                "Portfolio_Date": portfolio_date,
                "Month": month_str,
                "Security_Name": name_val,
                "ISIN": isin_val,
                "Industry_Rating": rating_val,
                "Quantity": qty,
            })

    except Exception as e:
        print(f"  [ERROR] {file_path.name}: {e}")

    return holdings


def main():
    print("=" * 80)
    print("LIC MF - Portfolio Cleaning Pipeline")
    print("=" * 80)

    files = sorted(list(RAW_DIR.rglob("*.xls*")))
    print(f"Found {len(files)} portfolio files in {RAW_DIR}")

    all_holdings = []
    for idx, f in enumerate(files, 1):
        file_holdings = clean_file(f)
        all_holdings.extend(file_holdings)
        if idx % 50 == 0 or idx == len(files):
            print(f"[{idx:3d}/{len(files)}] Processed... ({idx} files, {len(all_holdings)} holdings accumulated)")

    if not all_holdings:
        print("❌ No holdings extracted. Please check input raw files.")
        return

    df = pd.DataFrame(all_holdings)[STANDARD_COLUMNS]

    # Deduplicate exact duplicate rows if any
    initial_len = len(df)
    df.drop_duplicates(subset=["AMC", "Fund_Name", "Portfolio_Date", "ISIN", "Security_Name"], inplace=True)
    if len(df) < initial_len:
        print(f"Deduplicated {initial_len - len(df)} duplicate records.")

    # Sort deterministically
    df.sort_values(by=["Fund_Name", "Portfolio_Date", "Security_Name"], inplace=True)

    # Save to Excel
    df.to_excel(OUTPUT_FILE, index=False)

    print("\n" + "=" * 80)
    print("Cleaned Data Summary")
    print("=" * 80)
    print(f"Total Records : {len(df)}")
    print(f"Unique AMCs   : {df['AMC'].nunique()} ({df['AMC'].unique().tolist()})")
    print(f"Unique Funds  : {df['Fund_Name'].nunique()}")
    for fund, cnt in df["Fund_Name"].value_counts().items():
        print(f"  - {fund:42} : {cnt:5d} rows")
    print(f"Unique ISINs  : {df['ISIN'].nunique()}")
    print(f"Date Range    : {df['Portfolio_Date'].min()} to {df['Portfolio_Date'].max()} ({df['Portfolio_Date'].nunique()} months)")
    print(f"Output File   : {OUTPUT_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    main()
