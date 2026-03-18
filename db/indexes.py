"""
db/indexes.py — BigQuery clustering and partitioning for ICM tables.

Strategy
--------
Sale_Details       partition MONTH(Sale_Transaction_Date), cluster Employee_Number, Location_ID
Worker_Pay_Details partition MONTH(Pay_Period_Start_Date),  cluster Employee_Number, Comp_Plan_ID
Audit_Log          partition DAY(timestamp),                cluster actor, action
Worker_History     cluster Employee_Number          (ALTER TABLE — no partition needed)
Plan_assignment    cluster Employee_Number          (ALTER TABLE — no partition needed)

Run order
---------
  python -m db.indexes

Idempotent: apply_clustering() uses ALTER TABLE (safe to re-run).
migrate_to_partitioned() is destructive — it drops and recreates tables.
Run it once on a fresh/seed environment; not needed for tables created via
the updated deploy_full_icm_schema() which already includes partition config.
"""

import datetime
from decimal import Decimal

from google.cloud import bigquery
from google.cloud.bigquery.table import PrimaryKey, TableConstraints

PROJECT = "glossy-buffer-411806"
DATASET = "icm_analytics"

_client = None


def _get_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=PROJECT)
    return _client


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ref(table: str) -> str:
    return f"`{PROJECT}.{DATASET}.{table}`"


def _serialize(row: dict) -> dict:
    """Convert DATE / TIMESTAMP / Decimal values to JSON-serialisable types."""
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime.datetime):
            out[k] = v.isoformat()
        elif isinstance(v, datetime.date):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = str(v)   # keep NUMERIC precision
        else:
            out[k] = v
    return out


def _read_all(client: bigquery.Client, table_id: str) -> list[dict]:
    rows = client.query(f"SELECT * FROM {_ref(table_id)}").result()
    return [_serialize(dict(row)) for row in rows]


def _reload(client: bigquery.Client, table_id: str, rows: list[dict]) -> None:
    if not rows:
        return
    job = client.load_table_from_json(
        rows,
        f"{PROJECT}.{DATASET}.{table_id}",
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        ),
    )
    job.result()


# ── Step 1: Clustering-only (ALTER TABLE) ──────────────────────────────────────

def apply_clustering() -> None:
    """
    Add clustering to Worker_History and Plan_assignment via the table update API.
    This is a metadata operation — safe to run on populated tables. BigQuery
    will gradually reorganise existing data; new data is immediately clustered.
    """
    client = _get_client()
    targets = {
        "Worker_History": ["Employee_Number"],
        "Plan_assignment": ["Employee_Number"],
    }
    for table_id, cols in targets.items():
        print(f"  {table_id} CLUSTER BY {', '.join(cols)} ...", end=" ", flush=True)
        table = client.get_table(f"{PROJECT}.{DATASET}.{table_id}")
        table.clustering_fields = cols
        client.update_table(table, ["clustering_fields"])
        print("done")


# ── Step 2: Partition + cluster migrations ─────────────────────────────────────

def _migrate(
    client: bigquery.Client,
    table_id: str,
    schema: list[bigquery.SchemaField],
    partitioning: bigquery.TimePartitioning,
    clustering: list[str],
    primary_key_col: str | None = None,
) -> None:
    print(f"\n[{table_id}]")
    print(f"  Reading existing rows ...", end=" ", flush=True)
    rows = _read_all(client, table_id)
    print(f"{len(rows)} rows")

    print(f"  Dropping table ...", end=" ", flush=True)
    client.delete_table(f"{PROJECT}.{DATASET}.{table_id}")
    print("done")

    table = bigquery.Table(f"{PROJECT}.{DATASET}.{table_id}", schema=schema)
    table.time_partitioning = partitioning
    table.clustering_fields = clustering
    if primary_key_col:
        table.table_constraints = TableConstraints(
            primary_key=PrimaryKey(columns=[primary_key_col]),
            foreign_keys=[],
        )

    part_desc = f"PARTITION BY {partitioning.type_}({partitioning.field})"
    clust_desc = f"CLUSTER BY {', '.join(clustering)}"
    print(f"  Recreating with {part_desc}, {clust_desc} ...", end=" ", flush=True)
    client.create_table(table)
    print("done")

    print(f"  Reloading {len(rows)} rows ...", end=" ", flush=True)
    _reload(client, table_id, rows)
    print("done")


def migrate_to_partitioned() -> None:
    """
    Recreate Sale_Details, Worker_Pay_Details, and Audit_Log with time
    partitioning and clustering. Existing rows are preserved.
    """
    client = _get_client()

    # Sale_Details — MONTH(Sale_Transaction_Date), cluster Employee_Number, Location_ID
    _migrate(
        client,
        table_id="Sale_Details",
        schema=[
            bigquery.SchemaField("Transaction_ID",        "INT64",  mode="REQUIRED", description="Primary Key"),
            bigquery.SchemaField("Sale_Transaction_Date", "DATE"),
            bigquery.SchemaField("Location_ID",           "INT64"),
            bigquery.SchemaField("Employee_Number",       "INT64"),
            bigquery.SchemaField("Total_Sale_Amount",     "INT64"),
        ],
        partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.MONTH,
            field="Sale_Transaction_Date",
        ),
        clustering=["Employee_Number", "Location_ID"],
        primary_key_col="Transaction_ID",
    )

    # Worker_Pay_Details — MONTH(Pay_Period_Start_Date), cluster Employee_Number, Comp_Plan_ID
    _migrate(
        client,
        table_id="Worker_Pay_Details",
        schema=[
            bigquery.SchemaField("Employee_Number",       "INT64",   mode="REQUIRED"),
            bigquery.SchemaField("Payment_Date",          "DATE"),
            bigquery.SchemaField("Comp_Plan_ID",          "INT64"),
            bigquery.SchemaField("Pay_Period_Start_Date", "DATE"),
            bigquery.SchemaField("Pay_Period_End_Date",   "DATE"),
            bigquery.SchemaField("Amount_Paid",           "NUMERIC"),
        ],
        partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.MONTH,
            field="Pay_Period_Start_Date",
        ),
        clustering=["Employee_Number", "Comp_Plan_ID"],
    )

    # Audit_Log — DAY(timestamp), cluster actor, action
    _migrate(
        client,
        table_id="Audit_Log",
        schema=[
            bigquery.SchemaField("log_id",                 "STRING",    mode="REQUIRED"),
            bigquery.SchemaField("timestamp",              "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("actor",                  "STRING",    mode="REQUIRED"),
            bigquery.SchemaField("source",                 "STRING"),
            bigquery.SchemaField("action",                 "STRING"),
            bigquery.SchemaField("endpoint",               "STRING"),
            bigquery.SchemaField("target_employee_number", "INT64"),
            bigquery.SchemaField("query_text",             "STRING"),
            bigquery.SchemaField("result_status",          "STRING"),
            bigquery.SchemaField("error_message",          "STRING"),
            bigquery.SchemaField("ip_address",             "STRING"),
            bigquery.SchemaField("duration_ms",            "INT64"),
        ],
        partitioning=bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="timestamp",
        ),
        clustering=["actor", "action"],
    )


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Step 1: Apply clustering (ALTER TABLE) ===")
    apply_clustering()

    print("\n=== Step 2: Migrate to partitioned tables ===")
    migrate_to_partitioned()

    print("\n=== Done ===")
