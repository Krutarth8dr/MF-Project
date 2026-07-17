from pathlib import Path
import re
from datetime import datetime
from unicodedata import name

import pandas as pd

# ==============================================================================
# CONFIGURATION
# ==============================================================================

AMC_NAME = "AXIS"

TARGET_SHEETS = [
    "AXIS500",
    "AXISCON",
    "AXISDEF",
    "AXISEAF",
    "AXISEQF",
    "AXISESF",
    "AXISF25",
    "AXISGOF",
    "AXISIMF",
    "AXISMCF",
    "AXISMLC",
    "AXISMLF",
    "AXISSCF",
    "AXISVAL",
]

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
    "Debt Securities",
    "Money Market Instruments",
    "Reverse Repo",
    "TREPS",
    "Net Receivables",
    "GRAND TOTAL",
    "Sub Total",
]

ROOT_FOLDER = Path(__file__).resolve().parents[2]

RAW_FOLDER = ROOT_FOLDER / "01_raw_files" / "AXIS"

OUTPUT_FOLDER = ROOT_FOLDER / "03_clean_data" / "AXIS"

OUTPUT_FOLDER.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FILE = OUTPUT_FOLDER / "AXIS_All_Funds_Cleaned.xlsx"

CANONICAL_WORKBOOK = RAW_FOLDER / "Monthly_Portfolio_31_05_26.xlsx"
# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def print_separator(character="=", width=100):
    print(character * width)


def is_valid_isin(value):
    """
    Returns True only for valid Indian ISINs.
    """

    if pd.isna(value):
        return False

    value = str(value).strip().upper()

    return bool(
        re.fullmatch(
            r"IN[A-Z0-9]{10}",
            value,
        )
    )


# ==============================================================================
# DATE PARSING
# ==============================================================================


def parse_workbook_date(file_path):
    """
    Extracts the portfolio date from all Axis filename formats.

    Normalized to the 1st of the month (e.g. 31_05_26 -> 1-May-2026), the
    same convention followed across all cleaning scripts -- the actual day
    parsed from the filename is discarded and only year/month are kept.
    """

    name = file_path.stem

    # New format
    # Monthly_Portfolio_31_05_26

    match = re.search(
        r"(\d{2})_(\d{2})_(\d{2})$",
        name,
    )

    if match:

        day = int(match.group(1))
        month = int(match.group(2))
        year = 2000 + int(match.group(3))

        return pd.Timestamp(datetime(year, month, 1))  # normalized to 1st of month

    # Old format
    # monthly_20portfolio-31_2005_2025

    match = re.search(
        r"(\d{2})_20(\d{2})_(\d{4})$",
        name,
    )

    if match:

        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))

        return pd.Timestamp(datetime(year, month, 1))  # normalized to 1st of month

    # ------------------------------------------------------------------
    # Old text month format
    # monthly_20portfolio-30_20june_202024_20
    # ------------------------------------------------------------------

    match = re.search(
        r"(\d{2})_20([A-Za-z]+)_20(\d{4})_20$",
        name,
        re.IGNORECASE,
    )

    if match:

        day = int(match.group(1))

        month_name = match.group(2).lower()

        month_lookup = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }

        month = month_lookup[month_name]

        year = int(match.group(3))

        return pd.Timestamp(datetime(year, month, 1))  # normalized to 1st of month

    # ------------------------------------------------------------------
    # monthly_20portfolio_2031-10-2025
    # ------------------------------------------------------------------

    match = re.search(
        r"20(\d{2})-(\d{2})-(\d{4})$",
        name,
    )

    if match:

        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))

        return pd.Timestamp(datetime(year, month, 1))  # normalized to 1st of month

    raise ValueError(f"Unable to parse date from filename:\n{file_path.name}")


# ==============================================================================
# CANONICAL FUND NAME MAPPING
# ==============================================================================


def load_fund_name_mapping():
    """
    Reads the May 2026 workbook and creates

    Sheet Code -> Canonical Fund Name
    """

    print()
    print_separator()
    print("Loading Canonical Fund Names")
    print_separator()

    if not CANONICAL_WORKBOOK.exists():
        raise FileNotFoundError(f"Canonical workbook not found:\n{CANONICAL_WORKBOOK}")

    print(f"Workbook : {CANONICAL_WORKBOOK.name}")
    print()

    excel = pd.ExcelFile(
        CANONICAL_WORKBOOK,
    )

    mapping = {}

    for sheet in TARGET_SHEETS:

        if sheet not in excel.sheet_names:
            print(f"{sheet:<10} -> NOT FOUND")
            continue

        preview = pd.read_excel(
            CANONICAL_WORKBOOK,
            sheet_name=sheet,
            header=None,
            nrows=2,
        )

        fund_name = preview.iloc[0, 1] if preview.shape[1] > 1 else sheet

        fund_name = str(fund_name).strip()

        mapping[sheet] = fund_name

        print(f"{sheet:<10} -> {fund_name}")

    print()

    return mapping


# ==============================================================================
# SHEET CLEANING
# ==============================================================================


