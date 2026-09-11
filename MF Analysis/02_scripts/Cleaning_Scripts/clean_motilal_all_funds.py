"""
Motilal Oswal Mutual Fund - Portfolio Cleaning Script
Extracts equity portfolio holdings for 22 target funds from monthly workbooks (Oct 2024 to Aug 2026).
Cleans and standardizes the data and saves to 03_clean_data/MOTILAL/Motilal_All_Funds_Cleaned.xlsx.
"""

import os
import re
import sys
import calendar
from datetime import datetime
from pathlib import Path
import openpyxl
import xlrd
import pandas as pd

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "MOTILAL"
OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "MOTILAL"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_FOLDER / "Motilal_All_Funds_Cleaned.xlsx"

AMC_NAME = "Motilal Oswal MF"
START_DATE = pd.Timestamp(year=2024, month=10, day=1)
END_DATE = pd.Timestamp(year=2026, month=8, day=31)

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

# Canonical 22 Target Funds (mapped from August 2026 Index)
TARGET_FUNDS_CONFIG = {
    "YO20": "Motilal Oswal Large and Midcap Fund",
    "YO07": "Motilal Oswal Midcap Fund (Formerly known as Motilal Oswal Midcap 30 Fund)",
    "YO46": "Motilal Oswal Small Cap Fund",
    "YO05": "Motilal Oswal Focused Fund (Formerly known as Motilal Oswal Focused 25 Fund)",
    "YO08": "Motilal Oswal Flexi Cap Fund",
    "YO47": "Motilal Oswal Large Cap Fund",
    "YO09": "Motilal Oswal ELSS Tax Saver Fund (Formerly Known as Motilal Oswal Long Term Equity Fund)",
    "YO10": "Motilal Oswal Balanced Advantage Fund (Formerly known as Motilal Oswal Dynamic Fund)",
    "YO50": "Motilal Oswal Quant Fund",
    "YO51": "Motilal Oswal Multicap Fund",
    "YO52": "Motilal Oswal Nifty India Defence Index Fund",
    "YO53": "Motilal Oswal Manufacturing Fund",
    "YO54": "Motilal Oswal Business Cycle Fund",
    "YO58": "Motilal Oswal Digital India Fund",
    "YO65": "Motilal Oswal Innovation Opportunities Fund",
    "YO66": "Motilal Oswal Active Momentum Fund",
    "YO68": "Motilal Oswal Infrastructure Fund",
    "YO72": "Motilal Oswal Services Fund",
    "YO80": "Motilal Oswal Special Opportunities Fund",
    "YO82": "Motilal Oswal Consumption Fund",
    "YO89": "Motilal Oswal Financial Services Fund",
    "YO92": "Motilal Oswal Contra Fund",
}

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


def clean_text(val):
    if val is None:
        return ""
    text = str(val).strip()
    return re.sub(r"\s+", " ", text)


def parse_portfolio_date_from_sheet(sheet_data, file_path):
    """
    Extract portfolio date from header rows of the sheet, falling back to directory path.
    """
    for r in sheet_data[:15]:
        row_str = " ".join([str(c) for c in r if c is not None])
        m = re.search(r"(?:AS ON|AS AT|PORTFOLIO AS ON)\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", row_str, re.I)
        if m:
            m_str, d_str, y_str = m.groups()
            mo_num = MONTH_MAP.get(m_str.lower().strip())
            if mo_num:
                return datetime(int(y_str), mo_num, int(d_str))

        m2 = re.search(r"(?:AS ON|AS AT|PORTFOLIO AS ON)\s+(\d{1,2})[-./](\d{1,2})[-./](\d{4})", row_str, re.I)
        if m2:
            d_str, mo_str, y_str = m2.groups()
            return datetime(int(y_str), int(mo_str), int(d_str))

    # Fallback to directory structure: .../MOTILAL/<YYYY>/<MM>/...
    parts = file_path.parts
    try:
        y = int(parts[-3])
        m = int(parts[-2])
        last_d = calendar.monthrange(y, m)[1]
        return datetime(y, m, last_d)
    except Exception:
        return datetime(2026, 8, 31)


def parse_holdings(sheet_data, fund_code, fund_name, portfolio_dt):
    records = []
    month_str = portfolio_dt.strftime("%Y-%m")
    portfolio_date_str = portfolio_dt.strftime("%Y-%m-%d")

    header_found = False

    for row in sheet_data:
        clean_row = [c for c in row if c is not None and str(c).strip() != ""]
        row_str = " ".join([str(c).strip() for c in clean_row]).lower()

        if "name of" in row_str and ("isin" in row_str or "quantity" in row_str or "market" in row_str):
            header_found = True
            continue

        if not header_found:
            continue

        # Stop scanning on Sub Total or Unlisted or Debt or Money Market or Grand Total
        if any(term in str(c).lower().strip() for c in row if c is not None for term in ["sub total", "sub-total", "subtotal", "unlisted", "debt instruments", "money market", "grand total"]):
            if any(t in row_str for t in ["sub total", "sub-total", "subtotal", "unlisted", "debt instruments", "grand total"]):
                break

        # Look for ISIN starting with INE
        isin_idx = None
        for i, cell in enumerate(row):
            if cell is not None and isinstance(cell, str) and cell.strip().startswith("INE") and len(cell.strip()) == 12:
                isin_idx = i
                break

        if isin_idx is not None:
            isin = clean_text(row[isin_idx])

            # Security Name is the non-empty text before ISIN that is not a numeric / sr no
            sec_name = None
            for i in range(isin_idx - 1, -1, -1):
                val = str(row[i]).strip() if row[i] is not None else ""
                if val and not re.match(r"^\d+(\.0)?$", val) and len(val) > 2:
                    sec_name = clean_text(val)
                    break

            # Industry and Quantity
            industry = ""
            qty = None
            for i in range(isin_idx + 1, len(row)):
                cell = row[i]
                if cell is None or str(cell).strip() == "":
                    continue
                val_str = clean_text(cell)
                try:
                    num = float(str(cell).replace(",", "").strip())
                    if qty is None:
                        qty = num
                except ValueError:
                    if not industry:
                        industry = val_str

            if sec_name and isin and qty is not None and qty > 0:
                records.append({
                    "AMC": AMC_NAME,
                    "Fund_Name": fund_name,
                    "Portfolio_Date": portfolio_date_str,
                    "Month": month_str,
                    "Security_Name": sec_name,
                    "ISIN": isin,
                    "Industry_Rating": industry,
                    "Quantity": int(round(qty)),
                })

    return records


