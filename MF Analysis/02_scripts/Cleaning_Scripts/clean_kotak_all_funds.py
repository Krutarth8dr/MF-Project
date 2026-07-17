import re
import pandas as pd
from pathlib import Path

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_FOLDER = PROJECT_ROOT / "01_raw_files" / "KOTAK"

OUTPUT_FOLDER = PROJECT_ROOT / "03_clean_data" / "KOTAK"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "KOTAK_All_Funds_Cleaned.xlsx"

# Kotak's downloader organizes raw files into RAW_FOLDER/<year>/<month>/, so
# (unlike SBI's flat folder) we need a recursive search both for the
# canonical workbook and for the full set of workbooks to process.
CANONICAL_FILENAME_HINTS = ["june", "2026"]  # must all appear (case-insensitive)

# Sheet codes (tabs) to process. Kotak has ~116 scheme tabs covering equity,
# debt, hybrid, and index/ETF funds, but they don't all share the same sheet
# layout -- equity fund tabs have exactly one "Total" row, while debt fund
# tabs have several (one per asset-class sub-section), which the stop-at-
# first-Total logic below is NOT designed to handle correctly yet.
#
# Starting with just A50 (Kotak Nifty Alpha 50 Index Fund) since it's a
# confirmed-clean equity-style sheet. Add more equity-style codes here once
# each one has been checked.
TARGET_SHEETS = [
    "A50",
    "CMP",
    "BSI",
    "CON",
    "ELS",
    "EME",
    "ESG",
    "HLC",
    "K30",
    "KAM",
    "KBA",
    "KBC",
    "KEO",
    "KFE",
    "KIE",
    "KIP",
    "KMI",
    "KMN",
    "KOP",
    "KPF",
    "KQT",
    "KSF",
    "MAF",
    "MID",
    "MUC",
    "NCI",
    "SEF",
    "SPO",
    "SRF",
    "TAL",
    "TCH",
]

AMC_NAME = "Kotak MF"

# Kotak's fund sheets have a merged header ("Name of Instrument" spans
# columns A:C), but the actual security name for each holding row lives in
# column C (position 2), not column A. So instead of matching columns by
# header text (like the SBI script does), we pick columns by their fixed
# position, which is consistent across all Kotak sheets we've checked:
COL_SECURITY_NAME = 2
COL_ISIN = 3
COL_INDUSTRY_RATING = 4
COL_QUANTITY = 6


def find_all_workbooks():
    """Kotak's older raw files (roughly pre-2026) were saved in the legacy
    .xls format, while newer ones are .xlsx -- both exist side by side under
    RAW_FOLDER/<year>/<month>/. Searching only *.xlsx silently skips every
    .xls file, which is why older months were being dropped."""
    return sorted(list(RAW_FOLDER.rglob("*.xlsx")) + list(RAW_FOLDER.rglob("*.xls")))


def excel_engine_for(path: Path) -> str:
    """.xls (legacy binary format) needs the 'xlrd' engine; .xlsx (modern
    zip/XML format) needs 'openpyxl'. Passing the wrong engine raises an
    error, so we pick it based on the file extension."""
    if path.suffix.lower() == ".xls":
        return "xlrd"
    return "openpyxl"


def find_canonical_workbook():
    """Locate the reference workbook to pull official Kotak fund names from
    (via its 'Scheme' index sheet). Searches RAW_FOLDER recursively for a
    filename containing all of CANONICAL_FILENAME_HINTS."""
    candidates = [
        p
        for p in find_all_workbooks()
        if all(hint.lower() in p.name.lower() for hint in CANONICAL_FILENAME_HINTS)
    ]

    if not candidates:
        raise FileNotFoundError(
            "Could not find a canonical Kotak workbook matching "
            f"{CANONICAL_FILENAME_HINTS} under {RAW_FOLDER}. "
            "Set CANONICAL_WORKBOOK manually if your filenames differ."
        )

    # Prefer a "SEBI" portfolio workbook if there's a choice, since that's
    # the version this script was built and verified against.
    sebi_candidates = [p for p in candidates if "sebi" in p.name.lower()]
    chosen = sebi_candidates[0] if sebi_candidates else candidates[0]

    if len(candidates) > 1:
        print(
            f"  Note: multiple canonical-workbook candidates found, using: {chosen.name}"
        )

    return chosen


