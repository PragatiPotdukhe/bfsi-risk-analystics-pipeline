import os
import time
import requests
import pandas as pd
import wbgapi
from utils import get_logger

log = get_logger("extract")

# Toggle for local development / demo runs: both live sources have hard
# external blockers we hit and documented (RBI DBIE has a broken/HSTS-blocked
# SSL cert; data.gov.in gates the real resource behind email verification and
# the original resource ID couldn't be confirmed). Rather than silently fail,
# set USE_SAMPLE_DATA=true in .env to run the full pipeline end-to-end against
# the clearly-labelled synthetic CSVs in data/raw/ - see SAMPLE_DATA_README.md.
USE_SAMPLE_DATA = os.getenv("USE_SAMPLE_DATA", "false").lower() == "true"
_RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")


# -- Source 1: RBI DBIE ------------------------------------------------------
def extract_rbi():
    """Pull quarterly bank-wise NPA data from the RBI DBIE API."""
    if USE_SAMPLE_DATA:
        path = os.path.join(_RAW_DIR, "sample_rbi_npa_data.csv")
        log.info(f"USE_SAMPLE_DATA=true -> reading {path}")
        df = pd.read_csv(path)
        log.info(f"RBI (sample): {df.shape[0]} rows, {df.shape[1]} cols")
        return df

    RBI_KEY = os.getenv("RBI_API_KEY")
    if not RBI_KEY:
        raise ValueError("RBI_API_KEY not found in .env")

    url = "https://dbie.rbi.org.in/DBIE/dbie.rbi"
    params = {
        "site": "api",
        "type": "table",
        "id": "9",          # Table 9 = Scheduled Commercial Banks NPA data
        "format": "json",
        "apikey": RBI_KEY,
    }
    log.info("Fetching RBI NPA data...")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()

    payload = resp.json()
    # NOTE: verify the actual response shape once you have a live API key -
    # some DBIE endpoints wrap rows under "data", others under "records" or
    # "result". Print payload.keys() the first time you run this.
    df = pd.DataFrame(payload["data"])
    log.info(f"RBI: {df.shape[0]} rows, {df.shape[1]} cols")
    return df


# -- Source 2: data.gov.in ----------------------------------------------------
def extract_loans():
    """Pull district-level MSME loan disbursement data from data.gov.in (paginated)."""
    if USE_SAMPLE_DATA:
        # sample_msme_loans_data_full.csv: 46,970 rows / 671 districts / 28
        # states / FY2015-16 - FY2024-25 / 7 loan categories. District and
        # state names are real (public administrative reference data); every
        # loan/NPA figure is synthetic - generated, not observed. See
        # SAMPLE_DATA_README.md before quoting these numbers anywhere.
        path = os.path.join(_RAW_DIR, "sample_msme_loans_data_full.csv")
        log.info(f"USE_SAMPLE_DATA=true -> reading {path}")
        df = pd.read_csv(path)
        log.info(f"data.gov.in (sample): {df.shape[0]} rows, {df.shape[1]} cols")
        return df

    DATAGOV_KEY = os.getenv("DATAGOV_API_KEY")
    if not DATAGOV_KEY:
        raise ValueError("DATAGOV_API_KEY not found in .env")

    RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"  # MSME loan dataset
    all_records = []
    offset, limit = 0, 1000
    log.info("Fetching data.gov.in MSME loan data (paginated)...")

    while True:
        params = {
            "api-key": DATAGOV_KEY,
            "format": "json",
            "limit": limit,
            "offset": offset,
        }
        resp = requests.get(
            f"https://api.data.gov.in/resource/{RESOURCE_ID}",
            params=params, timeout=30,
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if not records:
            break
        all_records.extend(records)
        offset += limit
        log.info(f"  ...fetched {len(all_records)} rows")
        time.sleep(0.5)  # be polite - avoid hitting the daily rate limit

    df = pd.DataFrame(all_records)
    log.info(f"data.gov.in: {df.shape[0]} rows, {df.shape[1]} cols")
    return df


# -- Source 3: World Bank API -------------------------------------------------
def extract_macro():
    """Pull India macro indicators (2015-2024) from the World Bank via wbgapi."""
    INDICATORS = {
        "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",
        "FP.CPI.TOTL.ZG": "inflation_cpi_pct",
        "SL.UEM.TOTL.ZS": "unemployment_pct",
        "FR.INR.RINR": "real_interest_rate_pct",
    }
    log.info("Fetching World Bank macro indicators...")
    df_raw = wbgapi.data.DataFrame(
        list(INDICATORS.keys()),
        economy="IND",
        time=range(2015, 2025),
        index = "time",
        columns = "series",
        numericTimeKeys = True,
    )
    df = df_raw.rename(columns=INDICATORS).reset_index()
    df.rename(columns={"time": "year"}, inplace=True)
    df["year"] = df["year"].astype(int)
    log.info(f"World Bank: {df.shape[0]} rows")
    return df


if __name__ == "__main__":
    # Quick standalone smoke test - run `python extract.py` to sanity check
    # each source independently before wiring them into main.py.
    print(extract_macro().head())
