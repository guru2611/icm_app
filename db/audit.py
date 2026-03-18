"""
audit.py — SOX-compliant audit logging to BigQuery.

Every read of sensitive compensation data and every investigation is written to
the append-only Audit_Log table. Writes are fire-and-forget on daemon threads
so they never block the request path.

Actor identity is carried via the X-Actor HTTP header. In production this header
should be set by a trusted auth proxy (Google IAP, JWT middleware, etc.) — never
trusted from an unauthenticated client.
"""

import threading
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

PROJECT    = "glossy-buffer-411806"
DATASET    = "icm_analytics"
TABLE      = "Audit_Log"
_TABLE_REF = f"{PROJECT}.{DATASET}.{TABLE}"

_client = bigquery.Client(project=PROJECT)


def log_event(
    *,
    actor: str,
    action: str,
    source: str = "web",
    endpoint: str = "",
    target_employee_number: int | None = None,
    query_text: str | None = None,
    result_status: str = "success",
    error_message: str | None = None,
    ip_address: str = "",
    duration_ms: int | None = None,
) -> None:
    """
    Append one audit event to Audit_Log. Returns immediately.

    Args:
        actor:                   Identity of the requester (X-Actor header value).
        action:                  Logical operation name: investigate, employee_lookup,
                                 dispute_predictor, slack_investigate.
        source:                  Request origin: web | slack | api.
        endpoint:                HTTP path (e.g. /investigate).
        target_employee_number:  Employee whose data was accessed, if applicable.
        query_text:              Raw compensation query, if applicable.
        result_status:           success | error.
        error_message:           Exception message on error.
        ip_address:              Requester IP.
        duration_ms:             Time taken in milliseconds.
    """
    row = {
        "log_id":                 str(uuid.uuid4()),
        "timestamp":              datetime.now(timezone.utc).isoformat(),
        "actor":                  actor or "anonymous",
        "source":                 source,
        "action":                 action,
        "endpoint":               endpoint,
        "target_employee_number": target_employee_number,
        "query_text":             query_text,
        "result_status":          result_status,
        "error_message":          error_message,
        "ip_address":             ip_address,
        "duration_ms":            duration_ms,
    }
    threading.Thread(target=_write, args=(row,), daemon=True).start()


def _write(row: dict) -> None:
    try:
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        job = _client.load_table_from_json([row], _TABLE_REF, job_config=job_config)
        job.result()
    except Exception as exc:
        # Audit failures must never crash the application — log to stderr only.
        print(f"[audit] write error: {exc}")
