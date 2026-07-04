import os
import time
import requests
import pandas as pd
import wbgapi
from utils import get_logger

log = get_logger("extract")


# -- Source 1: RBI DBIE ------------------------------------------------------
def extract_rbi():
    """Pull quarterly bank-wise NPA data from the RBI DBIE API."""
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
