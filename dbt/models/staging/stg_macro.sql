with source as (
    select * from {{ source('bfsi_warehouse', 'dim_macro') }}
)

select
    year,
    gdp_growth_pct,
    inflation_cpi_pct,
    unemployment_pct,
    real_interest_rate_pct,
    is_covid_year
from source
