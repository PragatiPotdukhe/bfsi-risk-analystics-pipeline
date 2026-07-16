"""
Airflow DAG for the BFSI Risk Analytics Pipeline.

Runs extract -> transform -> load -> dbt_run -> dbt_test as separate tasks so
Airflow can retry, log, and monitor each phase independently. DataFrames are
passed between the Python tasks via Parquet files on disk (not XCom - XCom is
meant for small metadata, not full DataFrames of tens of thousands of rows).

dbt sits after load: the Python tasks are EL (extract + load into raw
BigQuery tables), dbt is T (staging views + marts + tests + snapshot on top
of those raw tables). This mirrors the standard ELT split - dbt never touches
the source APIs or the loading step.

Airflow 3.x moved PythonOperator/BashOperator out of airflow.operators.* and
into airflow.providers.standard.operators.* - imports below reflect that
(hit as a real DAG-parse error on first deploy; see
Pragati_Challenge_QA.md).
"""
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.operators.bash import BashOperator

# etl/ lives at /opt/airflow/project/etl inside the container (see the
# `docker run` command in README "Running under Airflow" - only dags/ and
# the project root get mounted, not a flat /opt/airflow/etl). Falling back
# to the relative path below lets this file still resolve correctly if you
# run it outside Docker for local editing/debugging.
_ETL_CANDIDATES = [
    "/opt/airflow/project/etl",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "etl"),
]
for _p in _ETL_CANDIDATES:
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
        break

from extract import extract_rbi, extract_loans, extract_macro       # noqa: E402
from transform import clean_rbi, clean_loans, clean_macro, join_all  # noqa: E402
from load import get_bq_client, load_table                          # noqa: E402

TMP_DIR = "/tmp/bfsi_pipeline"
os.makedirs(TMP_DIR, exist_ok=True)

# Same container-vs-local fallback as _ETL_CANDIDATES above, for the dbt
# project directory the Bash tasks need.
_DBT_PROJECT_DIR = (
    "/opt/airflow/project/dbt"
    if os.path.isdir("/opt/airflow/project/dbt")
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dbt")
)


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
    schedule="0 6 * * *",   # runs every day at 6:00 AM (Airflow 3.x renamed schedule_interval -> schedule)
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["bfsi", "risk-analytics", "portfolio-project"],
) as dag:

    extract_task = PythonOperator(task_id="extract", python_callable=_extract_all)
    transform_task = PythonOperator(task_id="transform", python_callable=_transform_data)
    load_task = PythonOperator(task_id="load", python_callable=_load_to_bigquery)

    # dbt run/test authenticate the same way the Python load step does -
    # via GOOGLE_APPLICATION_CREDENTIALS (ADC), not a service account key.
    # DBT_PROFILES_DIR points at dbt/ itself so profiles.yml (copied there
    # from profiles.yml.example, gitignored) sits next to dbt_project.yml.
    dbt_env = {
        "GOOGLE_APPLICATION_CREDENTIALS": os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
        "DBT_PROFILES_DIR": _DBT_PROJECT_DIR,
        "PATH": os.environ.get("PATH", ""),
    }

    dbt_run_task = BashOperator(
        task_id="dbt_run",
        bash_command=f"dbt run --project-dir {_DBT_PROJECT_DIR}",
        env=dbt_env,
    )

    dbt_test_task = BashOperator(
        task_id="dbt_test",
        bash_command=f"dbt test --project-dir {_DBT_PROJECT_DIR}",
        env=dbt_env,
    )

    dbt_snapshot_task = BashOperator(
        task_id="dbt_snapshot",
        bash_command=f"dbt snapshot --project-dir {_DBT_PROJECT_DIR}",
        env=dbt_env,
    )

    extract_task >> transform_task >> load_task >> dbt_run_task >> [dbt_test_task, dbt_snapshot_task]
