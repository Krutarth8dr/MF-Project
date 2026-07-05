import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CLEAN_FOLDER = PROJECT_ROOT / "03_clean_data" / "HDFC"
MATRIX_FOLDER = PROJECT_ROOT / "04_matrix_output" / "HDFC"
MATRIX_FOLDER.mkdir(parents=True, exist_ok=True)

clean_files = list(CLEAN_FOLDER.glob("clean_hdfc_*_all_months.xlsx"))

if not clean_files:
    raise ValueError(f"No clean files found in: {CLEAN_FOLDER}")

all_data = []

for file_path in clean_files:
    print("Reading:", file_path.name)

    df = pd.read_excel(file_path)

    required_columns = [
        "AMC",
        "FundName",
        "Month",
        "MonthDate",
        "ISIN",
        "EquityName",
        "Quantity",
    ]

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        raise ValueError(f"Missing columns in {file_path.name}: {missing}")

    all_data.append(df[required_columns])

final_df = pd.concat(all_data, ignore_index=True)

# Standard AMC name, just to keep clean and consistent
final_df["AMC"] = "HDFC Mutual Fund"

final_df = final_df.sort_values(
    by=["MonthDate", "EquityName", "FundName"],
    ascending=[True, True, True]
)

matrix_df = final_df.pivot_table(
    index=["AMC", "EquityName", "ISIN", "MonthDate", "Month"],
    columns="FundName",
    values="Quantity",
    aggfunc="sum",
    fill_value=0
).reset_index()

matrix_df = matrix_df.sort_values(
    by=["MonthDate", "EquityName"],
    ascending=[True, True]
)

base_columns = [
    "AMC",
    "EquityName",
    "ISIN",
    "MonthDate",
    "Month",
]

fund_columns = [
    col for col in matrix_df.columns
    if col not in base_columns
]

matrix_df["Total HDFC Qty"] = matrix_df[fund_columns].sum(axis=1)

matrix_df = matrix_df[
    base_columns + fund_columns + ["Total HDFC Qty"]
]

output_file = MATRIX_FOLDER / "matrix_hdfc_funds_quantity.xlsx"

if output_file.exists():
    try:
        output_file.unlink()
    except PermissionError:
        print("ERROR: Output file is open in Excel.")
        print("Please close this file and run again:")
        print(output_file)
        raise

matrix_df.to_excel(output_file, index=False)

print("Done.")
print("Clean files used:", len(clean_files))
print("Rows:", len(matrix_df))
print("Saved matrix:", output_file)