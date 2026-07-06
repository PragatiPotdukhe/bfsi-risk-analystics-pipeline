import os
from google.cloud import bigquery
from google.oauth2 import service_account
from utils import get_logger

log = get_logger("load")


def get_bq_client():
    """Returns an authenticated BigQuery client using the service account key."""
    # key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gcp_key.json")
    project = os.getenv("GCP_PROJECT_ID")
    # creds = service_account.Credentials.from_service_account_file(
    #     key_path,
    #     scopes=["https://www.googleapis.com/auth/cloud-platform"],
    # )
    # return bigquery.Client(credentials=creds, project=project)
    return bigquery.Client(project = project)

 
def load_table(df, table_name, client, write_mode="WRITE_TRUNCATE"):
    """
    Loads a DataFrame into a BigQuery table.

    write_mode options:
      WRITE_TRUNCATE = replace the table (correct here - each data.gov.in /
                        RBI pull is a full snapshot, not an incremental feed)
      WRITE_APPEND   = add rows (use this instead if a source ever becomes
                        incremental, e.g. a transaction log with a watermark)
    """
    dataset = os.getenv("GCP_DATASET", "bfsi_warehouse")
    project = os.getenv("GCP_PROJECT_ID")
    table_id = f"{project}.{dataset}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        write_disposition=write_mode,
        autodetect=True,  # BigQuery infers schema from the DataFrame
    )

    log.info(f"Loading {len(df)} rows -> {table_id}")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # blocks until the load job completes
    log.info(f"  Done. Rows loaded: {job.output_rows}")
    return job.output_rows
