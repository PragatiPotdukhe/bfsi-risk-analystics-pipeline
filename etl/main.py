from extract import extract_rbi, extract_loans, extract_macro
from transform import clean_rbi, clean_loans, clean_macro, join_all
from load import get_bq_client, load_table
from utils import get_logger

log = get_logger("main")


def run_pipeline():
    log.info("=" * 50)
    log.info("BFSI Risk Analytics Pipeline - START")
    log.info("=" * 50)

    # -- EXTRACT --------------------------------------------------------
    log.info("Phase 1: Extract")
    df_rbi_raw = extract_rbi()
    df_loans_raw = extract_loans()
    df_macro_raw = extract_macro()

    # -- TRANSFORM --------------------------------------------------------
    log.info("Phase 2: Transform")
    df_rbi = clean_rbi(df_rbi_raw)
    df_loans = clean_loans(df_loans_raw)
    df_macro = clean_macro(df_macro_raw)
    df_fact = join_all(df_loans, df_rbi, df_macro)  # master fact table

    # -- LOAD --------------------------------------------------------
    log.info("Phase 3: Load to BigQuery")
    client = get_bq_client()
    load_table(df_fact, "fact_loan_risk", client)
    load_table(df_rbi, "dim_npa_summary", client)
    load_table(df_macro, "dim_macro", client)

    log.info("Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
