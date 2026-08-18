from pathlib import Path
import re
from datetime import datetime

import pandas as pd

# ==============================================================================
# CONFIGURATION
# ==============================================================================

AMC_NAME = "AXIS"

TARGET_SHEETS = [
    "AXISCON",
    "AXISBCF",
    "AXISDEF",
    "AXISEHF",
    "AXISEQF",
    "AXISESF",
    "AXISESG",
    "AXISF25",
    "AXISGOF",
    "AXISIMF",
    "AXISMCF",
    "AXISMIF",
    "AXISMLC",
    "AXISMLF",
    "AXISTAF",
    "AXISSSF",
    "AXISSCF",
    "AXISVAL",
]

TARGET_SHEETS = list(dict.fromkeys(TARGET_SHEETS))

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

# Keep the ORIGINAL AXIS section boundaries.
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

# June 2026 remains the canonical source for Fund_Name.
CANONICAL_WORKBOOK = RAW_FOLDER / "Monthly_Portfolio_31_05_26.xlsx"


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def print_separator(character="=", width=100):
    print(character * width)


def normalize_text(value):
    if pd.isna(value):
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).replace("\n", " ").strip(),
    ).lower()


def is_valid_isin(value):
    """
    Valid Indian ISIN:
        IN + 10 alphanumeric characters
    """

    if pd.isna(value):
        return False

    value = str(value).strip().upper()

    return bool(
        re.fullmatch(
            r"INE[A-Z0-9]{9}",
            value,
        )
    )


# ==============================================================================
# DATE PARSING
# ==============================================================================


def parse_date_from_filename(file_path):
    """
    Try all filename formats previously supported by the AXIS cleaner.
    Returns None if no supported filename date exists.
    """

    name = file_path.stem

    # ------------------------------------------------------------------
    # New format:
    # Monthly_Portfolio_31_05_26
    # ------------------------------------------------------------------
    match = re.search(
        r"(\d{2})_(\d{2})_(\d{2})$",
        name,
    )

    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = 2000 + int(match.group(3))

        return pd.Timestamp(datetime(year, month, 1))

    # ------------------------------------------------------------------
    # Old format:
    # monthly_20portfolio-31_2005_2025
    # ------------------------------------------------------------------
    match = re.search(
        r"(\d{2})_20(\d{2})_(\d{4})$",
        name,
    )

    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3))

        return pd.Timestamp(datetime(year, month, 1))

    # ------------------------------------------------------------------
    # Old text-month format:
    # monthly_20portfolio-30_20june_202024_20
    # ------------------------------------------------------------------
    match = re.search(
        r"(\d{2})_20([A-Za-z]+)_20(\d{4})_20$",
        name,
        re.IGNORECASE,
    )

    if match:
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

        month_name = match.group(2).lower()

        if month_name in month_lookup:
            month = month_lookup[month_name]
            year = int(match.group(3))

            return pd.Timestamp(datetime(year, month, 1))

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

        return pd.Timestamp(datetime(year, month, 1))

    return None


def parse_date_from_workbook(workbook, sheet_names):
    """
    Fallback date parser.

    If the filename has no usable date, inspect the first few rows of
    the workbook for text such as:

        Monthly Portfolio Statement as on April 30, 2024

    or:

        Portfolio Statement as on April 30, 2024
    """

    date_pattern = re.compile(
        r"as\s+on\s+" r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
        re.IGNORECASE,
    )

    # Prefer the Index first, then the target sheets.
    preferred_sheets = []

    if "Index" in sheet_names:
        preferred_sheets.append("Index")

    preferred_sheets.extend([sheet for sheet in TARGET_SHEETS if sheet in sheet_names])

    for sheet in preferred_sheets:

        try:
            preview = pd.read_excel(
                workbook,
                sheet_name=sheet,
                header=None,
                nrows=15,
            )
        except Exception:
            continue

        for row in preview.itertuples(index=False):

            for cell in row:

                if pd.isna(cell):
                    continue

                text = str(cell).strip()

                match = date_pattern.search(text)

                if not match:
                    continue

                date_text = match.group(1)

                date_text = re.sub(
                    r",(\S)",
                    r", \1",
                    date_text,
                )

                parsed = pd.to_datetime(
                    date_text,
                    errors="coerce",
                )

                if pd.notna(parsed):
                    return parsed.replace(day=1)

    return None


def get_portfolio_date(workbook_path, workbook):
    """
    Filename is preferred because that was the original AXIS method.

    If the filename is a renamed/uploaded UUID (or otherwise contains no
    supported date), fall back to the date printed inside the workbook.
    """

    date_from_filename = parse_date_from_filename(workbook_path)

    if date_from_filename is not None:
        return date_from_filename

    date_from_workbook = parse_date_from_workbook(
        workbook,
        workbook.sheet_names,
    )

    if date_from_workbook is not None:
        return date_from_workbook

    raise ValueError(
        f"Unable to determine portfolio date from filename or workbook: "
        f"{workbook_path.name}"
    )


# ==============================================================================
# CANONICAL FUND NAME MAPPING
# ==============================================================================


