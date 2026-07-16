-- Singular test: fails if district coverage drops below 620 (the "620+
-- MSME districts across 28 states" figure quoted on the CV/README). This
-- makes that claim a living, tested fact rather than a one-time observation
-- - if the sample data or a filter upstream ever shrinks coverage, dbt test
-- catches it before the number gets quoted anywhere again.

with coverage as (
    select
        count(distinct concat(state, '|', district)) as district_count,
        count(distinct state)                          as state_count
    from {{ ref('dim_district_current_risk') }}
)

select *
from coverage
where district_count < 620
   or state_count < 28
