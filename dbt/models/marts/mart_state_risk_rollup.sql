-- State-level executive rollup: district counts per risk tier, average NPA
-- rate, and % of districts beating the industry NPA benchmark. Feeds the
-- Power BI state-level summary page.

select
    state,
    count(*)                                                        as district_count,
    countif(risk_tier = 'Green (Low Risk)')                         as green_districts,
    countif(risk_tier = 'Amber (Watch)')                             as amber_districts,
    countif(risk_tier = 'Red (High Risk)')                           as red_districts,
    countif(risk_tier = 'Critical (>10%)')                           as critical_districts,
    countif(risk_tier in ('Red (High Risk)', 'Critical (>10%)'))    as red_or_critical_districts,
    round(avg(npa_rate), 5)                                          as avg_npa_rate,
    round(safe_divide(countif(vs_industry < 0), count(*)), 4)       as pct_beating_industry
from {{ ref('dim_district_current_risk') }}
group by 1
order by red_or_critical_districts desc
