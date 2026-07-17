import re
import pandas as pd
from pathlib import Path

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "Aditya Birla"

OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "Aditya Birla"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "ABSL_All_Funds_Cleaned.xlsx"

# Like Kotak, ABSL's older raw files are legacy .xls (and even one .xlsm
# seen in the folder listing), while the current month is .xlsx. Search for
# all of them and pick the right pandas engine per file.
CANONICAL_FILENAME_HINTS = ["june", "2026"]  # must all appear (case-insensitive)

# Sheet codes (tabs) to process. ABSL has 100+ scheme tabs covering equity,
# debt, hybrid, ETF and index funds. Like Kotak, they likely don't all share
# the same layout -- debt-oriented sheets may have multiple "Sub Total" rows
# (one per asset-class sub-section), which the stop-at-first-Sub-Total logic
# below is NOT designed to handle correctly yet.
#
# Starting with just ABSLMCF (Aditya Birla Sun Life Multi-Cap Fund) since
# it's a confirmed-clean equity-style sheet. Add more equity-style codes
# here once each one has been checked.
TARGET_SHEETS = [
    "ABSLMCF",
    "ABSLBCF",
    "ABBSEIIF",
    "ABSLCONF",
    "ABSLESG",
    "ABSLMAAF",
    "ABSLMCF",
    "ABSLQF",
    "ABSLSO",
    "ABSLTNLF",
    "ADVG",
    "BINFRA",
    "BSLBKFS",
    "BSLDAAF",
    "BSLEQTY",
    "BSLFEF",
    "BSLMFG",
    "BSLNMF",
    "BSLPHF",
    "BSLR96",
    "BSLTA1",
    "BTOP100",
    "GENNEXT",
    "MIDCAP",
    "MNC",
    "NINDDEF",
    "PSUEQ",
    "PURE",
]

AMC_NAME = "ABSL"

# ABSL's fund sheets have a consistent (non-merged) layout, unlike Kotak's:
#   col 1 = Name of the Instrument
#   col 2 = ISIN
#   col 3 = Industry^ / Rating
#   col 4 = Quantity
COL_SECURITY_NAME = 1
COL_ISIN = 2
COL_INDUSTRY_RATING = 3
COL_QUANTITY = 4


def find_all_workbooks():
    """Search RAW_FOLDER recursively for every raw ABSL workbook, across all
    the Excel formats ABSL has used (.xlsx, legacy .xls, and macro-enabled
    .xlsm seen for at least one month)."""
    patterns = ("*.xlsx", "*.xls", "*.xlsm")
    files = []
    for pattern in patterns:
        files.extend(RAW_FOLDER.rglob(pattern))
    return sorted(set(files))


def excel_engine_for(path: Path) -> str:
    """.xls (legacy binary format) needs 'xlrd'; .xlsx/.xlsm (zip/XML based)
    need 'openpyxl'. Passing the wrong engine raises an error."""
    if path.suffix.lower() == ".xls":
        return "xlrd"
    return "openpyxl"


def find_canonical_workbook():
    """Locate the reference workbook to pull official ABSL fund names from
    (via its 'Index' sheet). Searches RAW_FOLDER recursively for a filename
    containing all of CANONICAL_FILENAME_HINTS."""
    candidates = [
        p
        for p in find_all_workbooks()
        if all(hint.lower() in p.name.lower() for hint in CANONICAL_FILENAME_HINTS)
    ]

    if not candidates:
        raise FileNotFoundError(
            "Could not find a canonical ABSL workbook matching "
            f"{CANONICAL_FILENAME_HINTS} under {RAW_FOLDER}. "
            "Set CANONICAL_WORKBOOK manually if your filenames differ."
        )

    chosen = candidates[0]

    if len(candidates) > 1:
        print(
            f"  Note: multiple canonical-workbook candidates found, using: {chosen.name}"
        )

    return chosen


