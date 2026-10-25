"""
Cleaning script for Canara MF (Canara Robeco Mutual Fund).
Extracts listed equity holdings from individual scheme monthly files for 14 target funds:
- BA: Canara Robeco Balanced Advantage Fund
- BF: Canara Robeco Banking and Financial Services Fund
- CF: Canara Robeco Consumption Fund
- DV: Canara Robeco Flexi Cap Fund
- EQ: Canara Robeco Large and Mid Cap Fund
- ET: Canara Robeco ELSS Tax Saver Fund
- IN: Canara Robeco Infrastructure Fund
- LC: Canara Robeco Large Cap Fund
- MA: Canara Robeco Multi Asset Allocation Fund
- MD: Canara Robeco Mid Cap Fund
- MF: Canara Robeco Multi Cap Fund
- MN: Canara Robeco Manufacturing Fund
- SC: Canara Robeco Small Cap Fund
- VF: Canara Robeco Value Fund

Stops cleaning as soon as "Sub Total", "(b)Unlisted", or "Total" are detected
in the "Name of the Instrument" column.
Output:
03_clean_data/Canara_MF/Canara_MF_All_Funds_Cleaned.xlsx
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
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "Canara_MF"
OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "Canara_MF"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_FOLDER / "Canara_MF_All_Funds_Cleaned.xlsx"

AMC_NAME = "Canara MF"

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
    "BA": "Canara Robeco Balanced Advantage Fund",
    "BF": "Canara Robeco Banking and Financial Services Fund",
    "CF": "Canara Robeco Consumption Fund",
    "DV": "Canara Robeco Flexi Cap Fund",
    "EQ": "Canara Robeco Large and Mid Cap Fund",
    "ET": "Canara Robeco ELSS Tax Saver Fund",
    "IN": "Canara Robeco Infrastructure Fund",
    "LC": "Canara Robeco Large Cap Fund",
    "MA": "Canara Robeco Multi Asset Allocation Fund",
    "MD": "Canara Robeco Mid Cap Fund",
    "MF": "Canara Robeco Multi Cap Fund",
    "MN": "Canara Robeco Manufacturing Fund",
    "SC": "Canara Robeco Small Cap Fund",
    "VF": "Canara Robeco Value Fund",
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


def parse_date_from_text(text):
    if not text:
        return None, None
    m = re.search(r"as on\s+([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})", str(text), re.I)
    if m:
        month_name, day, year = m.group(1), m.group(2), m.group(3)
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                dt = datetime.datetime.strptime(f"{month_name} {day} {year}", fmt)
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
    fname = file_path.name
    # Check prefix e.g. "LC_..." or "ba-17.xlsx"
    m = re.match(r"^([A-Z]{2})_", fname, re.I)
    if m:
        c = m.group(1).upper()
        if c in TARGET_FUNDS:
            return c

    m2 = re.match(r"^([a-zA-Z]{2})[-_]", fname)
    if m2:
        c2 = m2.group(1).upper()
        if c2 in TARGET_FUNDS:
            return c2

    return None


def clean_openpyxl_workbook(file_path, default_date, default_month):
    code = get_fund_code_from_file(file_path)

    with open(file_path, "rb") as fp:
        wb = openpyxl.load_workbook(io.BytesIO(fp.read()), data_only=True, read_only=True)

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return []

    # If code not determined from filename, check sheet title or row 0
    if not code:
        ws_title = ws.title.strip().upper()
        if ws_title in TARGET_FUNDS:
            code = ws_title
        else:
            row0_text = clean_text(" ".join(str(x or "") for x in rows[0]))
            for c, f_title in TARGET_FUNDS.items():
                if f_title.lower() in row0_text.lower():
                    code = c
                    break

    if not code or code not in TARGET_FUNDS:
        print(f"  [WARN] Unknown fund code for file: {file_path.name}")
        return []

    fund_name = TARGET_FUNDS[code]

    # Detect date from rows 0 to 5
    portfolio_date, month_str = None, None
    for r in rows[:6]:
        for cell in r:
            if cell and isinstance(cell, str) and "as on" in cell.lower():
                p_date, p_month = parse_date_from_text(cell)
                if p_date:
                    portfolio_date, month_str = p_date, p_month
                    break
        if portfolio_date:
            break

    if not portfolio_date:
        portfolio_date, month_str = default_date, default_month

    # Detect column positions
    inst_col, isin_col, ind_col, qty_col = None, None, None, None
    header_idx = None
    for r_idx, r in enumerate(rows[:10]):
        r_str = [str(x or "").strip().lower() for x in r]
        for c_idx, cell in enumerate(r_str):
            if "name of" in cell or "instrument" in cell:
                inst_col = c_idx
            elif "isin" in cell:
                isin_col = c_idx
            elif "industry" in cell or "rating" in cell:
                ind_col = c_idx
            elif "quantity" in cell or "qty" in cell:
                qty_col = c_idx
        if inst_col is not None and isin_col is not None and qty_col is not None:
            header_idx = r_idx
            break

    if header_idx is None:
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


def clean_xlrd_workbook(file_path, default_date, default_month):
    code = get_fund_code_from_file(file_path)

    wb = xlrd.open_workbook(file_path)
    ws = wb.sheet_by_index(0)

    if ws.nrows == 0:
        return []

    if not code:
        ws_title = ws.name.strip().upper()
        if ws_title in TARGET_FUNDS:
            code = ws_title
        else:
            row0_text = clean_text(" ".join(str(ws.cell_value(0, c) or "") for c in range(ws.ncols)))
            for c, f_title in TARGET_FUNDS.items():
                if f_title.lower() in row0_text.lower():
                    code = c
                    break

    if not code or code not in TARGET_FUNDS:
        return []

    fund_name = TARGET_FUNDS[code]

    portfolio_date, month_str = None, None
    for r in range(min(6, ws.nrows)):
        for c in range(ws.ncols):
            val = str(ws.cell_value(r, c) or "")
            if "as on" in val.lower():
                p_date, p_month = parse_date_from_text(val)
                if p_date:
                    portfolio_date, month_str = p_date, p_month
                    break
        if portfolio_date:
            break

    if not portfolio_date:
        portfolio_date, month_str = default_date, default_month

    inst_col, isin_col, ind_col, qty_col = None, None, None, None
    header_idx = None
    for r in range(min(10, ws.nrows)):
        r_str = [str(ws.cell_value(r, c) or "").strip().lower() for c in range(ws.ncols)]
        for c_idx, cell in enumerate(r_str):
            if "name of" in cell or "instrument" in cell:
                inst_col = c_idx
            elif "isin" in cell:
                isin_col = c_idx
            elif "industry" in cell or "rating" in cell:
                ind_col = c_idx
            elif "quantity" in cell or "qty" in cell:
                qty_col = c_idx
        if inst_col is not None and isin_col is not None and qty_col is not None:
            header_idx = r
            break

    if header_idx is None:
        return []

    extracted = []
    for r in range(header_idx + 1, ws.nrows):
        inst_val = ws.cell_value(r, inst_col) if inst_col < ws.ncols else None

        if is_stop_instrument(inst_val):
            break

        isin_val = clean_text(ws.cell_value(r, isin_col)) if isin_col < ws.ncols else ""
        if not (isin_val.startswith("INE") and len(isin_val) == 12):
            continue

        qty_val = clean_quantity(ws.cell_value(r, qty_col)) if qty_col < ws.ncols else None
        if qty_val is None or qty_val <= 0:
            continue

        sec_name = clean_text(inst_val)
        ind_val = clean_text(ws.cell_value(r, ind_col)) if ind_col is not None and ind_col < ws.ncols else ""

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
        if file_path.name.startswith("test_"):
            continue

        try:
            year_dir = file_path.parent.parent.name
            month_dir = file_path.parent.name
            default_date = f"{year_dir}-{month_dir}-28"
            dt_fallback = datetime.datetime.strptime(f"{year_dir}-{month_dir}", "%Y-%m")
            default_month = dt_fallback.strftime("%b-%Y")
        except Exception:
            default_date = "2026-09-30"
            default_month = "Sep-2026"

        with open(file_path, "rb") as fp:
            sig = fp.read(8)

        is_xlsx = sig.startswith(b"PK\x03\x04")
        is_ole = sig.startswith(b"\xd0\xcf\x11\xe0")

        if is_xlsx:
            rows = clean_openpyxl_workbook(file_path, default_date, default_month)
            all_data.extend(rows)
        elif is_ole:
            rows = clean_xlrd_workbook(file_path, default_date, default_month)
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
