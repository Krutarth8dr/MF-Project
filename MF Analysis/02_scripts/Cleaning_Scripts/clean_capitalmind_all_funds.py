"""
Cleaning script for Capital Mind MF (Capitalmind Mutual Fund).
Extracts listed equity holdings from monthly files for 2 target funds:
- CMFLEXI: Capitalmind Flexi Cap Fund
- CMMAAF: Capitalmind Multi Asset Allocation Fund

Stops cleaning as soon as "Sub Total", "(b)Unlisted", or "Total" are detected
in the "Name of the Instrument" column.
Output:
03_clean_data/Capital_Mind_MF/Capital_Mind_MF_All_Funds_Cleaned.xlsx
"""

import datetime
import glob
import io
import os
import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd
import xlrd

# ==============================================================================
# SETTINGS & PATHS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "Capital_Mind_MF"
OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "Capital_Mind_MF"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_FOLDER / "Capital_Mind_MF_All_Funds_Cleaned.xlsx"

AMC_NAME = "Capital Mind MF"

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

TARGET_FUNDS = {
    "CMFLEXI": "Capitalmind Flexi Cap Fund",
    "CMMAAF": "Capitalmind Multi Asset Allocation Fund",
}


def clean_text(val):
    if val is None:
        return ""
    text = str(val).strip()
    return re.sub(r"\s+", " ", text)


def is_stop_instrument(name_val):
    """
    User instruction:
    'stop cleaning as soon as you detect "Sub Total", "(b)Unlisted" "Total" cells containing these things in the "Name of the Instrument" column.'
    """
    if not name_val:
        return False
    lower = clean_text(name_val).lower()
    if not lower:
        return False

    if any(m in lower for m in [
        "sub total",
        "subtotal",
        "sub-total",
        "sub_total",
        "(b)unlisted",
        "(b) unlisted",
        "b) unlisted",
        "b)unlisted",
        "(b)",
        "grand total",
    ]):
        return True

    # Exact or startswith check for 'total' to avoid matching 'Adani Total Gas Ltd'
    if lower in ["total", "total:", "total (a)", "total(a)", "total (b)", "total(b)", "unlisted"]:
        return True
    if lower.startswith(("total (", "total(", "total -", "total:", "grand total")):
        return True

    # Other non-equity asset classes
    if any(t in lower for t in [
        "debt instruments",
        "money market",
        "treasury bill",
        "reverse repo",
        "treps",
        "net current assets",
        "total net assets",
        "derivatives",
    ]):
        return True

    return False


def parse_date_from_row(row_tuple):
    row_str = " ".join(str(c or "") for c in row_tuple)
    if any(w in row_str.lower() for w in ["as on", "statement as on", "portfolio as on"]):
        m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})", row_str)
        if m:
            mname, day, year = m.group(1), m.group(2), m.group(3)
            for fmt in ("%B %d %Y", "%b %d %Y"):
                try:
                    dt = datetime.datetime.strptime(f"{mname} {day} {year}", fmt)
                    return dt.strftime("%Y-%m-%d"), dt.strftime("%b-%Y")
                except Exception:
                    continue
    return None, None


def clean_quantity(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None
    s = str(val).strip().replace(",", "")
    try:
        f = float(s)
        return f if f > 0 else None
    except ValueError:
        return None


def get_fund_code_from_file(file_path):
    fname = file_path.name.upper()
    if "CMMAAF" in fname:
        return "CMMAAF"
    if "CMFLEXI" in fname or "CAPITALMIND_MONTHLY" in fname:
        return "CMFLEXI"
    return None


def clean_workbook(file_path, default_date, default_month):
    code = get_fund_code_from_file(file_path)
    if not code or code not in TARGET_FUNDS:
        return []

    fund_name = TARGET_FUNDS[code]

    with open(file_path, "rb") as fp:
        wb = openpyxl.load_workbook(io.BytesIO(fp.read()), data_only=True, read_only=True)

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return []

    # Detect date from rows 0 to 6
    portfolio_date, month_str = None, None
    for r in rows[:7]:
        p_date, p_month = parse_date_from_row(r)
        if p_date:
            portfolio_date, month_str = p_date, p_month
            break

    if not portfolio_date:
        portfolio_date, month_str = default_date, default_month

    # Detect header row
    inst_col, isin_col, ind_col, qty_col = None, None, None, None
    header_idx = None
    for r_idx, r in enumerate(rows[:10]):
        for c_idx, cell in enumerate(r):
            c_str = str(cell or "").strip().lower()
            if "name of" in c_str or "instrument" in c_str:
                inst_col = c_idx
            elif "isin" in c_str:
                isin_col = c_idx
            elif "rating" in c_str or "industry" in c_str:
                ind_col = c_idx
            elif "quantity" in c_str or "qty" in c_str:
                qty_col = c_idx
        if inst_col is not None and isin_col is not None and qty_col is not None:
            header_idx = r_idx
            break

    if header_idx is None:
        print(f"  [WARN] Header row not found in: {file_path.name}")
        return []

    extracted = []
    for r in rows[header_idx + 1:]:
        inst_val = r[inst_col] if inst_col < len(r) else None

        if is_stop_instrument(inst_val):
            break

        isin_val = clean_text(r[isin_col]) if isin_col < len(r) and r[isin_col] is not None else ""
        if not (isin_val.startswith("INE") and len(isin_val) == 12):
            continue

        qty_val = clean_quantity(r[qty_col]) if qty_col < len(r) else None
        if qty_val is None or qty_val <= 0:
            continue

        sec_name = clean_text(inst_val)
        ind_val = clean_text(r[ind_col]) if ind_col is not None and ind_col < len(r) and r[ind_col] is not None else ""

        extracted.append({
            "AMC": AMC_NAME,
            "Fund_Name": fund_name,
            "Portfolio_Date": portfolio_date,
            "Month": month_str,
            "Security_Name": sec_name,
            "ISIN": isin_val,
            "Industry_Rating": ind_val,
            "Quantity": qty_val,
        })

    return extracted


def process_all_files():
    files = sorted(glob.glob(str(RAW_FOLDER / "*" / "*" / "*.*")))
    print(f"Found {len(files)} files in {RAW_FOLDER}")

    all_data = []

    for fpath in files:
        file_path = Path(fpath)

        try:
            year_dir = file_path.parent.parent.name
            month_dir = file_path.parent.name
            default_date = f"{year_dir}-{month_dir}-28"
            dt_fallback = datetime.datetime.strptime(f"{year_dir}-{month_dir}", "%Y-%m")
            default_month = dt_fallback.strftime("%b-%Y")
        except Exception:
            default_date = "2026-09-30"
            default_month = "Sep-2026"

        rows = clean_workbook(file_path, default_date, default_month)
        all_data.extend(rows)

    df = pd.DataFrame(all_data, columns=STANDARD_COLUMNS)
    print(f"\nTotal extracted holdings: {len(df):,}")
    print("\nHoldings by Month:")
    print(df.groupby("Month")["Fund_Name"].count())
    print("\nHoldings by Fund:")
    print(df.groupby("Fund_Name")["ISIN"].count())

    df.sort_values(by=["Fund_Name", "Portfolio_Date", "Security_Name"], inplace=True)
    df.to_excel(OUTPUT_FILE, index=False)
    print(f"\n[SUCCESS] Cleaned data saved to: {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size:,} bytes")
    return df


if __name__ == "__main__":
    process_all_files()