def extract_portfolio_date(df):
    """
    The portfolio date is embedded in a title string a few rows down, e.g.:
      "Portfolio Statement as on June 30,2026"
    Note the missing space after the comma in ABSL's format trips up
    pandas' date parser (it silently returns year 0001 instead of erroring),
    so we normalize "DD,YYYY" -> "DD, YYYY" before parsing.

    Normalized to the 1st of the month (e.g. June 30,2026 -> 1-Jun-2026),
    the same convention followed across all cleaning scripts.
    """
    for i in range(min(6, len(df))):
        cell = df.iloc[i, 1]
        if pd.isna(cell):
            continue
        cell_str = str(cell)
        match = re.search(r"as on\s+(.+)$", cell_str, flags=re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            date_str = re.sub(r",(\S)", r", \1", date_str)
            parsed = pd.to_datetime(date_str, errors="coerce")
            if pd.isna(parsed):
                return parsed
            return parsed.replace(day=1)

    return pd.NaT


def get_month_key(portfolio_date):
    portfolio_date = pd.to_datetime(portfolio_date, errors="coerce")

    if pd.isna(portfolio_date):
        return None

    return portfolio_date.to_period("M").to_timestamp()


def get_processed_keys(existing_df):

    existing_df = existing_df.copy()

    existing_df["Portfolio_Date"] = pd.to_datetime(
        existing_df["Portfolio_Date"],
        errors="coerce",
    )

    existing_df["Month_Key"] = existing_df["Portfolio_Date"].apply(get_month_key)

    existing_df = existing_df[
        existing_df["Fund_Name"].notna() & existing_df["Month_Key"].notna()
    ]

    return set(
        zip(
            existing_df["Fund_Name"],
            existing_df["Month_Key"],
        )
    )


def is_valid_isin(isin):
    """
    Keep only Indian equity ISINs.
    """

    if pd.isna(isin):
        return False

    isin = str(isin).strip().upper()

    return isin.startswith("INE")


def load_canonical_fund_names(canonical_workbook):
    """
    Loads the official ABSL fund names from the canonical workbook's
    'Index' sheet, which maps fund codes (e.g. 'ABSLMCF') to full scheme
    names (e.g. 'ADITYA BIRLA SUN LIFE MULTI-CAP FUND').
    """

    print("=" * 90)
    print("Loading Canonical Fund Names")
    print("=" * 90)
    print(f"Source: {canonical_workbook}")

    index_df = pd.read_excel(
        canonical_workbook,
        sheet_name="Index",
        header=None,
        engine=excel_engine_for(canonical_workbook),
    )

    fund_name_mapping = {}

    for sheet in TARGET_SHEETS:

        match = index_df[index_df[1] == sheet]

        if match.empty:
            print(f"{sheet:<12} -> NOT FOUND in Index sheet")
            continue

        fund_name = str(match.iloc[0, 2]).strip()
        fund_name_mapping[sheet] = fund_name

        print(f"{sheet:<12} -> {fund_name}")

    print()

    return fund_name_mapping


def clean_sheet(df, sheet_name, fund_name):

    portfolio_date = extract_portfolio_date(df)
    header_row = None

    for i in range(len(df)):

        row_values = df.iloc[i].astype(str).str.strip().tolist()

        if "Name of the Instrument" in row_values:
            header_row = i
            break

    if header_row is None:
        raise ValueError("Header row not found.")

    data = df.iloc[header_row + 1 :].reset_index(drop=True)

    # Drop completely empty rows
    data = data.dropna(how="all")

    # Stop scanning rows once "Sub Total" appears in the "Name of the
    # Instrument" column, and keep only the rows above it.
    #
    # NOTE: this assumes exactly one relevant "Sub Total" per sheet, which
    # holds for equity fund sheets (like ABSLMCF) but likely NOT for debt
    # fund sheets, which tend to have a separate Sub Total per asset-class
    # sub-section. Don't add debt-fund sheet codes to TARGET_SHEETS until
    # this is extended to handle that (same caveat as the Kotak script).
    name_col = data[COL_SECURITY_NAME].astype(str).str.strip().str.upper()
    stop_mask = name_col == "SUB TOTAL"

    if stop_mask.any():
        stop_index = stop_mask.idxmax()  # first True (data was reset_index above)
        data = data.loc[: stop_index - 1]

    sub = data[[COL_SECURITY_NAME, COL_ISIN, COL_INDUSTRY_RATING, COL_QUANTITY]].copy()
    sub.columns = ["Security_Name", "ISIN", "Industry_Rating", "Quantity"]

    # Keep only valid ISIN rows
    sub = sub[sub["ISIN"].apply(is_valid_isin)]

    # Quantity must be numeric
    sub["Quantity"] = pd.to_numeric(sub["Quantity"], errors="coerce")

    sub = sub[sub["Quantity"].notna()]

    # Clean text
    sub["Security_Name"] = sub["Security_Name"].astype(str).str.strip()

    sub["Industry_Rating"] = sub["Industry_Rating"].fillna("").astype(str).str.strip()

    sub.insert(0, "AMC", AMC_NAME)
    sub.insert(1, "Fund_Name", fund_name)
    sub.insert(2, "Portfolio_Date", portfolio_date)
    sub.insert(
        3, "Month", portfolio_date.strftime("%b-%Y") if pd.notna(portfolio_date) else ""
    )

    final_columns = [
        "AMC",
        "Fund_Name",
        "Portfolio_Date",
        "Month",
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Quantity",
    ]

    return sub[final_columns]


def process_workbook(
    workbook_path,
    processed_keys,
    fund_name_mapping,
):

    print("\n" + "=" * 90)
    print(f"Workbook: {workbook_path.name}")
    print("=" * 90)

    xls = pd.ExcelFile(workbook_path, engine=excel_engine_for(workbook_path))

    cleaned_data = []

    for sheet in TARGET_SHEETS:

        if sheet not in xls.sheet_names:
            print(f"Skipping {sheet} (sheet not found)")
            continue

        if sheet not in fund_name_mapping:
            print(f"Skipping {sheet} (no canonical fund name)")
            continue

        try:

            df = pd.read_excel(
                xls,
                sheet_name=sheet,
                header=None,
            )

            fund_name = fund_name_mapping[sheet]

            portfolio_date = extract_portfolio_date(df)
            month_key = get_month_key(portfolio_date)

            if (fund_name, month_key) in processed_keys:
                print(f"{sheet:<12} | {fund_name:<35} | Already processed")
                continue

            cleaned_df = clean_sheet(
                df,
                sheet,
                fund_name,
            )

            cleaned_data.append(cleaned_df)
            processed_keys.add((fund_name, month_key))

            print(
                f"{sheet:<12}"
                f" | {cleaned_df['Fund_Name'].iloc[0]:<35}"
                f" | Rows: {len(cleaned_df)}"
            )

        except Exception as e:

            print(f"{sheet:<12} | ERROR -> {e}")

    if cleaned_data:
        return pd.concat(cleaned_data, ignore_index=True)

    return pd.DataFrame()


def main():

    canonical_workbook = find_canonical_workbook()

    workbook_files = find_all_workbooks()

    if not workbook_files:
        raise FileNotFoundError(f"No ABSL workbooks found in:\n{RAW_FOLDER}")

    all_data = []
    existing_df = None
    processed_keys = set()

    print("=" * 90)
    print("Cleaning ABSL Monthly Portfolio Files")
    print("=" * 90)

    fund_name_mapping = load_canonical_fund_names(canonical_workbook)

    if OUTPUT_FILE.exists():
        try:
            existing_df = pd.read_excel(OUTPUT_FILE)
            require_columns = ["Fund_Name", "Portfolio_Date"]
            missing = [col for col in require_columns if col not in existing_df.columns]

            if missing:
                print(
                    "Existing output is missing required columns. Reprocessing all ABSL files."
                )
                existing_df = None
            else:
                processed_keys = get_processed_keys(existing_df)
                print(
                    f"Existing output found: {len(processed_keys)} fund-month "
                    "combinations already processed"
                )

        except Exception as e:
            print("Could not read existing output. Reprocessing all ABSL files.")
            print("Reason:", e)
            existing_df = None
            processed_keys = set()

    for workbook in workbook_files:

        cleaned = process_workbook(workbook, processed_keys, fund_name_mapping)

        if not cleaned.empty:
            all_data.append(cleaned)

    if not all_data:
        if existing_df is not None:
            print("\nNo new ABSL data found. Existing cleaned file preserved.")
            print("Output:", OUTPUT_FILE)
            return

        raise ValueError("No cleaned data produced.")

    new_df = pd.concat(all_data, ignore_index=True)

    if existing_df is not None and not existing_df.empty:
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        final_df = new_df

    final_df["Portfolio_Date"] = pd.to_datetime(
        final_df["Portfolio_Date"], errors="coerce"
    )

    final_df = final_df.drop_duplicates()

    final_df = final_df.sort_values(by=["Portfolio_Date", "Fund_Name", "Security_Name"])

    final_df.reset_index(drop=True, inplace=True)

    if OUTPUT_FILE.exists():
        try:
            OUTPUT_FILE.unlink()
        except PermissionError:
            print("\nERROR")
            print("Please close:")
            print(OUTPUT_FILE)
            return

    final_df.to_excel(OUTPUT_FILE, index=False)

    print("\n" + "=" * 90)
    print("ABSL Cleaning Complete")
    print("=" * 90)
    print(f"Workbooks Processed : {len(workbook_files)}")
    print(f"New rows added     : {len(new_df)}")
    print(f"Total rows         : {len(final_df)}")
    print(f"Funds              : {final_df['Fund_Name'].nunique()}")
    print(f"Output             : {OUTPUT_FILE}")


# ==============================================================================
# RUN
# ==============================================================================

if __name__ == "__main__":
    main()
