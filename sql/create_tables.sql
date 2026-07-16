-- BFSI Risk Analytics Pipeline - Star Schema DDL
-- Dataset: bfsi_warehouse (create this dataset in the BigQuery console first)
--
-- These CREATE TABLE statements are optional if you rely on load.py's
-- autodetect=True (BigQuery will infer schema and create tables on first
-- load). Run these manually first if you want explicit control over types
-- and partitioning rather than letting autodetect decide.

-- Fact table: one row per loan record, partitioned by year for query pruning
CREATE TABLE IF NOT EXISTS `bfsi_warehouse.fact_loan_risk` (
  year_int              INT64,
  loans_sanctioned      FLOAT64,
  amt_sanctioned_lakh    FLOAT64,
  loans_disbursed       FLOAT64,
  amt_disbursed_lakh     FLOAT64,
  npa_count             FLOAT64,
  npa_amount_lakh        FLOAT64,
  disbursement_rate     FLOAT64,
  npa_rate              FLOAT64,
  npa_reported          INT64,
  avg_loan_size_lakh     FLOAT64,
  avg_npa_size_lakh      FLOAT64,
  risk_tier             STRING,
  loan_size_bucket      STRING,
  gdp_growth_pct        FLOAT64,
  inflation_cpi_pct     FLOAT64,
  unemployment_pct      FLOAT64,
  real_interest_rate_pct FLOAT64,
  industry_npa_pct      FLOAT64,
  vs_industry           FLOAT64,
  beats_industry        INT64
)
PARTITION BY RANGE_BUCKET(year_int, GENERATE_ARRAY(2015, 2026, 1));

-- Dimension table: quarterly RBI NPA benchmarks by bank category
CREATE TABLE IF NOT EXISTS `bfsi_warehouse.dim_npa_summary` (
  bank_group          STRING,
  bank_category       STRING,
  quarter             STRING,
  quarter_date        DATE,
  year                INT64,
  gross_npa_pct       FLOAT64,
  net_npa_pct         FLOAT64,
  gross_advances_cr   FLOAT64,
  gross_npa_amt_cr    FLOAT64,
  provision_coverage  FLOAT64,
  slma_pct            FLOAT64
);

-- Dimension table: annual India macro indicators
CREATE TABLE IF NOT EXISTS `bfsi_warehouse.dim_macro` (
  year                    INT64,
  gdp_growth_pct          FLOAT64,
  inflation_cpi_pct       FLOAT64,
  unemployment_pct        FLOAT64,
  real_interest_rate_pct  FLOAT64,
  is_covid_year           INT64
);

-- Sample validation query - row counts per table
SELECT 'fact_loan_risk' AS table_name, COUNT(*) AS row_count FROM `bfsi_warehouse.fact_loan_risk`
UNION ALL
SELECT 'dim_npa_summary', COUNT(*) FROM `bfsi_warehouse.dim_npa_summary`
UNION ALL
SELECT 'dim_macro', COUNT(*) FROM `bfsi_warehouse.dim_macro`;
