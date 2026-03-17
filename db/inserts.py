from google.cloud import bigquery

def load_fiscal_calendar(project_id, dataset_id):
    client = bigquery.Client(project=project_id)
    table_ref = f"{project_id}.{dataset_id}.Fiscal_Calendar_Details"

    rows = [
        {"Fiscal_Calendar_ID": 1,  "Fiscal_Year": 2024, "Fiscal_Start_Date": "2023-02-01", "Fiscal_End_Date": "2024-01-31", "Quarter_Start_Date": "2023-02-01", "Quarter_End_Date": "2023-04-30", "Quarter_Number": 1},
        {"Fiscal_Calendar_ID": 2,  "Fiscal_Year": 2024, "Fiscal_Start_Date": "2023-02-01", "Fiscal_End_Date": "2024-01-31", "Quarter_Start_Date": "2023-05-01", "Quarter_End_Date": "2023-07-31", "Quarter_Number": 2},
        {"Fiscal_Calendar_ID": 3,  "Fiscal_Year": 2024, "Fiscal_Start_Date": "2023-02-01", "Fiscal_End_Date": "2024-01-31", "Quarter_Start_Date": "2023-08-01", "Quarter_End_Date": "2023-10-31", "Quarter_Number": 3},
        {"Fiscal_Calendar_ID": 4,  "Fiscal_Year": 2024, "Fiscal_Start_Date": "2023-02-01", "Fiscal_End_Date": "2024-01-31", "Quarter_Start_Date": "2023-11-01", "Quarter_End_Date": "2024-01-31", "Quarter_Number": 4},
        {"Fiscal_Calendar_ID": 5,  "Fiscal_Year": 2025, "Fiscal_Start_Date": "2024-02-01", "Fiscal_End_Date": "2025-01-31", "Quarter_Start_Date": "2024-02-01", "Quarter_End_Date": "2024-04-30", "Quarter_Number": 1},
        {"Fiscal_Calendar_ID": 6,  "Fiscal_Year": 2025, "Fiscal_Start_Date": "2024-02-01", "Fiscal_End_Date": "2025-01-31", "Quarter_Start_Date": "2024-05-01", "Quarter_End_Date": "2024-07-31", "Quarter_Number": 2},
        {"Fiscal_Calendar_ID": 7,  "Fiscal_Year": 2025, "Fiscal_Start_Date": "2024-02-01", "Fiscal_End_Date": "2025-01-31", "Quarter_Start_Date": "2024-08-01", "Quarter_End_Date": "2024-10-31", "Quarter_Number": 3},
        {"Fiscal_Calendar_ID": 8,  "Fiscal_Year": 2025, "Fiscal_Start_Date": "2024-02-01", "Fiscal_End_Date": "2025-01-31", "Quarter_Start_Date": "2024-11-01", "Quarter_End_Date": "2025-01-31", "Quarter_Number": 4},
        {"Fiscal_Calendar_ID": 9,  "Fiscal_Year": 2026, "Fiscal_Start_Date": "2025-02-01", "Fiscal_End_Date": "2026-01-31", "Quarter_Start_Date": "2025-02-01", "Quarter_End_Date": "2025-04-30", "Quarter_Number": 1},
        {"Fiscal_Calendar_ID": 10, "Fiscal_Year": 2026, "Fiscal_Start_Date": "2025-02-01", "Fiscal_End_Date": "2026-01-31", "Quarter_Start_Date": "2025-05-01", "Quarter_End_Date": "2025-07-31", "Quarter_Number": 2},
        {"Fiscal_Calendar_ID": 11, "Fiscal_Year": 2026, "Fiscal_Start_Date": "2025-02-01", "Fiscal_End_Date": "2026-01-31", "Quarter_Start_Date": "2025-08-01", "Quarter_End_Date": "2025-10-31", "Quarter_Number": 3},
        {"Fiscal_Calendar_ID": 12, "Fiscal_Year": 2026, "Fiscal_Start_Date": "2025-02-01", "Fiscal_End_Date": "2026-01-31", "Quarter_Start_Date": "2025-11-01", "Quarter_End_Date": "2026-01-31", "Quarter_Number": 4},
        {"Fiscal_Calendar_ID": 13, "Fiscal_Year": 2027, "Fiscal_Start_Date": "2026-02-01", "Fiscal_End_Date": "2027-01-31", "Quarter_Start_Date": "2026-02-01", "Quarter_End_Date": "2026-04-30", "Quarter_Number": 1},
        {"Fiscal_Calendar_ID": 14, "Fiscal_Year": 2027, "Fiscal_Start_Date": "2026-02-01", "Fiscal_End_Date": "2027-01-31", "Quarter_Start_Date": "2026-05-01", "Quarter_End_Date": "2026-07-31", "Quarter_Number": 2},
        {"Fiscal_Calendar_ID": 15, "Fiscal_Year": 2027, "Fiscal_Start_Date": "2026-02-01", "Fiscal_End_Date": "2027-01-31", "Quarter_Start_Date": "2026-08-01", "Quarter_End_Date": "2026-10-31", "Quarter_Number": 3},
        {"Fiscal_Calendar_ID": 16, "Fiscal_Year": 2027, "Fiscal_Start_Date": "2026-02-01", "Fiscal_End_Date": "2027-01-31", "Quarter_Start_Date": "2026-11-01", "Quarter_End_Date": "2027-01-31", "Quarter_Number": 4},
    ]

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )

    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()
    print(f"[+] Loaded {len(rows)} rows into {table_ref}")

if __name__ == "__main__":
    PROJECT = "glossy-buffer-411806"
    DATASET = "icm_analytics"
    load_fiscal_calendar(PROJECT, DATASET)
