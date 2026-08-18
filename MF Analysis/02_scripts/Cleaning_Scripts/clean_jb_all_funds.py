import re

from pathlib import Path

import pandas as pd

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "JIO_BLACKROCK"

OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "JIO_BLACKROCK"

OUTPUT_FOLDER.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FILE = OUTPUT_FOLDER / "JIO_BLACKROCK_All_Funds_Cleaned.xlsx"

CANONICAL_WORKBOOK = (
    RAW_FOLDER / "Jio BlackRock Mutual Fund-Monthly-Portfolio-30-06-2026.xlsx"
)

TARGET_SHEETS = [
    "JBLARGE",
    "JBFLEXI",
    "JBSECRO",
]

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

def read_sheet_metadata(
    excel,
    sheet_name,
):
    """
    Reads fund name, portfolio date and month.
    """

    preview = pd.read_excel(
        excel,
        sheet_name=sheet_name,
        header=None,
        nrows=4,
    )

    fund_name = str(preview.iloc[0, 1]).strip()

    date_text = (
        str(preview.iloc[2, 1])
        .replace(
            "Monthly Portfolio Statement as on",
            "",
        )
        .strip()
    )

    portfolio_date = pd.to_datetime(
        date_text,
    )

    portfolio_date = pd.Timestamp(
        year=portfolio_date.year,
        month=portfolio_date.month,
        day=1,
    )

    month = portfolio_date.strftime("%b-%Y")

    return (
        fund_name,
        portfolio_date,
        month,
    )

def load_canonical_fund_names():
    """
    Reads the canonical fund names from
    the June 2026 workbook.
    """

    print("=" * 100)
    print("Loading Canonical Fund Names")
    print("=" * 100)

    print(f"Workbook : {CANONICAL_WORKBOOK.name}\n")

    excel = pd.ExcelFile(
        CANONICAL_WORKBOOK,
    )

    mapping = {}

    for sheet in TARGET_SHEETS:

        fund_name, _, _ = read_sheet_metadata(
            excel,
            sheet,
        )

        mapping[sheet] = fund_name

        print(f"{sheet:<12} -> {fund_name}")

    return mapping

def clean_single_sheet(
    excel,
    sheet_name,
    fund_name,
):
    """
    Cleans one Jio BlackRock fund sheet.
    """

    print(f"{sheet_name:<12} Cleaning...")

    _, portfolio_date, month = read_sheet_metadata(
        excel,
        sheet_name,
    )

    df = pd.read_excel(
        excel,
        sheet_name=sheet_name,
        header=3,
    )

    # --------------------------------------------------------------------------
    # Clean column names
    # --------------------------------------------------------------------------

    df.columns = [
        str(col).replace("\n", " ").replace("\r", " ").strip() for col in df.columns
    ]

    # --------------------------------------------------------------------------
    # Stop at "Sub Total"
    # --------------------------------------------------------------------------

    stop_rows = df[
        df["Name of the Instrument"].astype(str).str.strip().str.lower() == "sub total"
    ].index

    if len(stop_rows):

        df = df.iloc[: stop_rows[0]]

    # --------------------------------------------------------------------------
    # Keep only valid ISINs
    # --------------------------------------------------------------------------

    df = df[
        df["ISIN"].apply(
            is_valid_isin,
        )
    ].copy()

    # --------------------------------------------------------------------------
    # Rename columns
    # --------------------------------------------------------------------------

    rename_map = {
        "Name of the Instrument": "Security_Name",
        "ISIN": "ISIN",
        "Industry Classification": "Industry_Rating",
        "Industry Classification/Rating": "Industry_Rating",
        "Industry Classification / Rating": "Industry_Rating",
        "Rating / Industry Classification": "Industry_Rating",
        "Quantity": "Quantity",
    }

    df = df.rename(
        columns=rename_map,
    )

    # --------------------------------------------------------------------------
    # Validate required columns
    # --------------------------------------------------------------------------

    required = [
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Quantity",
    ]

    missing = [col for col in required if col not in df.columns]

    if missing:

        raise ValueError(f"Missing columns : {missing}")

    # --------------------------------------------------------------------------
    # Contract columns
    # --------------------------------------------------------------------------

    df = df[required].copy()

    df.insert(
        0,
        "AMC",
        "JIO_BLACKROCK",
    )

    df.insert(
        1,
        "Fund_Name",
        fund_name,
    )

    df.insert(
        2,
        "Portfolio_Date",
        portfolio_date,
    )

    df.insert(
        3,
        "Month",
        month,
    )

    print(f"     Rows : {len(df)}")

    return df

def process_workbook(
    workbook,
    processed_keys,
    fund_name_mapping,
):
    """
    Processes one monthly workbook.
    """

    print("\n" + "=" * 100)
    print(f"Workbook : {workbook.name}")
    print("=" * 100)

    excel = pd.ExcelFile(workbook)

    cleaned_data = []

    for sheet in TARGET_SHEETS:

        if sheet not in excel.sheet_names:

            print(f"{sheet:<12} | Not available")

            continue

        try:

            _, portfolio_date, _ = read_sheet_metadata(
                excel,
                sheet,
            )

            month_key = portfolio_date.strftime("%Y-%m")

            fund_name = fund_name_mapping[sheet]

            if (
                fund_name,
                month_key,
            ) in processed_keys:

                print(f"{sheet:<12}" f" | {fund_name:<45}" " | Already processed")

                continue

            cleaned = clean_single_sheet(
                excel=excel,
                sheet_name=sheet,
                fund_name=fund_name,
            )

            cleaned_data.append(
                cleaned,
            )

            processed_keys.add(
                (
                    fund_name,
                    month_key,
                )
            )

        except Exception as e:

            print(f"{sheet:<12} | ERROR")

            print(e)

    if cleaned_data:

        return pd.concat(
            cleaned_data,
            ignore_index=True,
        )

    return pd.DataFrame()

