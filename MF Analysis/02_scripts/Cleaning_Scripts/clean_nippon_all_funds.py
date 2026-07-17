import os
import re
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "NIPPON"

OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "NIPPON"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "NIPPON_All_Funds_Cleaned.xlsx"

AMC_NAME = "Nippon India Mutual Fund"

CANONICAL_WORKBOOK = RAW_FOLDER / "NIMF-MONTHLY-PORTFOLIO-31-May-26.xls"

TARGET_SHEETS = [
    "GF",  
    "GS",  
    "PH",
    "ME",
    "NE",
    "EO",      
    "SE",  
    "TS",
    "LE",  
    "EA",
    "QP",
    "SC",
    "SF",
    "AF",
    "LC",
    "MG",  
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

VALID_ISIN_PREFIXES = (
    "INE",
)


def read_sheet_metadata(excel, sheet_name):
    """
    Reads the top few rows of a sheet and extracts
    the portfolio date.
    """

    preview = pd.read_excel(
        excel,
        sheet_name=sheet_name,
        header=None,
        nrows=5,
    )

    portfolio_date = extract_portfolio_date(preview)
    portfolio_date = pd.Timestamp(
        year=portfolio_date.year,
        month=portfolio_date.month,
        day=1,
    )


    month = portfolio_date.strftime("%b-%Y")

    return portfolio_date, month


def extract_portfolio_date(preview):
    """
    Extracts the portfolio date from the metadata rows.
    """

    text = str(preview.iloc[1, 1]).strip()

    if "as on" not in text.lower():
        raise ValueError(f"Unable to extract portfolio date:\n{text}")

    date_text = text.split("as on", 1)[1].strip()

    formats = [
        "%B %d,%Y",  # February 28,2025
        "%B %d, %Y",  # February 28, 2025
        "%d-%b-%Y",  # 28-Feb-2025
        "%d-%b-%y",  # 28-Feb-25
    ]

    for fmt in formats:
        try:
            return pd.to_datetime(date_text, format=fmt)
        except ValueError:
            pass

    raise ValueError(f"Unable to parse date: {date_text}")

def load_canonical_fund_names():
    """
    Loads the official Nippon fund names from the canonical workbook.
    """

    print()
    print("=" * 100)
    print("Loading Canonical Fund Names")
    print("=" * 100)

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

            print(f"{sheet:<4} -> NOT FOUND")

            continue

        preview = pd.read_excel(
            excel,
            sheet_name=sheet,
            header=None,
            nrows=2,
        )

        fund_name = str(preview.iloc[0, 1]).strip()

        fund_name = fund_name.split("(")[0].strip()

        mapping[sheet] = fund_name

        print(f"{sheet:<4} -> {mapping[sheet]}")

    print()

    return mapping

def clean_single_sheet(excel, sheet_name,fund_name):
    """
    Cleans one Nippon fund sheet and returns a
    standardized dataframe.
    """

    # --------------------------------------------------------------------------
    # Read metadata
    # --------------------------------------------------------------------------

    portfolio_date, month = read_sheet_metadata(
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

    df = df.dropna(how="all")

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
        "Name of the Instrument": "Security_Name",
        "Industry / Rating": "Industry_Rating",
        "Quantity": "Quantity",
        "ISIN": "ISIN",
    }

    df = df.rename(columns=rename_map)

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
    # Keep only listed equity holdings
    # --------------------------------------------------------------------------\

    instrument_column = "Security_Name"

    subtotal_rows = df[
        df[instrument_column].fillna("").astype(str).str.strip().str.lower() == "subtotal"
    ]

    if not subtotal_rows.empty:

        subtotal_index = subtotal_rows.index[0]

        df = df.loc[: subtotal_index - 1]

        df = df[
            df["ISIN"].str.startswith(
                VALID_ISIN_PREFIXES,
                na=False,
            )
        ]

    df = df[df["Quantity"].notna()]

    # --------------------------------------------------------------------------
    # Add metadata
    # --------------------------------------------------------------------------

    df.insert(0, "AMC", AMC_NAME)
    df.insert(1, "Fund_Name", fund_name)
    df.insert(2, "Portfolio_Date", portfolio_date)
    df.insert(3, "Month", month)

    # --------------------------------------------------------------------------
    # Final output
    # --------------------------------------------------------------------------

    df = df[STANDARD_COLUMNS]

    return df

def main():

    fund_name_mapping = load_canonical_fund_names()

    fund_name_to_code = {
        fund_name: sheet_code for sheet_code, fund_name in fund_name_mapping.items()
    }

    print("=" * 100)
    print("Cleaning Nippon Monthly Portfolio Files")
    print("=" * 100)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # --------------------------------------------------------------------------
    # Load canonical fund names
    # --------------------------------------------------------------------------

    # --------------------------------------------------------------------------
    # Find all monthly workbooks
    # --------------------------------------------------------------------------

    workbook_files = list(RAW_FOLDER.glob("*.xls"))
    workbook_files += list(RAW_FOLDER.glob("*.xlsx"))

    workbook_files = sorted(
        workbook_files,
        key=lambda f: f.name,
    )

    if not workbook_files:
        raise FileNotFoundError("No Nippon monthly workbooks found.")

    # --------------------------------------------------------------------------
    # Read existing cleaned file
    # --------------------------------------------------------------------------

    existing_df = None
    processed_fund_months = set()

    if OUTPUT_FILE.exists():

        try:

            existing_df = pd.read_excel(OUTPUT_FILE)

            existing_df["Portfolio_Date"] = pd.to_datetime(
                existing_df["Portfolio_Date"],
                errors="coerce",
            )

            processed_fund_months = set(
                zip(
                    existing_df["Fund_Name"].map(fund_name_to_code),
                    existing_df["Portfolio_Date"],
                )
            )

            print(
                f"\nExisting output found : "
                f"{len(processed_fund_months)} fund-month combinations"
            )

        except Exception:

            print("Could not read existing output.")

            existing_df = None

    # --------------------------------------------------------------------------
    # Clean new data
    # --------------------------------------------------------------------------

    cleaned_data = []

    for file_path in workbook_files:

        print()
        print("#" * 100)
        print(file_path.name)
        print("#" * 100)

        excel = pd.ExcelFile(
            file_path,

        )

        for sheet_name in TARGET_SHEETS:

            if sheet_name not in excel.sheet_names:

                print(f"{sheet_name:<4} Missing sheet")

                continue

            portfolio_date, _ = read_sheet_metadata(
                excel,
                sheet_name,
            )

            fund_name = fund_name_mapping[sheet_name]

            if (
                sheet_name,
                portfolio_date,
            ) in processed_fund_months:

                print(f"{sheet_name:<4} Already processed")

                continue

            print(f"{sheet_name:<4} Cleaning...")

            try:

                cleaned = clean_single_sheet(
                    excel=excel,
                    sheet_name=sheet_name,
                    fund_name=fund_name,
                )

                cleaned_data.append(cleaned)

                print(f"     Rows : {len(cleaned)}")

            except Exception as e:

                print(f"{sheet_name:<4} ERROR")

                print(e)

    # --------------------------------------------------------------------------
    # Nothing new?
    # --------------------------------------------------------------------------

    if not cleaned_data:

        print()
        print("=" * 100)
        print("No new Nippon data found.")
        print("=" * 100)

        return

    new_df = pd.concat(
        cleaned_data,
        ignore_index=True,
    )

    # --------------------------------------------------------------------------
    # Combine with existing data
    # --------------------------------------------------------------------------

    if existing_df is not None and len(existing_df) > 0:

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
    # Remove duplicate fund-month-security combinations
    # --------------------------------------------------------------------------

    final_df = final_df.drop_duplicates(
        subset=[
            "Fund_Name",
            "Portfolio_Date",
            "ISIN",
        ],
        keep="last",
    )

    # --------------------------------------------------------------------------
    # Sort output
    # --------------------------------------------------------------------------

    final_df = final_df.sort_values(
        by=[
            "AMC",
            "Fund_Name",
            "Portfolio_Date",
            "Security_Name",
        ],
        ascending=[
            True,
            True,
            True,
            True,
        ],
    )

    # --------------------------------------------------------------------------
    # Save output
    # --------------------------------------------------------------------------

    if OUTPUT_FILE.exists():

        try:
            OUTPUT_FILE.unlink()

        except PermissionError:

            print()
            print("ERROR")
            print("=" * 100)
            print("Close the output Excel file and run again.")
            print(OUTPUT_FILE)

            return

    final_df.to_excel(
        OUTPUT_FILE,
        index=False,
    )

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------

    print()
    print("=" * 100)
    print("Nippon cleaned file updated successfully")
    print("=" * 100)

    print(f"Output      : {OUTPUT_FILE}")
    print(f"New Rows    : {len(new_df)}")
    print(f"Total Rows  : {len(final_df)}")
    print(f"Funds       : {final_df['Fund_Name'].nunique()}")
    print(f"Months      : {final_df['Month'].nunique()}")

if __name__ == "__main__":
    main()