def load_fund_name_mapping():
    """
    Reads the canonical May/June 2026 AXIS workbook and creates:

        Sheet Code -> Canonical Fund Name

    The original AXIS logic is preserved: the first row of each fund sheet
    contains the fund name in column B.
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
# SHEET HEADER DETECTION
# ==============================================================================


def find_header_row_and_columns(workbook, sheet_name):
    """
    Detect the AXIS holdings header dynamically.

    This preserves the original expected fields but does not assume that
    the header is at a fixed row.

    Supported security-name variants include:
        Name of the Instrument
        Name of the Instrument / Issuer

    Supported industry variants include:
        Industry
        Industry / Rating
        Industry / Rating (or similar normalized forms)
    """

    preview = pd.read_excel(
        workbook,
        sheet_name=sheet_name,
        header=None,
        nrows=30,
    )

    for row_idx in range(len(preview)):

        row = preview.iloc[row_idx].tolist()

        normalized = [normalize_text(value) for value in row]

        security_col = None
        isin_col = None
        industry_col = None
        quantity_col = None

        # Security name.
        for col_idx, value in enumerate(normalized):

            if value.startswith("name of the instrument"):
                security_col = col_idx
                break

        # ISIN.
        for col_idx, value in enumerate(normalized):

            if value == "isin":
                isin_col = col_idx
                break

        # Industry / Rating.
        for col_idx, value in enumerate(normalized):

            if (
                value == "industry"
                or value.startswith("industry / rating")
                or value.startswith("industry^")
                or value.startswith("industry /")
            ):
                industry_col = col_idx
                break

        # Quantity.
        for col_idx, value in enumerate(normalized):

            if value == "quantity":
                quantity_col = col_idx
                break

        if (
            security_col is not None
            and isin_col is not None
            and industry_col is not None
            and quantity_col is not None
        ):
            return (
                row_idx,
                {
                    "Security_Name": security_col,
                    "ISIN": isin_col,
                    "Industry_Rating": industry_col,
                    "Quantity": quantity_col,
                },
            )

    raise ValueError(f"{sheet_name}: Header row not found.")


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
    Clean one AXIS fund sheet.

    Original AXIS section logic is preserved:

        Start:
        '(a) Listed / awaiting listing on Stock Exchanges'

        Stop at the first occurrence of one of:
            Debt Securities
            Money Market Instruments
            Reverse Repo
            TREPS
            Net Receivables
            GRAND TOTAL
            Sub Total
    """

    print(f"{sheet_name:<10} Cleaning...")

    # -------------------------------------------------------------------------
    # Detect the actual header row and actual column positions.
    # -------------------------------------------------------------------------

    header_row, column_map = find_header_row_and_columns(
        workbook,
        sheet_name,
    )

    # -------------------------------------------------------------------------
    # Read the sheet using the detected header.
    # -------------------------------------------------------------------------

    data = pd.read_excel(
        workbook,
        sheet_name=sheet_name,
        header=header_row,
    )

    data = data.dropna(how="all").reset_index(drop=True)

    # -------------------------------------------------------------------------
    # Rename detected columns by position.
    #
    # This is more robust than relying on pandas' exact header text.
    # -------------------------------------------------------------------------

    security_col = data.columns[column_map["Security_Name"]]

    isin_col = data.columns[column_map["ISIN"]]

    industry_col = data.columns[column_map["Industry_Rating"]]

    quantity_col = data.columns[column_map["Quantity"]]

    data = data.rename(
        columns={
            security_col: "Security_Name",
            isin_col: "ISIN",
            industry_col: "Industry_Rating",
            quantity_col: "Quantity",
        }
    )

    # -------------------------------------------------------------------------
    # Find start of equity section.
    # -------------------------------------------------------------------------

    security = data["Security_Name"].fillna("").astype(str).str.strip()

    start_row = None

    for i, value in enumerate(security):

        normalized_value = normalize_text(value)

        if normalized_value == "(a) listed / awaiting listing on stock exchanges":
            start_row = i + 1
            break

    if start_row is None:
        raise ValueError(f"{sheet_name}: Equity section not found.")

    # -------------------------------------------------------------------------
    # Find end of equity section.
    #
    # IMPORTANT: preserve the original AXIS stop-marker methodology.
    # -------------------------------------------------------------------------

    end_row = len(data)

    for i in range(
        start_row,
        len(data),
    ):

        value = security.iloc[i]

        if not value:
            continue

        value_upper = value.upper()

        for marker in STOP_MARKERS:

            if marker.upper() in value_upper:

                end_row = i
                break

        if end_row != len(data):
            break

    data = data.iloc[start_row:end_row].copy()

    # -------------------------------------------------------------------------
    # Keep only valid equity holdings.
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
    # Add metadata.
    #
    # Fund_Name comes from the canonical workbook.
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

    # --------------------------------------------------------------------------
    # Canonical Fund Names
    # --------------------------------------------------------------------------

    fund_name_mapping = load_fund_name_mapping()

    # --------------------------------------------------------------------------
    # Monthly workbooks
    # --------------------------------------------------------------------------

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

        try:

            workbook = pd.ExcelFile(
                workbook_path,
            )

            # Filename first; workbook text as fallback.
            portfolio_date = get_portfolio_date(
                workbook_path,
                workbook,
            )

            print(f"Portfolio Date : " f"{portfolio_date.strftime('%b-%Y')}")

        except Exception as error:

            print(f"ERROR opening/date detection: {error}")
            continue

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

                if not cleaned.empty:
                    all_data.append(cleaned)

            except Exception as error:

                print(f"ERROR : {sheet}")
                print(error)

        total_workbooks += 1

    if not all_data:

        raise RuntimeError("No cleaned data generated.")

    # --------------------------------------------------------------------------
    # Combine.
    # --------------------------------------------------------------------------

    final_df = pd.concat(
        all_data,
        ignore_index=True,
    )

    # Keep the original Axis de-duplication concept, but avoid collapsing
    # distinct securities that happen to share a Fund/Date/ISIN unexpectedly.
    final_df = final_df.drop_duplicates()

    final_df = final_df.sort_values(
        [
            "Portfolio_Date",
            "Fund_Name",
            "Security_Name",
        ]
    ).reset_index(drop=True)

    # --------------------------------------------------------------------------
    # Write.
    # --------------------------------------------------------------------------

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

    print(f"Funds               : " f"{final_df['Fund_Name'].nunique()}")

    print(f"Output              : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
