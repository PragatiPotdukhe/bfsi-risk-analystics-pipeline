import os
import logging
from dotenv import load_dotenv

load_dotenv()  # loads .env file into environment variables


def get_logger(name):
    """Standard logger - prints to console with timestamp."""
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(message)s",
        level=logging.INFO
    )
    return logging.getLogger(name)


def parse_fiscal_year(fy_str):
    """
    Converts "2022-23" to integer 2022 (start year).
    Used to join data.gov.in fiscal years to World Bank calendar years.
    """
    return int(str(fy_str)[:4])


def parse_rbi_quarter(q_str):
    """
    Converts "Q2:2023-24" to a proper date "2023-09-30".
    Q1=Jun30, Q2=Sep30, Q3=Dec31, Q4=Mar31 (Q4 rolls into the next calendar year).
    """
    quarter_end = {"Q1": "06-30", "Q2": "09-30", "Q3": "12-31", "Q4": "03-31"}
    parts = q_str.split(":")       # ["Q2", "2023-24"]
    q = parts[0]                   # "Q2"
    year = parts[1][:4]            # "2023"
    if q == "Q4":
        year = str(int(year) + 1)  # Q4:2023-24 -> 2024-03-31
    return f"{year}-{quarter_end[q]}"
