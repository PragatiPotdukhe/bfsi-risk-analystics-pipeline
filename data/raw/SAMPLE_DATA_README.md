# sample_rbi_npa_data.csv — SYNTHETIC TEST DATA, NOT REAL RBI FIGURES

This file is fabricated data generated to unblock pipeline development while
RBI's DBIE portal (API access, and a broken SSL certificate on
dbie.rbi.org.in) was inaccessible. It is structured to look like the real
RBI "Quarterly Statistics on Deposits and Credit of Scheduled Commercial
Banks" release (same column shape as `clean_rbi()` expects), but the actual
numbers are randomly generated and mean nothing. 70 rows: 5 bank groups x 14
quarters.

**Use it only to:**
- Verify `extract_rbi()` / `clean_rbi()` run without errors
- Test the join logic in `join_all()` end-to-end
- Confirm the BigQuery load and Power BI connection work

**Before this project is "done," do one of the following — don't skip this:**
1. Swap this file for real RBI data once DBIE access is sorted (API key,
   working portal, or the Handbook of Statistics annual table), and delete
   this file, OR
2. If real RBI data genuinely can't be obtained, keep using representative
   data but say so explicitly and accurately in the README and in any
   interview — e.g. "the pipeline is designed to ingest live RBI NPA data;
   during development I used a representative synthetic dataset with the
   same schema, since [reason]." That is an honest description of a real
   engineering constraint, not something to hide.

**Do not** present numbers derived from this file as real RBI statistics in
the CV, dashboard commentary, or interviews. That would misrepresent
fabricated data as an official government source.

---

# sample_msme_loans_data_full.csv — SYNTHETIC, NOT REAL data.gov.in DATA (current default)

This is what `USE_SAMPLE_DATA=true` actually loads via `extract_loans()`
now, and what the CV's "~47,000 records / 620+ districts / 28 states"
Featured Project bullet is measured against.

**What's real:** every state name (28 states, no UTs) and every district
name (671 districts) — ordinary public administrative reference data, not
sourced from any confidential system.

**What's synthetic:** every single loan/NPA number. Generated column-by-column
from randomised distributions (lognormal loan volumes, a persistent
per-district "risk propensity" effect, a COVID-year dip/NPA spike in
2020-21, category multipliers across 7 MSME segments) — calibrated to be
*plausible*, not to reproduce any real published statistic. Nothing in this
file was observed; all of it was generated. See
`Pragati_CV_Generation_Prompt.md`-era discussion for why: the real
data.gov.in resource is gated behind email verification and the original
resource ID couldn't be confirmed.

**Shape:** 46,970 rows = 671 districts x 10 fiscal years (2015-16 to
2024-25) x 7 loan categories (Micro/Small/Medium x
Manufacturing/Services/Trade). Same columns as the old sample plus one:
`State, District, Year, Loan Category, Loans Sanctioned, Amt Sanctioned
Lakh, Loans Disbursed, Amt Disbursed Lakh, Npa Count, Npa Amount Lakh`.

Latest-year (2024-25) district-level risk tiers, aggregated across all 7
categories the same way `dbt/models/marts/dim_district_current_risk.sql`
does it: 361 Green, 214 Amber, 91 Red, 5 Critical -> **96 Red/Critical-tier
districts**. (The CV's original "87" was written before this dataset
existed - see the Featured Project bullet for the corrected, verified
number.)

**Do not** present these figures as real RBI or data.gov.in statistics —
in the README, the Power BI dashboard, the CV, or an interview. The honest
framing, and the one actually written into the CV, is: real Indian
geography, synthetic financial figures, at a scale that exercises the same
star schema and dbt models a production version would.

## sample_msme_loans_data.csv — superseded, kept for a quick smoke test

The original 155-row file (8 states, ~30 districts, 5 years) still works
fine if you just want a fast sanity check that `extract_loans()` /
`clean_loans()` run without error — it's not wired up as the default
anymore (`extract.py` now points at `sample_msme_loans_data_full.csv`).
Same synthetic-data rules apply to it.

## How the toggle works

```python
# etl/extract.py
USE_SAMPLE_DATA = os.getenv("USE_SAMPLE_DATA", "false").lower() == "true"
```

Set `USE_SAMPLE_DATA=true` in `.env` to run the full pipeline against these
files instead of the live RBI DBIE / data.gov.in APIs. Flip it to `false`
(and supply `RBI_API_KEY` / `DATAGOV_API_KEY`) if either live source ever
becomes usable — nothing else in the codebase needs to change.
