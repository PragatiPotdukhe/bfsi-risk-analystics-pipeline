import pandas as pd
from utils import get_logger, parse_rbi_quarter, parse_fiscal_year

log = get_logger("transform")


# -- Clean RBI NPA data -------------------------------------------------------
def clean_rbi(df_raw):
    df = df_raw.copy()  # never mutate the raw DataFrame

    # 1. Standardise column names to snake_case
    df.columns = (
        df.columns.str.lower().str.strip()
        .str.replace(" ", "_").str.replace("/", "_")
    )

    # 2. Keep only the columns we need (safe-select, skip any missing)
    KEEP = ["bank_group", "quarter", "gross_npa_pct", "net_npa_pct",
            "gross_advances_cr", "gross_npa_amt_cr", "provision_coverage", "slma_pct"]
    df = df[[c for c in KEEP if c in df.columns]]

    # 3. Fix string "-" placeholders as NaN
    for col in ["gross_npa_pct", "net_npa_pct", "slma_pct", "provision_coverage"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 4. Fix comma-formatted numbers e.g. "4,28,318"
    for col in ["gross_advances_cr", "gross_npa_amt_cr"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str).str.replace(",", "", regex=False)
                .pipe(pd.to_numeric, errors="coerce")
            )

    # 5. Parse quarter string to a proper date, e.g. "Q2:2023-24" -> 2023-09-30
    df["quarter_date"] = df["quarter"].apply(parse_rbi_quarter)
    df["quarter_date"] = pd.to_datetime(df["quarter_date"])
    df["year"] = df["quarter_date"].dt.year

    # 6. Bank category bucket (for Power BI slicers)
    public = ["Public Sector Banks", "State Bank of India", "Nationalised Banks"]
    private = ["Private Sector Banks", "Old Private Sector", "New Private Sector"]
    df["bank_category"] = df["bank_group"].apply(
        lambda x: "Public" if x in public else ("Private" if x in private else "Foreign/Other")
    )

    # 7. Forward-fill small gaps within the same bank_group (quarterly continuity)
    df = df.sort_values(["bank_group", "quarter_date"])
    df[["gross_npa_pct", "net_npa_pct"]] = (
        df.groupby("bank_group")[["gross_npa_pct", "net_npa_pct"]].transform(lambda x: x.ffill())
    )

    log.info(f"clean_rbi: {df.shape[0]} rows after cleaning")
    return df


# -- Clean loan data & add BFSI-derived metrics ------------------------------
def clean_loans(df_raw):
    df = df_raw.copy()

    # 1. Standardise column names
    df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")

    # NOTE: the exact column names below (loans_sanctioned, amt_sanctioned_lakh,
    # etc.) are placeholders matching the original project spec. Run
    # `print(df_raw.columns.tolist())` after your first real extract_loans()
    # call and rename to match the actual data.gov.in field names before
    # relying on this function.

    NUM_COLS = ["loans_sanctioned", "amt_sanctioned_lakh", "loans_disbursed",
                "amt_disbursed_lakh", "npa_count", "npa_amount_lakh"]
    NUM_COLS = [c for c in NUM_COLS if c in df.columns]
    df[NUM_COLS] = df[NUM_COLS].apply(pd.to_numeric, errors="coerce")

    # 2. Drop rows missing the key fields we need for every downstream metric
    required = [c for c in ["loans_sanctioned", "amt_sanctioned_lakh"] if c in df.columns]
    df.dropna(subset=required, inplace=True)
    log.info(f"  After null drop: {df.shape[0]} rows")

    # 3. Derived metric: disbursement rate
    df["disbursement_rate"] = (df["loans_disbursed"] / df["loans_sanctioned"]).clip(0, 1)

    # 4. Derived metric: NPA rate
    df["npa_rate"] = (df["npa_count"] / df["loans_disbursed"]).clip(0, 1)
    df["npa_reported"] = df["npa_count"].notna().astype(int)

    # 5. Derived metric: average loan size (lakh)
    df["avg_loan_size_lakh"] = (df["amt_sanctioned_lakh"] / df["loans_sanctioned"]).round(2)

    # 6. Derived metric: average NPA size (lakh)
    df["avg_npa_size_lakh"] = (df["npa_amount_lakh"] / df["npa_count"]).round(2)

    # 7. Risk tier - mirrors EWS-style bucketing on NPA rate
    def risk_tier(npa_rate):
        if pd.isna(npa_rate):
            return "Unknown"
        elif npa_rate < 0.02:
            return "Green (Low Risk)"
        elif npa_rate < 0.05:
            return "Amber (Watch)"
        elif npa_rate < 0.10:
            return "Red (High Risk)"
        else:
            return "Critical (>10%)"
    df["risk_tier"] = df["npa_rate"].apply(risk_tier)

    # 8. Loan size bucket
    def loan_size_bucket(amt):
        if pd.isna(amt):
            return "Unknown"
        elif amt < 10:
            return "Micro (<10L)"
        elif amt < 50:
            return "Small (10-50L)"
        elif amt < 200:
            return "Medium (50-200L)"
        else:
            return "Large (>200L)"
    df["loan_size_bucket"] = df["avg_loan_size_lakh"].apply(loan_size_bucket)

    # 9. Parse fiscal year string ("2022-23") to integer year for joining
    if "year" in df.columns:
        df["year_int"] = df["year"].apply(parse_fiscal_year)

    log.info(f"clean_loans: {df.shape[0]} rows, {df.shape[1]} cols")
    return df


# -- Clean macro data ----------------------------------------------------------
def clean_macro(df_raw):
    df = df_raw.copy()
    df.sort_values("year", inplace=True)
    df.ffill(inplace=True)  # fill latest-year gaps (World Bank data lag)
    df["is_covid_year"] = (df["year"] == 2020).astype(int)
    log.info(f"clean_macro: {df.shape[0]} rows")
    return df


# -- Join all 3 datasets --------------------------------------------------------
def join_all(df_loans, df_rbi, df_macro):
    # Join 1: attach macro indicators to loans, on year
    df = df_loans.merge(
        df_macro, left_on="year_int", right_on="year",
        how="left", suffixes=("", "_macro"),
    )

    # Join 2: attach an industry NPA benchmark, on year.
    # NOTE: the MSME loan dataset has no bank-category field (that only
    # exists in the RBI data), so we benchmark against the overall
    # industry-average NPA% for that year rather than a per-category figure.
    # If you later find a bank/segment field in the real data.gov.in
    # response, you can re-introduce a category-level join like clean_rbi's
    # bank_category.
    rbi_annual = (
        df_rbi.groupby("year")
        .agg(industry_npa_pct=("gross_npa_pct", "mean"))
        .reset_index()
    )
    df = df.merge(
        rbi_annual, left_on="year_int", right_on="year",
        how="left", suffixes=("", "_rbi"),
    )

    # Derived: is this record's NPA rate better than the industry benchmark?
    df["vs_industry"] = df["npa_rate"] - (df["industry_npa_pct"] / 100)
    df["beats_industry"] = (df["vs_industry"] < 0).astype(int)

    log.info(f"join_all: final shape {df.shape}")
    return df
