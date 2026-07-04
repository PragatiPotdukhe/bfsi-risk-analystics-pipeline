"""
Airflow DAG for the BFSI Risk Analytics Pipeline.

Runs the extract -> transform -> load steps as separate tasks so Airflow can
retry, log, and monitor each phase independently. DataFrames are passed
between tasks via Parquet files on disk (not XCom - XCom is meant for small
metadata, not full DataFrames of tens of thousands of rows).

If Docker/RAM isn't available on your laptop, this file is still worth
writing and understanding even if you end up running the pipeline via
Windows Task Scheduler instead - just be upfront in interviews about which
one you actually ran.
"""
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "etl"))

from extract import extract_rbi, extract_loans, extract_macro       # noqa: E402
from transform import clean_rbi, clean_loans, clean_macro, join_all  # noqa: E402
from load import get_bq_client, load_table                          # noqa: E402

TMP_DIR = "/tmp/bfsi_pipeline"
os.makedirs(TMP_DIR, exist_ok=True)


def _extract_all():
    extract_rbi().to_parquet(f"{TMP_DIR}/rbi_raw.parquet")
    extract_loans().to_parquet(f"{TMP_DIR}/loans_raw.parquet")
    extract_macro().to_parquet(f"{TMP_DIR}/macro_raw.parquet")


def _transform_data():
    import pandas as pd
    df_rbi = clean_rbi(pd.read_parquet(f"{TMP_DIR}/rbi_raw.parquet"))
    df_loans = clean_loans(pd.read_parquet(f"{TMP_DIR}/loans_raw.parquet"))
    df_macro = clean_macro(pd.read_parquet(f"{TMP_DIR}/macro_raw.parquet"))
    df_fact = join_all(df_loans, df_rbi, df_macro)

    df_fact.to_parquet(f"{TMP_DIR}/fact_loan_risk.parquet")
    df_rbi.to_parquet(f"{TMP_DIR}/dim_npa_summary.parquet")
    df_macro.to_parquet(f"{TMP_DIR}/dim_macro.parquet")


def _load_to_bigquery():
    import pandas as pd
    client = get_bq_client()
    load_table(pd.read_parquet(f"{TMP_DIR}/fact_loan_risk.parquet"), "fact_loan_risk", client)
    load_table(pd.read_parquet(f"{TMP_DIR}/dim_npa_summary.parquet"), "dim_npa_summary", client)
    load_table(pd.read_parquet(f"{TMP_DIR}/dim_macro.parquet"), "dim_macro", client)


with DAG(
    dag_id="bfsi_risk_pipeline",
    schedule_interval="0 6 * * *",   # runs every day at 6:00 AM
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["bfsi", "risk-analytics", "portfolio-project"],
) as dag:

    extract_task = PythonOperator(task_id="extract", python_callable=_extract_all)
    transform_task = PythonOperator(task_id="transform", python_callable=_transform_data)
    load_task = PythonOperator(task_id="load", python_callable=_load_to_bigquery)

    extract_task >> transform_task >> load_task
