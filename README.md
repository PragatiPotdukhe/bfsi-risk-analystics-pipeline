# BFSI Risk Analytics Pipeline

End-to-end personal data engineering project: 3 public data sources -> Python ETL (EL) -> dbt Core (T) -> Google BigQuery (star schema) -> Power BI dashboard, orchestrated with Apache Airflow.

**Read this before you run anything:** this code is a reference implementation, not a copy-paste-and-ship kit. Retype and understand each function yourself, verify the actual data.gov.in column names against your real API response if you ever get live access, and adjust the logic to match what you actually get back. That's what makes this defensible in an interview.

## Architecture

```
RBI DBIE API      -> extract_rbi()   -┐
data.gov.in API   -> extract_loans() -┤-> transform/join -> raw tables in BigQuery -┐
World Bank API    -> extract_macro() -┘        (EL, Python)                        │
                                                                                     ▼
                                          dbt Core: staging views -> marts -> tests -> snapshot
                                                          (T, SQL)                   │
                                                                                     ▼
                                                                              Power BI dashboard

Airflow DAG runs daily at 6 AM (0 6 * * *): extract >> transform >> load >> dbt_run >> [dbt_test, dbt_snapshot]
```

## Data note - read before quoting any numbers

Both live sources have hard external blockers that are documented, not hidden:
RBI DBIE's portal has a broken/HSTS-blocked SSL certificate, and the
data.gov.in resource is gated behind email verification with an
unconfirmed resource ID. `USE_SAMPLE_DATA=true` in `.env` runs the full
pipeline against clearly-labelled synthetic data instead (see
`data/raw/SAMPLE_DATA_README.md`). The MSME sample
(`sample_msme_loans_data_full.csv`) uses **real** Indian state and district
names (public administrative reference data) with **synthetic** loan/NPA
figures at a scale that matches what's quoted on the CV: 46,970 records /
671 districts / 28 states / FY2015-16 - FY2024-25. Never present these
figures as real RBI or data.gov.in statistics - in the README, the
dashboard, or in an interview.

## Project structure

```
bfsi-risk-analytics-pipeline/
  etl/
    utils.py       - get_logger(), parse_fiscal_year(), parse_rbi_quarter()
    extract.py     - extract_rbi(), extract_loans(), extract_macro() (+ USE_SAMPLE_DATA fallback)
    transform.py   - clean_rbi(), clean_loans(), clean_macro(), join_all()
    load.py        - get_bq_client() (ADC), load_table() (WRITE_TRUNCATE)
    main.py        - run_pipeline() orchestrator
  dags/
    bfsi_dag.py    - Airflow DAG: extract >> transform >> load >> dbt_run >> [dbt_test, dbt_snapshot]
  dbt/
    dbt_project.yml
    profiles.yml.example  - copy to profiles.yml (gitignored) or ~/.dbt/profiles.yml
    models/staging/       - stg_loan_risk, stg_npa_summary, stg_macro (+ sources.yml)
    models/marts/         - dim_district_current_risk, mart_state_risk_rollup, mart_risk_tier_trend
    snapshots/             - district_risk_tier_snapshot.sql (SCD2 on risk tier changes)
    tests/                 - 2 singular tests (tier-threshold consistency, district-scale guard)
  sql/
    create_tables.sql - star schema DDL + validation query
  data/raw/
    sample_*.csv                    - clearly-labelled synthetic sample data (committed on purpose)
    SAMPLE_DATA_README.md
  .github/workflows/
    dbt_ci.yml      - sqlfluff lint + `dbt parse` on every push (no warehouse creds - see file header)
  requirements.txt
  .env.example     - copy to .env and fill in your own keys (never commit .env)
  .gitignore
```

## Setup

1. `python -m venv venv` then activate it
2. `pip install -r requirements.txt` (installs the Python ETL deps + dbt-core + dbt-bigquery)
3. Copy `.env.example` to `.env`. For a first run, leave `USE_SAMPLE_DATA=true` - you don't need RBI/data.gov.in keys to exercise the full pipeline.
4. GCP auth - **no service account key file.** This project's GCP org has `iam.disableServiceAccountKeyCreation` enforced (and Google recommends ADC anyway):
   ```
   gcloud auth application-default login
   ```
   Then set `GOOGLE_APPLICATION_CREDENTIALS` in `.env` to the resulting `application_default_credentials.json` path.
5. Create the BigQuery dataset `bfsi_warehouse` in your GCP project (`GCP_PROJECT_ID` in `.env`).
6. Run the Python EL step: `cd etl && python main.py`
7. Run the dbt T step:
   ```
   cp dbt/profiles.yml.example dbt/profiles.yml   # then edit project/dataset if needed
   cd dbt
   dbt run
   dbt test
   dbt snapshot
   ```

## Running under Airflow

Airflow 3.x via Docker (confirmed working):

```powershell
docker run -p 8080:8080 `
  -v <path-to-repo>\dags:/opt/airflow/dags `
  -v <path-to-repo>:/opt/airflow/project `
  -v <path-to-your-gcloud-adc-json>:/tmp/adc.json `
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json `
  -e AIRFLOW__CORE__LOAD_EXAMPLES=false `
  apache/airflow:latest standalone
```

After each container restart, reinstall deps (this base image doesn't persist installs across restarts):
```
docker exec -it -u airflow <container_id> python -m pip install wbgapi google-cloud-bigquery db-dtypes pandas pyarrow dbt-core dbt-bigquery
```
Then inside the container (or via one more `docker exec`), copy `dbt/profiles.yml.example` to `dbt/profiles.yml` so the `dbt_run`/`dbt_test`/`dbt_snapshot` DAG tasks (which set `DBT_PROFILES_DIR` to the mounted `dbt/` folder) can find it.

Real fixes hit getting this running, documented in `Pragati_Challenge_QA.md`: Windows volume mount path, `ModuleNotFoundError` on the etl/ import, Airflow 3.x moving `PythonOperator`/`BashOperator` under `airflow.providers.standard.operators.*`, `schedule_interval` -> `schedule`, pip permissions inside the container, a relative-path bug in `extract.py`, and mounting ADC credentials into the container.

## Known gaps fixed along the way

- `join_all()` originally referenced a `bank_type_mapped` column that's never created anywhere - would have thrown a `KeyError`. Benchmarks against the overall industry-average NPA% per year instead, since the MSME loan dataset has no bank-category field.
- `get_bq_client()` originally loaded a service-account key file - switched to `google.auth.default()` (ADC) after the org policy blocked key creation.
- `dags/bfsi_dag.py`'s etl/ import path assumed a flat `/opt/airflow/etl` mount that never matched the actual `docker run` command (`etl/` lives under `/opt/airflow/project/etl`) - fixed with a container-path/local-path fallback.

## CI

`.github/workflows/dbt_ci.yml` runs `sqlfluff` lint and `dbt parse` on every push to `dbt/**`. It does **not** run models or tests against real BigQuery - no service-account key exists to give it (same org policy as above), and a personal ADC login isn't something to hand to GitHub Actions. `dbt run`/`dbt test`/`dbt snapshot` against real data run locally or via the Airflow DAG.

## Next steps

See `Pragati_DE_Project_Build_Checklist.md` for the full phase-by-phase build plan, and `Pragati_Interview_Prep_Project_QA.md` / `Pragati_Challenge_QA.md` for how to talk about this in interviews.
