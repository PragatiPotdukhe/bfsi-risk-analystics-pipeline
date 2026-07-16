-- Singular test: fails (returns rows) if any district's risk_tier
-- disagrees with the npa_rate thresholds it should have been bucketed by.
-- Guards against the tier logic in dim_district_current_risk.sql drifting
-- out of sync with etl/transform.py::risk_tier() over time.

select *
from {{ ref('dim_district_current_risk') }}
where
    (risk_tier = 'Green (Low Risk)' and npa_rate >= 0.02)
    or (risk_tier = 'Amber (Watch)' and (npa_rate < 0.02 or npa_rate >= 0.05))
    or (risk_tier = 'Red (High Risk)' and (npa_rate < 0.05 or npa_rate >= 0.10))
    or (risk_tier = 'Critical (>10%)' and npa_rate < 0.10)
