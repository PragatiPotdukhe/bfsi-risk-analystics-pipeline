-- Analytics-ready "current state" view: one row per state/district, using
-- each district's latest fiscal year. Aggregates across loan categories
-- since risk_tier in the raw fact table is computed per category-row - the
-- district's *current* tier should reflect its overall NPA rate across all
-- categories, not just one segment.

with district_year as (
    select
        state,
        district,
        year_int,
        sum(loans_disbursed)                       as loans_disbursed,
        sum(npa_count)                              as npa_count,
        sum(amt_disbursed_lakh)                     as amt_disbursed_lakh,
        sum(npa_amount_lakh)                        as npa_amount_lakh,
        avg(industry_npa_pct)                       as industry_npa_pct
    from {{ ref('stg_loan_risk') }}
    group by 1, 2, 3
),

with_rate as (
    select
        *,
        safe_divide(npa_count, loans_disbursed)     as npa_rate
    from district_year
),

tiered as (
    select
        *,
        case
            when npa_rate < 0.02 then 'Green (Low Risk)'
            when npa_rate < 0.05 then 'Amber (Watch)'
            when npa_rate < 0.10 then 'Red (High Risk)'
            when npa_rate is not null then 'Critical (>10%)'
            else 'Unknown'
        end                                          as risk_tier,
        npa_rate - (industry_npa_pct / 100)           as vs_industry,
        row_number() over (
            partition by state, district order by year_int desc
        )                                              as rn_current
    from with_rate
),

with_prior as (
    select
        cur.state,
        cur.district,
        cur.year_int              as current_year,
        cur.loans_disbursed,
        cur.npa_count,
        cur.amt_disbursed_lakh,
        cur.npa_amount_lakh,
        cur.npa_rate,
        cur.risk_tier,
        cur.vs_industry,
        prior.risk_tier            as prior_year_risk_tier
    from tiered cur
    left join tiered prior
        on cur.state = prior.state
        and cur.district = prior.district
        and prior.year_int = cur.year_int - 1
    where cur.rn_current = 1
)

select
    state,
    district,
    current_year,
    loans_disbursed,
    npa_count,
    amt_disbursed_lakh,
    npa_amount_lakh,
    round(npa_rate, 5)              as npa_rate,
    round(vs_industry, 5)           as vs_industry,
    risk_tier,
    prior_year_risk_tier,
    case
        when prior_year_risk_tier is null then 'New'
        when risk_tier = prior_year_risk_tier then 'Unchanged'
        else 'Changed'
    end                              as tier_movement
from with_prior
