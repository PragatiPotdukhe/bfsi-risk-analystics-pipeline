-- Year-over-year tier composition across the full 10-year window (not just
-- current year) - feeds the Power BI trend page. Aggregated at
-- district-year grain across all loan categories, same logic as
-- dim_district_current_risk but without collapsing to "latest year only".

with district_year as (
    select
        state,
        district,
        year_int,
        sum(loans_disbursed)   as loans_disbursed,
        sum(npa_count)          as npa_count
    from {{ ref('stg_loan_risk') }}
    group by 1, 2, 3
),

tiered as (
    select
        state,
        district,
        year_int,
        safe_divide(npa_count, loans_disbursed) as npa_rate,
        case
            when safe_divide(npa_count, loans_disbursed) < 0.02 then 'Green (Low Risk)'
            when safe_divide(npa_count, loans_disbursed) < 0.05 then 'Amber (Watch)'
            when safe_divide(npa_count, loans_disbursed) < 0.10 then 'Red (High Risk)'
            when loans_disbursed > 0 then 'Critical (>10%)'
            else 'Unknown'
        end as risk_tier
    from district_year
)

select
    year_int,
    risk_tier,
    count(*)                    as district_count,
    round(avg(npa_rate), 5)     as avg_npa_rate
from tiered
group by 1, 2
order by 1, 2
