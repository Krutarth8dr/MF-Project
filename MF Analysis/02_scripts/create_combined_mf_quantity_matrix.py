import pandas as pd
from pathlib import Path

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MATRIX_FILES = {
    "HDFC": PROJECT_ROOT
    / "04_matrix_output"
    / "HDFC"
    / "matrix_hdfc_funds_quantity.xlsx",
    "ICICI": PROJECT_ROOT
    / "04_matrix_output"
    / "ICICI"
    / "matrix_icici_funds_quantity.xlsx",
    "SBI": PROJECT_ROOT / "04_matrix_output" / "SBI" / "matrix_sbi_funds_quantity.xlsx",
}

OUTPUT_FOLDER = PROJECT_ROOT / "05_matrix" / "MASTER"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "matrix_all_amc_funds_quantity.xlsx"


# ==============================================================================
# BASE COLUMNS
# ==============================================================================

FINAL_BASE_COLUMNS = [
    "AMC",
    "Security_Name",
    "ISIN",
    "Portfolio_Date",
    "Month",
    "Industry_Rating",
]

IGNORE_COLUMNS = {
    "Total HDFC Qty",
    "Total ICICI Qty",
    "Total SBI Qty",
    "Total_All_AMC_Qty",
}


# ==============================================================================
# STANDARDIZE MATRIX
# ==============================================================================


def standardize_matrix(df):
    """
    Standardizes all AMC matrices into one common structure.
    """

    rename_map = {
        "EquityName": "Security_Name",
        "MonthDate": "Portfolio_Date",
        "Sector": "Industry_Rating",
        "FundName": "Fund_Name",
    }

    df = df.rename(columns=rename_map)

    if "Industry_Rating" not in df.columns:
        df["Industry_Rating"] = ""

    df["Portfolio_Date"] = pd.to_datetime(df["Portfolio_Date"], errors="coerce")

    df["Month"] = df["Portfolio_Date"].dt.strftime("%b-%Y")

    return df


# ==============================================================================
# FUND COLUMN IDENTIFICATION
# ==============================================================================


def get_fund_columns(df):

    return [
        col
        for col in df.columns
        if col not in FINAL_BASE_COLUMNS and col not in IGNORE_COLUMNS
    ]


# ==============================================================================
# MAIN
# ==============================================================================


def main():

    all_dataframes = []
    all_fund_columns = []

    print("=" * 90)
    print("Creating Combined Mutual Fund Quantity Matrix")
    print("=" * 90)

    for amc_name, matrix_file in MATRIX_FILES.items():

        if not matrix_file.exists():
            raise FileNotFoundError(f"{amc_name} matrix not found:\n{matrix_file}")

        print(f"\nReading {amc_name} matrix...")
        print(matrix_file)

        df = pd.read_excel(matrix_file)

        df = standardize_matrix(df)

        df = df[df["Portfolio_Date"].notna()]

        fund_columns = get_fund_columns(df)

        for col in fund_columns:
            if col not in all_fund_columns:
                all_fund_columns.append(col)

        all_dataframes.append(df)

    # ==========================================================================
    # ALIGN FUND COLUMNS
    # ==========================================================================

    standardized_dataframes = []

    for df in all_dataframes:

        for col in all_fund_columns:

            if col not in df.columns:
                df[col] = 0

        df = df[FINAL_BASE_COLUMNS + all_fund_columns].copy()

        standardized_dataframes.append(df)

    # ==========================================================================
    # COMBINE ALL AMCs
    # ==========================================================================

    combined_df = pd.concat(standardized_dataframes, ignore_index=True)

    # Ensure all fund columns are numeric
    for col in all_fund_columns:

        combined_df[col] = pd.to_numeric(combined_df[col], errors="coerce").fillna(0)

    # Total quantity across all AMCs
    combined_df["Total_All_AMC_Qty"] = combined_df[all_fund_columns].sum(axis=1)

    # ==========================================================================
    # SORT
    # ==========================================================================

    combined_df = combined_df.sort_values(
        by=[
            "Portfolio_Date",
            "AMC",
            "Security_Name",
        ],
        ascending=[
            True,
            True,
            True,
        ],
    )

    final_columns = FINAL_BASE_COLUMNS + all_fund_columns + ["Total_All_AMC_Qty"]

    combined_df = combined_df[final_columns]

    # ==========================================================================
    # SAVE
    # ==========================================================================

    if OUTPUT_FILE.exists():

        try:
            OUTPUT_FILE.unlink()

        except PermissionError:

            print()
            print("ERROR")
            print("Please close the following file:")
            print(OUTPUT_FILE)

            return

    combined_df.to_excel(
        OUTPUT_FILE,
        index=False,
    )

    # ==========================================================================
    # SUMMARY
    # ==========================================================================

    print()
    print("=" * 90)
    print("Combined Mutual Fund Quantity Matrix Created Successfully")
    print("=" * 90)

    print("Output :", OUTPUT_FILE)
    print("Rows   :", len(combined_df))
    print("AMCs   :", len(MATRIX_FILES))
    print("Funds  :", len(all_fund_columns))

    print("\nAMC Files Used:")

    for amc in MATRIX_FILES:
        print("-", amc)


if __name__ == "__main__":
    main()
