import re
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "DSP"

OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "DSP"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "DSP_All_Funds_Cleaned.xlsx"

CANONICAL_FOLDER = RAW_FOLDER / "monthend-portfolios_30_june_2026"

AMC_NAME = "DSP Mutual Fund"
TARGET_SHEETS = [
    "Aggressive Hybrid",
    "Flexi Cap",
    "Large Cap",
    "Large & Mid Cap",
    "TIGER",
    "MIDCAP",
    "TAX",
    "SMALLCAP",
    "NRNEF",
    "Focused",
    "DAAF",
    "ESF",
    "EQUALNIFTY50",
    "ARBITRAGE",
    "HEALTHCARE",
    "NIFTY50INDEX",
    "NIFTYNEXT50INDEX",
    "QUANT",
    "VALUE",
    "Nifty 50 Equal ETF",
    "NIFTY MIDCAP 150 Q50",
    "Nifty Private Bank ETF",
    "Multi Asset",
    "Nifty Smallcap250 Quality 50",
    "Multicap Fund",
    "Business Cycle Fund",
]
STANDARD_COLUMNS = [
    "AMC",
    "Fund_Name",
    "Portfolio_Date",
    "Month",
    "ISIN",
    "Security_Name",
    "Industry_Rating",
    "Quantity",
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

def find_equity_workbook(folder):
    """
    Returns the DSP Equity workbook inside a monthly folder.
    """

    workbooks = sorted(folder.glob("DSP Equity*.xlsx"))

    if not workbooks:

        raise FileNotFoundError(f"No DSP Equity workbook found in:\n{folder}")

    return workbooks[0]

def extract_fund_name(preview):
    """
    Extracts the fund name from cell B1.
    """

    return str(preview.iloc[0, 1]).strip()

def extract_portfolio_date(preview):
    """
    Extracts the portfolio date from cell B2.
    """

    text = str(preview.iloc[1, 1]).strip()

    if "Portfolio as on" not in text:
        raise ValueError(f"Unable to extract portfolio date:\n{text}")

    date_text = text.replace(
        "Portfolio as on",
        "",
    ).strip()

    portfolio_date = pd.to_datetime(
        date_text,
        format="%B %d, %Y",
    )

    portfolio_date = pd.Timestamp(
        year=portfolio_date.year,
        month=portfolio_date.month,
        day=1,
    )

    return portfolio_date

def read_sheet_metadata(excel, sheet_name):
    """
    Reads the metadata from the top of a DSP sheet.
    """

    preview = pd.read_excel(
        excel,
        sheet_name=sheet_name,
        header=None,
        nrows=5,
    )

    fund_name = extract_fund_name(preview)

    portfolio_date = extract_portfolio_date(preview)

    month = portfolio_date.strftime("%b-%Y")

    return fund_name, portfolio_date, month

def load_canonical_fund_names():
    """
    Loads the official DSP fund names from the
    canonical workbook.
    """

    print("=" * 100)
    print("Loading Canonical Fund Names")
    print("=" * 100)

    workbook = find_equity_workbook(
        CANONICAL_FOLDER,
    )

    excel = pd.ExcelFile(workbook)

    fund_name_mapping = {}

    for sheet in TARGET_SHEETS:

        if sheet not in excel.sheet_names:

            print(f"{sheet:<30} -> NOT FOUND")

            continue

        preview = pd.read_excel(
            excel,
            sheet_name=sheet,
            header=None,
            nrows=2,
        )

        fund_name = extract_fund_name(preview)

        fund_name_mapping[sheet] = fund_name

        print(f"{sheet:<30} -> {fund_name}")

    print()

    return fund_name_mapping

def clean_single_sheet(
    excel,
    sheet_name,
    fund_name,
):
    """
    Cleans one DSP fund sheet and returns a
    standardized dataframe.
    """

    # --------------------------------------------------------------------------
    # Read metadata
    # --------------------------------------------------------------------------

    _, portfolio_date, month = read_sheet_metadata(
        excel,
        sheet_name,
    )

    # --------------------------------------------------------------------------
    # Read holdings table
    # --------------------------------------------------------------------------

    df = pd.read_excel(
        excel,
        sheet_name=sheet_name,
        header=3,
    )

    df = df.dropna(
        how="all",
    )

    # --------------------------------------------------------------------------
    # Standardize column names
    # --------------------------------------------------------------------------

    df.columns = [
        str(col).replace("\n", " ").replace("\r", " ").strip() for col in df.columns
    ]

    # --------------------------------------------------------------------------
    # Rename required columns
    # --------------------------------------------------------------------------

    rename_map = {
        "Name of Instrument": "Security_Name",
        "ISIN": "ISIN",
        "Quantity": "Quantity",
        "Rating/Industry": "Industry_Rating",
    }

    df = df.rename(columns=rename_map)

    # --------------------------------------------------------------------------
    # Validate required columns
    # --------------------------------------------------------------------------

    required_columns = [
        "ISIN",
        "Security_Name",
        "Industry_Rating",
        "Quantity",
    ]

    missing = [col for col in required_columns if col not in df.columns]

    if missing:

        raise ValueError(f"Missing columns : {missing}")

    df = df[required_columns]

    # --------------------------------------------------------------------------
    # Stop at Total
    # --------------------------------------------------------------------------

    total_rows = df[
        df["Security_Name"].fillna("").astype(str).str.strip().str.upper().eq("TOTAL")
    ]

    if not total_rows.empty:

        df = df.iloc[: total_rows.index[0]]

    # --------------------------------------------------------------------------
    # Basic cleanup
    # --------------------------------------------------------------------------

    df["ISIN"] = df["ISIN"].fillna("").astype(str).str.strip()

    df["Security_Name"] = df["Security_Name"].fillna("").astype(str).str.strip()

    df["Industry_Rating"] = df["Industry_Rating"].fillna("").astype(str).str.strip()

    df["Quantity"] = pd.to_numeric(
        df["Quantity"],
        errors="coerce",
    )

    # --------------------------------------------------------------------------
    # Keep only valid equity holdings
    # --------------------------------------------------------------------------

    df = df[
        df["ISIN"].apply(
            is_valid_isin,
        )
    ]

    df = df[df["Quantity"].notna()]

    # --------------------------------------------------------------------------
    # Add metadata
    # --------------------------------------------------------------------------

    df.insert(
        0,
        "AMC",
        AMC_NAME,
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

    # --------------------------------------------------------------------------
    # Final output
    # --------------------------------------------------------------------------

    df = df[STANDARD_COLUMNS]

    return df

def process_workbook(
    workbook,
    processed_keys,
    fund_name_mapping,
):
    """
    Processes one monthly DSP workbook.
    """

    print("\n" + "=" * 100)
    print(f"Workbook : {workbook.name}")
    print("=" * 100)

    excel = pd.ExcelFile(workbook)

    cleaned_data = []

    for sheet in TARGET_SHEETS:

        if sheet not in excel.sheet_names:

            print(f"{sheet:<35} | Sheet not found")

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

                print(f"{sheet:<35}" f" | {fund_name:<40}" " | Already processed")

                continue

            cleaned = clean_single_sheet(
                excel=excel,
                sheet_name=sheet,
                fund_name=fund_name,
            )

            cleaned_data.append(cleaned)

            processed_keys.add(
                (
                    fund_name,
                    month_key,
                )
            )

            print(f"{sheet:<35}" f" | {fund_name:<40}" f" | Rows : {len(cleaned)}")

        except Exception as e:

            print(f"{sheet:<35} | ERROR")

            print(e)

    if cleaned_data:

        return pd.concat(
            cleaned_data,
            ignore_index=True,
        )

    return pd.DataFrame()

def get_processed_keys(existing_df):
    """
    Returns a set of (Fund_Name, YYYY-MM) pairs that
    have already been processed.
    """

    existing_df = existing_df.copy()

    existing_df["Portfolio_Date"] = pd.to_datetime(
        existing_df["Portfolio_Date"],
        errors="coerce",
    )

    existing_df["Portfolio_Date"] = existing_df["Portfolio_Date"].apply(
        lambda x: (
            pd.Timestamp(
                year=x.year,
                month=x.month,
                day=1,
            )
            if pd.notna(x)
            else pd.NaT
        )
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

def main():

    print("=" * 100)
    print("Cleaning DSP Monthly Portfolio Files")
    print("=" * 100)

    # --------------------------------------------------------------------------
    # Load canonical fund names
    # --------------------------------------------------------------------------

    fund_name_mapping = load_canonical_fund_names()

    # --------------------------------------------------------------------------
    # Find monthly folders
    # --------------------------------------------------------------------------

    monthly_folders = sorted(
        [folder for folder in RAW_FOLDER.iterdir() if folder.is_dir()]
    )

    if not monthly_folders:

        raise FileNotFoundError(f"No monthly folders found in:\n{RAW_FOLDER}")

    # --------------------------------------------------------------------------
    # Read existing output
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
    # Process monthly workbooks
    # --------------------------------------------------------------------------

    all_data = []

    for folder in monthly_folders:

        workbook = find_equity_workbook(
            folder,
        )

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

        print("\nNo new DSP data found.")

        return

    new_df = pd.concat(
        all_data,
        ignore_index=True,
    )

    # --------------------------------------------------------------------------
    # Combine with existing output
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
    print("DSP Cleaning Complete")
    print("=" * 100)

    print(f"Folders Processed : {len(monthly_folders)}")
    print(f"New Rows Added    : {len(new_df)}")
    print(f"Total Rows        : {len(final_df)}")
    print(f"Funds             : {final_df['Fund_Name'].nunique()}")
    print(f"Output            : {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

