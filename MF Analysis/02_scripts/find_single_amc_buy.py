from pathlib import Path

import pandas as pd

# ==============================================================================
# SETTINGS
# ==============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MATRIX_FOLDER = PROJECT_ROOT / "05_matrix" / "MASTER"

LONG_MATRIX_FILE = MATRIX_FOLDER / "matrix_all_amc_funds_quantity_long.xlsx"
SECURITY_MASTER_FILE = MATRIX_FOLDER / "security_master.xlsx"


def load_and_prepare():
    df = pd.read_excel(LONG_MATRIX_FILE)

    df["Portfolio_Date"] = pd.to_datetime(df["Portfolio_Date"], errors="coerce")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0)

    df = df[df["Portfolio_Date"].notna()]

    return df


def get_latest_and_prev_month(df):
    latest_date = df["Portfolio_Date"].max()
    prev_date = (latest_date.to_period("M") - 1).to_timestamp()
    return latest_date, prev_date


def build_amc_isin_change_table(df, latest_date, prev_date):
    """
    Collapse the long matrix down to one row per (AMC, ISIN), with the total
    quantity held by that AMC (summed across all its funds and any
    Security_Name spelling variants) in the previous month and the latest
    month, plus the change between the two.

    An AMC that doesn't appear for a given ISIN/month simply had 0 there --
    the source matrix already drops zero-quantity rows, so "not present"
    and "held zero" are the same thing here.
    """

    window = df[df["Portfolio_Date"].isin([prev_date, latest_date])]

    grouped = window.groupby(["AMC", "ISIN", "Portfolio_Date"], as_index=False)[
        "Quantity"
    ].sum()

    pivot = grouped.pivot_table(
        index=["AMC", "ISIN"],
        columns="Portfolio_Date",
        values="Quantity",
        fill_value=0,
    )

    # Make sure both month columns exist even in edge cases (e.g. an AMC
    # with literally zero holdings across the board in one of the months).
    for d in (prev_date, latest_date):
        if d not in pivot.columns:
            pivot[d] = 0.0

    pivot = pivot.rename(columns={prev_date: "Qty_Prev", latest_date: "Qty_Latest"})
    pivot["Change"] = pivot["Qty_Latest"] - pivot["Qty_Prev"]

    return pivot.reset_index()


def find_single_amc_net_buys(change_table):
    """
    Keep only ISINs where, across every AMC that held it in either month:
      - no AMC's quantity went DOWN (Change < 0 disqualifies the ISIN), and
      - exactly ONE AMC's quantity went UP (Change > 0), all others flat.
    """

    qualifying = []

    for isin, group in change_table.groupby("ISIN"):
        changes = group["Change"]
        has_any_decrease = (changes < 0).any()
        num_increased = (changes > 0).sum()

        if not has_any_decrease and num_increased == 1:
            qualifying.append(isin)

    return sorted(set(qualifying))


def attach_names(isins):
    security_master = pd.read_excel(SECURITY_MASTER_FILE)

    if "Name_1" not in security_master.columns:
        raise ValueError(f"'Name_1' column not found in {SECURITY_MASTER_FILE}")

    name_lookup = security_master.drop_duplicates(subset="ISIN").set_index("ISIN")[
        "Name_1"
    ]

    result = pd.DataFrame({"ISIN": isins})
    result["Security_Name"] = result["ISIN"].map(name_lookup)

    result = result[["ISIN", "Security_Name"]]
    result = result.sort_values("Security_Name", na_position="last").reset_index(
        drop=True
    )

    return result


def main():

    print("=" * 90)
    print("Finding Stocks Net-Bought By Only One AMC")
    print("=" * 90)

    df = load_and_prepare()

    latest_date, prev_date = get_latest_and_prev_month(df)
    latest_label = latest_date.strftime("%b-%Y")
    prev_label = prev_date.strftime("%b-%Y")

    print(f"\nLatest month   : {latest_label}")
    print(f"Previous month : {prev_label}")

    if not (df["Portfolio_Date"] == prev_date).any():
        print(
            f"\nWARNING: no rows found for {prev_label} in the matrix. "
            "Every AMC's previous-month quantity will be treated as 0, "
            "which will make everything look like a 'new buy'. "
            "Double check the matrix actually has data for that month."
        )

    change_table = build_amc_isin_change_table(df, latest_date, prev_date)

    qualifying_isins = find_single_amc_net_buys(change_table)

    print(f"\nQualifying ISINs found: {len(qualifying_isins)}")

    result = attach_names(qualifying_isins)

    missing_names = result["Security_Name"].isna().sum()
    if missing_names:
        print(
            f"WARNING: {missing_names} ISIN(s) had no match in "
            f"{SECURITY_MASTER_FILE.name} (Name_1 will be blank for those)."
        )

    output_file = MATRIX_FOLDER / f"single_amc_net_buys_{latest_label}.csv"
    result.to_csv(output_file, index=False)

    print(f"\nOutput: {output_file}")
    print(f"Rows  : {len(result)}")


if __name__ == "__main__":
    main()
