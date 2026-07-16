with source as (
    select * from {{ source('bfsi_warehouse', 'dim_npa_summary') }}
)

select
    bank_group,
    bank_category,
    quarter,
    quarter_date,
    year,
    gross_npa_pct,
    net_npa_pct,
    gross_advances_cr,
    gross_npa_amt_cr,
    provision_coverage,
    slma_pct
from source
