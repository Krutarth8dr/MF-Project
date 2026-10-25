"""
Cleaning script for Abakkus MF.
Extracts listed equity holdings from sheets:
- ABAFC -> Abakkus Flexi Cap Fund
- ABALM -> Abakkus Large & Mid Cap Fund
- ABASC -> Abakkus Small Cap Fund

Stops cleaning as soon as "Sub Total", "(b)Unlisted", or "Total" are detected
in the "Name of the Instrument" column.
Output:
03_clean_data/ABAKKUS_MF/Abakkus_MF_All_Funds_Cleaned.xlsx
"""

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
RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "ABAKKUS_MF"
OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "ABAKKUS_MF"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_FOLDER / "Abakkus_MF_All_Funds_Cleaned.xlsx"

AMC_NAME = "Abakkus MF"

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

# Fund mapping taken from September sheet
TARGET_SHEETS = {
    "ABAFC": "Abakkus Flexi Cap Fund",
    "ABALM": "Abakkus Large & Mid Cap Fund",
    "ABASC": "Abakkus Small Cap Fund",
}

STOP_MARKERS = [
    "sub total",
    "subtotal",
    "sub-total",
    "sub_total",
    "(b) unlisted",
    "(b)unlisted",
    "b) unlisted",
    "b)unlisted",
    "(b)",
    "unlisted",
    "total",
    "grand total",
]


def clean_text(val):
    if val is None:
        return ""
    text = str(val).strip()
    return re.sub(r"\s+", " ", text)


def is_stop_instrument(name_val):
    if not name_val:
        return False
    lower = clean_text(name_val).lower()
    if lower in [
        "total", "sub total", "subtotal", "sub-total", "sub_total",
        "grand total", "total:", "total (a)", "total(a)", "total (b)", "total(b)", "unlisted"
    ]:
        return True
    if lower.startswith((
        "sub total", "subtotal", "sub-total", "sub_total",
        "total (", "total(", "total -", "total:", "grand total",
        "(b) unlisted", "(b)unlisted", "b) unlisted", "b)unlisted", "(b)", "b)"
    )):
        return True
    if any(t in lower for t in ["debt instruments", "money market", "treps", "net current assets", "total net assets", "derivatives"]):
        return True
    return False


def parse_date_from_row(row_val):
    text = str(row_val or "")
    m = re.search(r"as on\s+([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})", text, re.I)
    if m:
        mon_str = m.group(1)[:3]
        yr = int(m.group(3))
        dt = pd.to_datetime(f"{mon_str} {yr}", format="%b %Y")
        pdate = pd.Timestamp(year=dt.year, month=dt.month, day=1)
        return pdate, pdate.strftime("%b-%Y")
    return None, None