def extract_portfolio_date(df):
    """
    The portfolio date isn't in a fixed cell like SBI's -- it's embedded in
    the sheet's title string in row 0, e.g.:
      "Portfolio of Kotak Nifty Alpha 50 Index Fund as on 30-Jun-2026"

    Normalized to the 1st of the month (e.g. 30-Jun-2026 -> 1-Jun-2026), the
    same convention followed across all cleaning scripts.
    """
    title = df.iloc[0, 2]

    if pd.isna(title):
        return pd.NaT

    match = re.search(r"as on\s+(.+)$", str(title), flags=re.IGNORECASE)

    if not match:
        return pd.NaT

    parsed = pd.to_datetime(match.group(1).strip(), errors="coerce", dayfirst=True)

    if pd.isna(parsed):
        return parsed

    return parsed.replace(day=1)


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
    Loads the official Kotak fund names from the canonical workbook's
    'Scheme' index sheet, which maps sheet-code abbreviations (e.g. 'A50')
    to full scheme names (e.g. 'Kotak Nifty Alpha 50 Index Fund').
    """

    print("=" * 90)
    print("Loading Canonical Fund Names")
    print("=" * 90)
    print(f"Source: {canonical_workbook}")

    scheme_df = pd.read_excel(
        canonical_workbook,
        sheet_name="Scheme",
        header=None,
        engine=excel_engine_for(canonical_workbook),
    )

    fund_name_mapping = {}

    for sheet in TARGET_SHEETS:

        match = scheme_df[scheme_df[0] == sheet]

        if match.empty:
            print(f"{sheet:<12} -> NOT FOUND in Scheme index")
            continue

        fund_name = str(match.iloc[0, 1]).strip()
        fund_name_mapping[sheet] = fund_name

        print(f"{sheet:<12} -> {fund_name}")

    print()

    return fund_name_mapping


def clean_sheet(df, sheet_name, fund_name):

    portfolio_date = extract_portfolio_date(df)
    header_row = None

    for i in range(len(df)):

        row_values = df.iloc[i].astype(str).str.strip().tolist()

        if "ISIN Code" in row_values:
            header_row = i
            break

    if header_row is None:
        raise ValueError("Header row not found.")

    data = df.iloc[header_row + 1 :].reset_index(drop=True)

    # Drop completely empty rows
    data = data.dropna(how="all")

    # Stop scanning rows once "Total" appears in the Industry column, and
    # keep only the rows above it.
    #
    # NOTE: this assumes exactly one "Total" per sheet, which holds for
    # equity fund sheets (like A50) but NOT for debt fund sheets, which have
    # a separate Total per asset-class sub-section. Don't add debt-fund
    # sheet codes to TARGET_SHEETS until this is extended to handle that.
    industry_col = data[COL_INDUSTRY_RATING].astype(str).str.strip().str.upper()
    stop_mask = industry_col == "TOTAL"

    if stop_mask.any():
        stop_index = stop_mask.idxmax()  # first True, by original (pre-reset) label
        # data was reset_index(drop=True) above, so idxmax gives a positional label too
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

    # Kotak raw files live under RAW_FOLDER/<year>/<month>/, so we search
    # recursively (unlike SBI's flat-folder glob). Older files (pre-2026)
    # were saved as legacy .xls, newer ones as .xlsx -- find_all_workbooks()
    # picks up both.
    workbook_files = find_all_workbooks()

    if not workbook_files:
        raise FileNotFoundError(f"No Kotak workbooks found in:\n{RAW_FOLDER}")

    all_data = []
    existing_df = None
    processed_keys = set()

    print("=" * 90)
    print("Cleaning Kotak Monthly Portfolio Files")
    print("=" * 90)

    fund_name_mapping = load_canonical_fund_names(canonical_workbook)

    if OUTPUT_FILE.exists():
        try:
            existing_df = pd.read_excel(OUTPUT_FILE)
            require_columns = ["Fund_Name", "Portfolio_Date"]
            missing = [col for col in require_columns if col not in existing_df.columns]

            if missing:
                print(
                    "Existing output is missing required columns. Reprocessing all Kotak files."
                )
                existing_df = None
            else:
                processed_keys = get_processed_keys(existing_df)
                print(
                    f"Existing output found: {len(processed_keys)} fund-month "
                    "combinations already processed"
                )

        except Exception as e:
            print("Could not read existing output. Reprocessing all Kotak files.")
            print("Reason:", e)
            existing_df = None
            processed_keys = set()

    for workbook in workbook_files:

        cleaned = process_workbook(workbook, processed_keys, fund_name_mapping)

        if not cleaned.empty:
            all_data.append(cleaned)

    if not all_data:
        if existing_df is not None:
            print("\nNo new Kotak data found. Existing cleaned file preserved.")
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
    print("Kotak Cleaning Complete")
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