def clean_sheet(
    workbook,
    sheet_name,
    portfolio_date,
    fund_name,
):
    """
    Cleans a single Axis fund sheet.
    """

    print(f"{sheet_name:<10} Cleaning...")

    # -------------------------------------------------------------------------
    # Detect header row
    # -------------------------------------------------------------------------

    preview = pd.read_excel(
        workbook,
        sheet_name=sheet_name,
        header=None,
        nrows=20,
    )

    header_row = None

    for i in range(len(preview)):

        row = preview.iloc[i].fillna("").astype(str).str.upper().tolist()

        row_text = " | ".join(row)

        if "NAME OF THE INSTRUMENT" in row_text and "ISIN" in row_text:
            header_row = i
            break

    if header_row is None:
        raise ValueError(f"{sheet_name}: Header row not found.")

    # -------------------------------------------------------------------------
    # Read sheet
    # -------------------------------------------------------------------------

    data = pd.read_excel(
        workbook,
        sheet_name=sheet_name,
        header=header_row,
    )

    data = data.dropna(
        how="all",
    ).reset_index(drop=True)

    data.columns = [str(col).strip() for col in data.columns]

    # -------------------------------------------------------------------------
    # Rename columns
    # -------------------------------------------------------------------------

    rename_map = {
        "Name of the Instrument": "Security_Name",
        "ISIN": "ISIN",
        "Industry": "Industry_Rating",
        "Industry / Rating": "Industry_Rating",
        "Quantity": "Quantity",
    }

    data = data.rename(
        columns=rename_map,
    )

    required_columns = [
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Quantity",
    ]

    for column in required_columns:

        if column not in data.columns:
            raise ValueError(f"{sheet_name}: Missing column '{column}'")

    # -------------------------------------------------------------------------
    # Find start of equity section
    # -------------------------------------------------------------------------

    security = data["Security_Name"].fillna("").astype(str).str.strip()

    start_row = None

    for i, value in enumerate(security):

        if value == "(a) Listed / awaiting listing on Stock Exchanges":
            start_row = i + 1
            break

    if start_row is None:
        raise ValueError(f"{sheet_name}: Equity section not found.")

    # -------------------------------------------------------------------------
    # Find end of equity section
    # -------------------------------------------------------------------------

    end_row = len(data)

    for i in range(start_row, len(data)):

        value = security.iloc[i]

        for marker in STOP_MARKERS:

            if marker.upper() in value.upper():

                end_row = i
                break

        if end_row != len(data):
            break

    data = data.iloc[start_row:end_row].copy()

    # -------------------------------------------------------------------------
    # Keep only valid equity rows
    # -------------------------------------------------------------------------

    data = data[data["ISIN"].apply(is_valid_isin)]

    data["Quantity"] = pd.to_numeric(
        data["Quantity"],
        errors="coerce",
    )

    data = data[data["Quantity"].notna()]

    data["Security_Name"] = data["Security_Name"].astype(str).str.strip()

    data["Industry_Rating"] = data["Industry_Rating"].fillna("").astype(str).str.strip()

    # -------------------------------------------------------------------------
    # Add metadata
    # -------------------------------------------------------------------------

    data.insert(
        0,
        "AMC",
        AMC_NAME,
    )

    data.insert(
        1,
        "Fund_Name",
        fund_name,
    )

    data.insert(
        2,
        "Portfolio_Date",
        portfolio_date,
    )

    data.insert(
        3,
        "Month",
        portfolio_date.strftime("%b-%Y"),
    )

    data = data[STANDARD_COLUMNS].copy()

    print(f"          Rows : {len(data)}")

    return data


# ==============================================================================
# MAIN
# ==============================================================================


def main():

    print_separator()
    print("Cleaning Axis Monthly Portfolio Files")
    print_separator()

    fund_name_mapping = load_fund_name_mapping()

    workbook_files = list(RAW_FOLDER.glob("*.xls"))
    workbook_files += list(RAW_FOLDER.glob("*.xlsx"))

    workbook_files = [file for file in workbook_files if not file.name.startswith("~$")]

    if not workbook_files:
        raise FileNotFoundError("No Axis workbooks found.")

    all_data = []

    total_workbooks = 0

    for workbook_path in workbook_files:

        print()
        print_separator("#")
        print(workbook_path.name)
        print_separator("#")

        portfolio_date = parse_workbook_date(workbook_path)

        workbook = pd.ExcelFile(
            workbook_path,
        )

        for sheet in TARGET_SHEETS:

            if sheet not in workbook.sheet_names:
                continue

            fund_name = fund_name_mapping.get(
                sheet,
                sheet,
            )

            try:

                cleaned = clean_sheet(
                    workbook=workbook,
                    sheet_name=sheet,
                    portfolio_date=portfolio_date,
                    fund_name=fund_name,
                )

                all_data.append(cleaned)

            except Exception as error:

                print(f"ERROR : {sheet}")
                print(error)

        total_workbooks += 1

    if not all_data:

        raise RuntimeError("No cleaned data generated.")

    final_df = pd.concat(
        all_data,
        ignore_index=True,
    )

    final_df = final_df.drop_duplicates(
        subset=[
            "Fund_Name",
            "Portfolio_Date",
            "ISIN",
        ]
    )

    final_df = final_df.sort_values(
        [
            "Portfolio_Date",
            "Fund_Name",
            "Security_Name",
        ]
    ).reset_index(drop=True)

    if OUTPUT_FILE.exists():

        try:

            OUTPUT_FILE.unlink()

        except PermissionError:

            print()
            print("Please close:")
            print(OUTPUT_FILE)

            raise

    final_df.to_excel(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print_separator()
    print("Cleaning Complete")
    print_separator()

    print(f"Workbooks Processed : {total_workbooks}")
    print(f"Total Rows          : {len(final_df)}")
    print(f"Output              : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
