-- SCD2 snapshot of each district's current risk tier. Why a snapshot and
-- not just a versioned table: dim_district_current_risk is rebuilt fresh on
-- every dbt run (WRITE_TRUNCATE upstream), so it only ever shows "now" - if
-- a district gets reclassified from Amber to Red between two Airflow runs,
-- that transition is lost unless something preserves history. This
-- snapshot is that audit trail: "when did District X first get flagged
-- Critical" is a real BFSI/regulatory question, and check-strategy on
-- (risk_tier, npa_rate) means a new row is only inserted when the
-- classification actually changes, not on every run.

{% snapshot district_risk_tier_snapshot %}

{{
    config(
        target_schema='snapshots',
        unique_key="concat(state, '|', district)",
        strategy='check',
        check_cols=['risk_tier', 'npa_rate', 'current_year'],
    )
}}

select
    state,
    district,
    current_year,
    npa_rate,
    risk_tier,
    tier_movement
from {{ ref('dim_district_current_risk') }}

{% endsnapshot %}