def get_processed_keys(existing_df):
    """
    Returns processed (Fund_Name, YYYY-MM) pairs.
    """

    existing_df = existing_df.copy()

    existing_df["Portfolio_Date"] = pd.to_datetime(
        existing_df["Portfolio_Date"],
        errors="coerce",
    )

    existing_df["Month_Key"] = existing_df["Portfolio_Date"].dt.strftime("%Y-%m")

    existing_df = existing_df[
        existing_df["Fund_Name"].notna() & existing_df["Month_Key"].notna()
    ]

    return set(
        zip(
            existing_df["Fund_Name"],
            existing_df["Month_Key"],
        )
    )

def get_workbook_date(workbook):
    """
    Extracts the portfolio date from the
    workbook filename.
    """

    match = re.search(
        r"(\d{2}-\d{2}-\d{4})",
        workbook.name,
    )

    if not match:

        return pd.Timestamp.min

    return pd.to_datetime(
        match.group(1),
        format="%d-%m-%Y",
    )

def main():

    print("=" * 100)
    print("Cleaning Jio BlackRock Monthly Portfolio Files")
    print("=" * 100)

    # --------------------------------------------------------------------------
    # Load canonical fund names
    # --------------------------------------------------------------------------

    fund_name_mapping = load_canonical_fund_names()

    # --------------------------------------------------------------------------
    # Find workbooks
    # --------------------------------------------------------------------------

    workbooks = sorted(
        RAW_FOLDER.glob("*.xls*"),
        key=get_workbook_date,
    )

    if not workbooks:

        raise FileNotFoundError(f"No workbooks found in:\n{RAW_FOLDER}")

    # --------------------------------------------------------------------------
    # Existing output
    # --------------------------------------------------------------------------

    existing_df = None

    processed_keys = set()

    if OUTPUT_FILE.exists():

        try:

            existing_df = pd.read_excel(
                OUTPUT_FILE,
            )

            processed_keys = get_processed_keys(
                existing_df,
            )

            print(
                f"\nExisting output found : "
                f"{len(processed_keys)} fund-month combinations"
            )

        except Exception as e:

            print("Could not read existing output.")

            print(e)

            existing_df = None

            processed_keys = set()

    # --------------------------------------------------------------------------
    # Process workbooks
    # --------------------------------------------------------------------------

    all_data = []

    for workbook in workbooks:

        cleaned = process_workbook(
            workbook=workbook,
            processed_keys=processed_keys,
            fund_name_mapping=fund_name_mapping,
        )

        if not cleaned.empty:

            all_data.append(
                cleaned,
            )

    # --------------------------------------------------------------------------
    # Nothing new?
    # --------------------------------------------------------------------------

    if not all_data:

        print("\nNo new Jio BlackRock data found.")

        return

    new_df = pd.concat(
        all_data,
        ignore_index=True,
    )

    # --------------------------------------------------------------------------
    # Merge
    # --------------------------------------------------------------------------

    if existing_df is not None and not existing_df.empty:

        final_df = pd.concat(
            [
                existing_df,
                new_df,
            ],
            ignore_index=True,
        )

    else:

        final_df = new_df

    # --------------------------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------------------------

    final_df["Portfolio_Date"] = pd.to_datetime(
        final_df["Portfolio_Date"],
        errors="coerce",
    )

    final_df = final_df.drop_duplicates(
        subset=[
            "Fund_Name",
            "Portfolio_Date",
            "ISIN",
        ]
    )

    # --------------------------------------------------------------------------
    # Sort
    # --------------------------------------------------------------------------

    final_df = final_df.sort_values(
        by=[
            "Portfolio_Date",
            "Fund_Name",
            "Security_Name",
        ]
    )

    final_df.reset_index(
        drop=True,
        inplace=True,
    )

    # --------------------------------------------------------------------------
    # Save
    # --------------------------------------------------------------------------

    if OUTPUT_FILE.exists():

        try:

            OUTPUT_FILE.unlink()

        except PermissionError:

            print("\nPlease close:")

            print(OUTPUT_FILE)

            return

    final_df.to_excel(
        OUTPUT_FILE,
        index=False,
    )

    print("\n" + "=" * 100)
    print("Jio BlackRock Cleaning Complete")
    print("=" * 100)

    print(f"Workbooks Processed : {len(workbooks)}")
    print(f"New Rows Added      : {len(new_df)}")
    print(f"Total Rows          : {len(final_df)}")
    print(f"Funds               : {final_df['Fund_Name'].nunique()}")
    print(f"Months              : {final_df['Portfolio_Date'].nunique()}")
    print(f"Output              : {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