def clean_motilal_data():
    print("=" * 75)
    print("MOTILAL OSWAL MUTUAL FUND - CLEANING PIPELINE")
    print(f"Raw Folder:        {RAW_FOLDER}")
    print(f"Output File:       {OUTPUT_FILE}")
    print(f"Target Date Range: {START_DATE.strftime('%b %Y')} to {END_DATE.strftime('%b %Y')}")
    print(f"Target Funds:      {len(TARGET_FUNDS_CONFIG)} funds")
    print("=" * 75)

    excel_files = sorted(list(RAW_FOLDER.rglob("*.xlsx")) + list(RAW_FOLDER.rglob("*.xls")))
    if not excel_files:
        print(f"ERROR: No monthly files found in {RAW_FOLDER}")
        sys.exit(1)

    print(f"\n[Step 1/3] Found {len(excel_files)} monthly consolidated workbooks to process.")

    all_rows = []

    for file_idx, file_path in enumerate(excel_files, 1):
        ext = file_path.suffix.lower()
        file_holdings_count = 0
        funds_matched = 0

        if ext == ".xls":
            try:
                wb = xlrd.open_workbook(str(file_path))
                sheet_names = wb.sheet_names()
            except Exception as e:
                print(f"  [{file_idx}/{len(excel_files)}] [ERROR] Failed to load .xls {file_path.name}: {e}")
                continue

            # Parse date from a sample sheet
            sample_sh = wb.sheet_by_name(sheet_names[1]) if len(sheet_names) > 1 else wb.sheet_by_name(sheet_names[0])
            sample_data = [[sample_sh.cell_value(r, c) for c in range(sample_sh.ncols)] for r in range(min(15, sample_sh.nrows))]
            portfolio_dt = parse_portfolio_date_from_sheet(sample_data, file_path)

            for code, canonical_name in TARGET_FUNDS_CONFIG.items():
                sname = next((s for s in sheet_names if s.strip().upper() == code.upper() or s.strip().upper() == code.upper().replace("YO", "Y0")), None)
                if not sname:
                    continue

                sh = wb.sheet_by_name(sname)
                sheet_data = [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
                recs = parse_holdings(sheet_data, code, canonical_name, portfolio_dt)
                if recs:
                    funds_matched += 1
                    file_holdings_count += len(recs)
                    all_rows.extend(recs)

        else:
            try:
                wb = openpyxl.load_workbook(file_path, data_only=True)
                sheet_names = wb.sheetnames
            except Exception as e:
                print(f"  [{file_idx}/{len(excel_files)}] [ERROR] Failed to load .xlsx {file_path.name}: {e}")
                continue

            sample_sh = wb[sheet_names[1]] if len(sheet_names) > 1 else wb[sheet_names[0]]
            sample_data = list(sample_sh.iter_rows(values_only=True))[:15]
            portfolio_dt = parse_portfolio_date_from_sheet(sample_data, file_path)

            for code, canonical_name in TARGET_FUNDS_CONFIG.items():
                sname = next((s for s in sheet_names if s.strip().upper() == code.upper() or s.strip().upper() == code.upper().replace("YO", "Y0")), None)
                if not sname:
                    continue

                sh = wb[sname]
                sheet_data = list(sh.iter_rows(values_only=True))
                recs = parse_holdings(sheet_data, code, canonical_name, portfolio_dt)
                if recs:
                    funds_matched += 1
                    file_holdings_count += len(recs)
                    all_rows.extend(recs)

        print(f"  [{file_idx:2d}/{len(excel_files):2d}] {portfolio_dt.strftime('%b %Y')} ({file_path.name}) -> {funds_matched}/{len(TARGET_FUNDS_CONFIG)} funds, {file_holdings_count} holdings")

    print("\n[Step 2/3] Compiling cleaned dataset...")
    if not all_rows:
        print("ERROR: No valid equity holdings extracted!")
        sys.exit(1)

    df = pd.DataFrame(all_rows, columns=STANDARD_COLUMNS)

    # Convert types
    df["Portfolio_Date"] = pd.to_datetime(df["Portfolio_Date"])
    df["Quantity"] = df["Quantity"].astype("int64")

    # Sort dataset cleanly
    df = df.sort_values(["Portfolio_Date", "Fund_Name", "Security_Name"]).reset_index(drop=True)

    print(f"Total rows extracted: {len(df):,}")
    print(f"Unique funds:         {df['Fund_Name'].nunique()}")
    print(f"Unique ISINs:         {df['ISIN'].nunique()}")
    print(f"Unique months:        {df['Month'].nunique()}")
    print(f"Date range:           {df['Portfolio_Date'].min().strftime('%d-%b-%Y')} to {df['Portfolio_Date'].max().strftime('%d-%b-%Y')}")

    print("\n[Step 3/3] Saving cleaned data to Excel...")
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"Saved successfully: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size:,} bytes)")
    print("=" * 75)


if __name__ == "__main__":
    clean_motilal_data()
