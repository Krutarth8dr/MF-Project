import os
import pandas as pd
from pathlib import Path

# =========================
# SETTINGS
# =========================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = str(PROJECT_ROOT / "03_clean_data" / "ICICI" / "ICICI_All_Funds_Cleaned.xlsx")

OUTPUT_FOLDER = str(PROJECT_ROOT / "04_matrix_output" / "ICICI")
OUTPUT_FILE = os.path.join(OUTPUT_FOLDER, "matrix_icici_funds_quantity.xlsx")

# IMPORTANT: For combined matrix with HDFC, use Quantity
VALUE_COLUMN = "Quantity"


# =========================
# MAIN PROCESS
# =========================

def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    if not os.path.exists(INPUT_FILE):
        print("ERROR: Input cleaned file not found:")
        print(INPUT_FILE)
        return

    df = pd.read_excel(INPUT_FILE)

    required_columns = [
        "AMC",
        "Fund_Name",
        "Security_Name",
        "ISIN",
        "Industry_Rating",
        "Portfolio_Date",
        "Month",
        "Quantity",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        print("ERROR: Missing columns in cleaned file:")
        for col in missing_columns:
            print("-", col)
        return

    df["AMC"] = "ICICI Prudential Mutual Fund"

    df["Portfolio_Date"] = pd.to_datetime(df["Portfolio_Date"], errors="coerce")
    df = df[df["Portfolio_Date"].notna()]

    df["Month"] = df["Portfolio_Date"].dt.strftime("%b-%Y")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0)

    # Create HDFC-style matrix:
    # Rows = AMC + Security + Month
    # Columns = Fund names
    # Values = Quantity
    matrix_df = df.pivot_table(
        index=[
            "AMC",
            "Security_Name",
            "ISIN",
            "Portfolio_Date",
            "Month",
            "Industry_Rating",
        ],
        columns="Fund_Name",
        values=VALUE_COLUMN,
        aggfunc="sum",
        fill_value=0
    ).reset_index()

    matrix_df = matrix_df.sort_values(
        by=["Portfolio_Date", "Security_Name"],
        ascending=[True, True]
    )

    base_columns = [
        "AMC",
        "Security_Name",
        "ISIN",
        "Portfolio_Date",
        "Month",
        "Industry_Rating",
    ]

    fund_columns = [
        col for col in matrix_df.columns
        if col not in base_columns
    ]

    matrix_df["Total ICICI Qty"] = matrix_df[fund_columns].sum(axis=1)

    matrix_df = matrix_df[
        base_columns + fund_columns + ["Total ICICI Qty"]
    ]

    if os.path.exists(OUTPUT_FILE):
        try:
            os.remove(OUTPUT_FILE)
        except PermissionError:
            print("ERROR: Output file is open in Excel.")
            print("Please close this file and run again:")
            print(OUTPUT_FILE)
            return

    matrix_df.to_excel(OUTPUT_FILE, index=False)

    print("=" * 90)
    print("ICICI quantity matrix created successfully")
    print("=" * 90)
    print("Output:", OUTPUT_FILE)
    print("Rows:", len(matrix_df))
    print("Funds:", len(fund_columns))
    print("Fund columns:")
    for col in fund_columns:
        print("-", col)


if __name__ == "__main__":
    main()