-- Light cleanup/rename layer over the raw fact table. No business logic
-- here beyond column selection - that belongs in marts/.

with source as (
    select * from {{ source('bfsi_warehouse', 'fact_loan_risk') }}
)

select
    state,
    district,
    year                    as fiscal_year,
    year_int,
    loan_size_bucket,
    risk_tier,
    loans_sanctioned,
    amt_sanctioned_lakh,
    loans_disbursed,
    amt_disbursed_lakh,
    npa_count,
    npa_amount_lakh,
    disbursement_rate,
    npa_rate,
    avg_loan_size_lakh,
    avg_npa_size_lakh,
    gdp_growth_pct,
    inflation_cpi_pct,
    unemployment_pct,
    real_interest_rate_pct,
    industry_npa_pct,
    vs_industry,
    beats_industry
from source