def clean_abakkus_data():
    print("=" * 80)
    print("ABAKKUS MF - CLEANING PIPELINE")
    print(f"Raw Folder:   {RAW_FOLDER}")
    print(f"Output File:  {OUTPUT_FILE}")
    print("=" * 80)

    files = sorted(
        [
            f for f in list(RAW_FOLDER.glob("*/*/*.*"))
            if not f.name.startswith("~$")
        ]
    )

    if not files:
        print(f"ERROR: No monthly files found in {RAW_FOLDER}")
        sys.exit(1)

    print(f"\n[Step 1/3] Found {len(files)} raw files to process.")

    all_records = []

    for file_path in files:
        with open(file_path, "rb") as fp:
            content = fp.read()

        is_openxml = content.startswith(b"PK\x03\x04")
        is_biff8 = content.startswith(b"\xd0\xcf\x11\xe0")

        # Determine year/month fallback from path
        parts = file_path.parts
        fallback_yr = int(parts[-3])
        fallback_mo = int(parts[-2])
        default_pdate = pd.Timestamp(year=fallback_yr, month=fallback_mo, day=1)
        default_month_str = default_pdate.strftime("%b-%Y")

        if is_openxml:
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            sheet_names = wb.sheetnames

            for code, fund_name in TARGET_SHEETS.items():
                if code not in sheet_names:
                    continue
                ws = wb[code]

                # Parse date from header rows (rows 2, 3, 4)
                pdate = None
                month_str = None
                for r_idx in range(1, 6):
                    for c_idx in range(1, 6):
                        v = ws.cell(r_idx, c_idx).value
                        if v and "as on" in str(v).lower():
                            pdate, month_str = parse_date_from_row(v)
                            break
                    if pdate:
                        break

                if not pdate:
                    pdate = default_pdate
                    month_str = default_month_str

                # Detect header columns
                col_inst = None
                col_isin = None
                col_ind = None
                col_qty = None
                header_row_idx = None

                for r in range(1, 10):
                    row_vals = [clean_text(ws.cell(r, c).value).lower() for c in range(1, 15)]
                    for c_idx, val in enumerate(row_vals, 1):
                        if "name of the instrument" in val or "instrument" in val:
                            col_inst = c_idx
                            header_row_idx = r
                        elif val == "isin":
                            col_isin = c_idx
                        elif "industry" in val or "rating" in val:
                            col_ind = c_idx
                        elif "quantity" in val or "qty" in val:
                            col_qty = c_idx

                    if col_inst and col_isin and col_qty:
                        break

                if not (col_inst and col_isin and col_qty):
                    print(f"  [WARN] Header not found for sheet {code} in {file_path.name}")
                    continue

                sheet_records = 0
                for r in range(header_row_idx + 1, ws.max_row + 1):
                    inst_val = clean_text(ws.cell(r, col_inst).value)
                    if is_stop_instrument(inst_val):
                        break

                    isin_val = clean_text(ws.cell(r, col_isin).value).upper()
                    if not (isin_val.startswith("INE") and len(isin_val) == 12):
                        continue

                    ind_val = clean_text(ws.cell(r, col_ind).value) if col_ind else ""

                    qty_val = ws.cell(r, col_qty).value
                    try:
                        if qty_val is None or str(qty_val).strip() == "":
                            continue
                        qty = float(str(qty_val).replace(",", "").strip())
                        if qty <= 0:
                            continue
                    except Exception:
                        continue

                    all_records.append({
                        "AMC": AMC_NAME,
                        "Fund_Name": fund_name,
                        "Portfolio_Date": pdate.strftime("%Y-%m-%d"),
                        "Month": month_str,
                        "Security_Name": inst_val,
                        "ISIN": isin_val,
                        "Industry_Rating": ind_val,
                        "Quantity": qty,
                    })
                    sheet_records += 1

                print(f"  {month_str} | {code} ({fund_name}): {sheet_records} holdings")

        elif is_biff8:
            wb = xlrd.open_workbook(file_path)
            sheet_names = wb.sheet_names()

            for code, fund_name in TARGET_SHEETS.items():
                if code not in sheet_names:
                    continue
                ws = wb.sheet_by_name(code)

                pdate = None
                month_str = None
                for r_idx in range(min(6, ws.nrows)):
                    for c_idx in range(min(6, ws.ncols)):
                        v = ws.cell_value(r_idx, c_idx)
                        if v and "as on" in str(v).lower():
                            pdate, month_str = parse_date_from_row(v)
                            break
                    if pdate:
                        break

                if not pdate:
                    pdate = default_pdate
                    month_str = default_month_str

                col_inst = None
                col_isin = None
                col_ind = None
                col_qty = None
                header_row_idx = None

                for r in range(min(10, ws.nrows)):
                    row_vals = [clean_text(ws.cell_value(r, c)).lower() for c in range(ws.ncols)]
                    for c_idx, val in enumerate(row_vals):
                        if "name of the instrument" in val or "instrument" in val:
                            col_inst = c_idx
                            header_row_idx = r
                        elif val == "isin":
                            col_isin = c_idx
                        elif "industry" in val or "rating" in val:
                            col_ind = c_idx
                        elif "quantity" in val or "qty" in val:
                            col_qty = c_idx

                    if col_inst is not None and col_isin is not None and col_qty is not None:
                        break

                if col_inst is None or col_isin is None or col_qty is None:
                    print(f"  [WARN] Header not found for sheet {code} in {file_path.name}")
                    continue

                sheet_records = 0
                for r in range(header_row_idx + 1, ws.nrows):
                    inst_val = clean_text(ws.cell_value(r, col_inst))
                    if is_stop_instrument(inst_val):
                        break

                    isin_val = clean_text(ws.cell_value(r, col_isin)).upper()
                    if not (isin_val.startswith("INE") and len(isin_val) == 12):
                        continue

                    ind_val = clean_text(ws.cell_value(r, col_ind)) if col_ind is not None else ""

                    qty_val = ws.cell_value(r, col_qty)
                    try:
                        if qty_val is None or str(qty_val).strip() == "":
                            continue
                        qty = float(str(qty_val).replace(",", "").strip())
                        if qty <= 0:
                            continue
                    except Exception:
                        continue

                    all_records.append({
                        "AMC": AMC_NAME,
                        "Fund_Name": fund_name,
                        "Portfolio_Date": pdate.strftime("%Y-%m-%d"),
                        "Month": month_str,
                        "Security_Name": inst_val,
                        "ISIN": isin_val,
                        "Industry_Rating": ind_val,
                        "Quantity": qty,
                    })
                    sheet_records += 1

                print(f"  {month_str} | {code} ({fund_name}): {sheet_records} holdings")
        else:
            print(f"  [ERROR] Unknown file format: {file_path.name}")

    df = pd.DataFrame(all_records)
    print("\n" + "=" * 80)
    print(f"[Step 2/3] Total extracted holdings: {len(df)}")
    print("Holdings by Month & Fund:")
    print(df.groupby(["Month", "Fund_Name"]).size())
    print("=" * 80)

    # Sort deterministically
    df["Month_Sort"] = pd.to_datetime(df["Portfolio_Date"])
    df = df.sort_values(by=["Month_Sort", "Fund_Name", "Security_Name"]).reset_index(drop=True)
    df = df.drop(columns=["Month_Sort"])
    df = df[STANDARD_COLUMNS]

    print(f"\n[Step 3/3] Saving cleaned data to: {OUTPUT_FILE}")
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cleaned_Data")

    print(f"[SUCCESS] {AMC_NAME} data cleaning completed: {len(df)} records saved.\n")
    return df


if __name__ == "__main__":
    clean_abakkus_data()
