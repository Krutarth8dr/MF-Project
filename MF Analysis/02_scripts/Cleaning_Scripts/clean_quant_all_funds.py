from pathlib import Path
import re
from datetime import datetime

import pandas as pd

# ==============================================================================
# CONFIGURATION
# ==============================================================================

AMC_NAME = "QUANT"

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

STOP_MARKERS = [
    "Sub Total",
    "Total",
    "DERIVATIVES",
    "(b) Unlisted",
    "HOLDINGS",
]

ROOT_FOLDER = Path(__file__).resolve().parents[2]
RAW_FOLDER = ROOT_FOLDER / "01_raw_files" / "QUANT"
OUTPUT_FOLDER = ROOT_FOLDER / "03_clean_data" / "QUANT"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_FOLDER / "QUANT_All_Funds_Cleaned.xlsx"

# ==============================================================================
# HELPERS
# ==============================================================================


def print_separator(character="=", width=100):
    print(character * width)


def is_valid_isin(value):
    if pd.isna(value):
        return False
    value = str(value).strip().upper()
    return bool(re.fullmatch(r"INE[A-Z0-9]{9}", value))


def find_fund_name(preview: pd.DataFrame) -> str:
    for row_index in range(min(len(preview), 6)):
        row = preview.iloc[row_index].tolist()
        for cell in row:
            text = str(cell).strip()
            if not text:
                continue
            if "quant" in text.lower() and "quant mutual fund" not in text.lower():
                return text
    if preview.shape[0] > 1 and preview.shape[1] > 2:
        fallback = str(preview.iloc[1, 2]).strip()
        if fallback:
            return fallback
    raise ValueError("Unable to detect fund name from workbook metadata.")


def find_portfolio_date(preview: pd.DataFrame) -> pd.Timestamp:
    for _, row in preview.iterrows():
        for cell in row.astype(str):
            if isinstance(cell, str) and "MONTHLY PORTFOLIO STATEMENT AS ON" in cell.upper():
                date_text = cell.replace("MONTHLY PORTFOLIO STATEMENT AS ON", "").strip()
                try:
                    portfolio_date = pd.to_datetime(date_text, dayfirst=True, errors="raise")
                except Exception:
                    portfolio_date = pd.to_datetime(date_text, errors="coerce")
                if pd.isna(portfolio_date):
                    raise ValueError(f"Could not parse portfolio date from '{cell}'")
                return portfolio_date.normalize()
    raise ValueError("Portfolio date row not found in workbook metadata.")


def detect_header_row(preview: pd.DataFrame) -> int:
    for index in range(min(len(preview), 15)):
        row = preview.iloc[index].tolist()
        normalized = [str(cell).strip().upper() for cell in row if not pd.isna(cell)]
        if "NAME OF THE INSTRUMENT" in normalized and "ISIN" in normalized:
            return index
    raise ValueError("Header row not found.")


def clean_quant_sheet(workbook: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    preview = pd.read_excel(workbook, sheet_name=sheet_name, header=None, nrows=10)
    fund_name = find_fund_name(preview)
    portfolio_date = find_portfolio_date(preview)
    portfolio_date = pd.Timestamp(year=portfolio_date.year, month=portfolio_date.month, day=1)
    month_label = portfolio_date.strftime("%b-%Y")

    header_row = detect_header_row(preview)
    df = pd.read_excel(workbook, sheet_name=sheet_name, header=header_row)
    df = df.dropna(how="all").reset_index(drop=True)
    df.columns = [str(col).strip() for col in df.columns]

    rename_map = {
        "Name of the Instrument": "Security_Name",
        "NAME OF THE INSTRUMENT": "Security_Name",
        "ISIN": "ISIN",
        "Industry": "Industry_Rating",
        "INDUSTRY": "Industry_Rating",
        "Industry / Rating": "Industry_Rating",
        "Industry/Rating": "Industry_Rating",
        "Industry Classification": "Industry_Rating",
        "Rating": "Industry_Rating",
        "Quantity": "Quantity",
        "QUANTITY": "Quantity",
    }
    df = df.rename(columns=rename_map)

    required_columns = ["Security_Name", "ISIN", "Industry_Rating", "Quantity"]
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    security = df["Security_Name"].fillna("").astype(str).str.strip()
    start_row = None
    for idx, value in enumerate(security):
        text = str(value).strip().upper()
        if "(A) LISTED" in text or "LISTED / AWAITING LISTING" in text:
            start_row = idx + 1
            break
    if start_row is None:
        start_row = 0

    end_row = len(df)
    for idx in range(start_row, len(df)):
        text = str(security.iloc[idx]).strip().upper()
        if any(marker.upper() == text or marker.upper() in text for marker in STOP_MARKERS):
            end_row = idx
            break

    df = df.iloc[start_row:end_row].copy()
    df = df[df["ISIN"].apply(is_valid_isin)].copy()
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df = df[df["Quantity"].notna()].copy()
    df["Security_Name"] = df["Security_Name"].astype(str).str.strip()
    df["Industry_Rating"] = df["Industry_Rating"].fillna("").astype(str).str.strip()

    df.insert(0, "AMC", AMC_NAME)
    df.insert(1, "Fund_Name", fund_name)
    df.insert(2, "Portfolio_Date", portfolio_date)
    df.insert(3, "Month", month_label)
    df = df[STANDARD_COLUMNS].copy()

    return df


def main():
    print_separator()
    print("Cleaning Quant Monthly Portfolio Files")
    print_separator()

    if not RAW_FOLDER.exists():
        raise FileNotFoundError(f"Quant raw folder not found: {RAW_FOLDER}")

    workbooks = sorted(RAW_FOLDER.rglob("*.xls*"))
    workbooks = [path for path in workbooks if not path.name.startswith("~$")]
    if not workbooks:
        raise FileNotFoundError(f"No Quant workbooks found in: {RAW_FOLDER}")

    all_data = []
    total_workbooks = 0

    for workbook_path in workbooks:
        print_separator("#")
        print(workbook_path.name)
        print_separator("#")
        workbook = pd.ExcelFile(workbook_path)
        for sheet_name in workbook.sheet_names:
            try:
                cleaned = clean_quant_sheet(workbook, sheet_name)
                if not cleaned.empty:
                    all_data.append(cleaned)
            except Exception as error:
                print(f"ERROR processing {workbook_path.name} / {sheet_name}: {error}")
        total_workbooks += 1

    if not all_data:
        raise RuntimeError("No cleaned data generated.")

    final_df = pd.concat(all_data, ignore_index=True)
    final_df["Portfolio_Date"] = pd.to_datetime(final_df["Portfolio_Date"], errors="coerce")
    final_df = final_df.drop_duplicates(subset=["Fund_Name", "Portfolio_Date", "ISIN"])
    final_df = final_df.sort_values(["Portfolio_Date", "Fund_Name", "Security_Name"]).reset_index(drop=True)

    if OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()
    final_df.to_excel(OUTPUT_FILE, index=False)

    print_separator()
    print("Quant Cleaning Complete")
    print_separator()
    print(f"Workbooks Processed : {total_workbooks}")
    print(f"Total Rows          : {len(final_df)}")
    print(f"Output              : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
