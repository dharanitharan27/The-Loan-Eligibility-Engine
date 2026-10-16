"""
AWS Lambda / Worker for Scalable Event-Driven User Data Ingestion.
Parses CSV from S3 event (or local stream) in memory-bounded batches and bulk-upserts into PostgreSQL RDS.
Triggers n8n Workflow B upon completion.
"""
import os
import io
import csv
import json
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import requests

from backend.database import get_connection, get_active_engine

logger = logging.getLogger("ingest_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/match-users")
BATCH_CHUNK_SIZE = 500


def clean_row(row: Dict[str, str], batch_id: str) -> Optional[Dict[str, Any]]:
    """Validates and casts a raw CSV row into typed fields."""
    try:
        user_id_raw = row.get("user_id", "").strip()
        if not user_id_raw:
            user_id = str(uuid.uuid4())
        else:
            # Validate or format UUID
            try:
                user_id = str(uuid.UUID(user_id_raw))
            except ValueError:
                user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id_raw))

        name = row.get("name", "").strip() or "Valued Customer"
        email = row.get("email", "").strip() or "customer@example.com"
        monthly_income = float(row.get("monthly_income", "0").replace(",", "").strip())
        credit_score = int(float(row.get("credit_score", "0").strip()))
        employment_status = row.get("employment_status", "Salaried").strip()
        age = int(float(row.get("age", "30").strip()))

        return {
            "user_id": user_id,
            "name": name,
            "email": email,
            "monthly_income": monthly_income,
            "credit_score": credit_score,
            "employment_status": employment_status,
            "age": age,
            "batch_id": batch_id
        }
    except Exception as e:
        logger.debug(f"Skipping malformed row {row}: {e}")
        return None


def ingest_csv_stream(file_stream: io.TextIOBase, filename: str, batch_id: Optional[str] = None) -> Dict[str, Any]:
    """Streams and inserts CSV data into PostgreSQL in chunks of BATCH_CHUNK_SIZE."""
    start_time = time.time()
    if not batch_id:
        batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    conn = get_connection()
    cursor = conn.cursor()
    engine = get_active_engine()

    reader = csv.DictReader(file_stream)
    total_read = 0
    total_inserted = 0
    chunk: List[Dict[str, Any]] = []

    def flush_chunk(rows_chunk: List[Dict[str, Any]]):
        nonlocal total_inserted
        if not rows_chunk:
            return

        if engine == "postgres":
            from psycopg2.extras import execute_values
            sql = """
            INSERT INTO users (
                user_id, name, email, monthly_income, credit_score, employment_status, age, batch_id, updated_at
            ) VALUES %s
            ON CONFLICT (user_id) DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email,
                monthly_income = EXCLUDED.monthly_income,
                credit_score = EXCLUDED.credit_score,
                employment_status = EXCLUDED.employment_status,
                age = EXCLUDED.age,
                batch_id = EXCLUDED.batch_id,
                updated_at = CURRENT_TIMESTAMP;
            """
            values = [
                (
                    r["user_id"], r["name"], r["email"], r["monthly_income"],
                    r["credit_score"], r["employment_status"], r["age"], r["batch_id"]
                ) for r in rows_chunk
            ]
            execute_values(cursor, sql, values, template="(%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)")
        else:
            # SQLite
            sql = """
            INSERT INTO users (
                user_id, name, email, monthly_income, credit_score, employment_status, age, batch_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                name = excluded.name,
                email = excluded.email,
                monthly_income = excluded.monthly_income,
                credit_score = excluded.credit_score,
                employment_status = excluded.employment_status,
                age = excluded.age,
                batch_id = excluded.batch_id,
                updated_at = CURRENT_TIMESTAMP;
            """
            values = [
                (
                    r["user_id"], r["name"], r["email"], r["monthly_income"],
                    r["credit_score"], r["employment_status"], r["age"], r["batch_id"]
                ) for r in rows_chunk
            ]
            cursor.executemany(sql, values)

        conn.commit()
        total_inserted += len(rows_chunk)

    try:
        # Mark batch as PROCESSING
        if engine == "postgres":
            cursor.execute("""
            INSERT INTO ingestion_batches (batch_id, filename, total_rows, processed_rows, status, created_at)
            VALUES (%s, %s, 0, 0, 'PROCESSING', CURRENT_TIMESTAMP)
            ON CONFLICT (batch_id) DO UPDATE SET status = 'PROCESSING';
            """, (batch_id, filename))
        else:
            cursor.execute("""
            INSERT INTO ingestion_batches (batch_id, filename, total_rows, processed_rows, status, created_at)
            VALUES (?, ?, 0, 0, 'PROCESSING', CURRENT_TIMESTAMP)
            ON CONFLICT (batch_id) DO UPDATE SET status = 'PROCESSING';
            """, (batch_id, filename))
        conn.commit()

        for row in reader:
            total_read += 1
            cleaned = clean_row(row, batch_id)
            if cleaned:
                chunk.append(cleaned)
                if len(chunk) >= BATCH_CHUNK_SIZE:
                    flush_chunk(chunk)
                    chunk = []

        if chunk:
            flush_chunk(chunk)

        # Mark batch as COMPLETED
        elapsed_sec = round(time.time() - start_time, 2)
        if engine == "postgres":
            cursor.execute("""
            UPDATE ingestion_batches
            SET total_rows = %s, processed_rows = %s, status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
            WHERE batch_id = %s;
            """, (total_read, total_inserted, batch_id))
        else:
            cursor.execute("""
            UPDATE ingestion_batches
            SET total_rows = ?, processed_rows = ?, status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
            WHERE batch_id = ?;
            """, (total_read, total_inserted, batch_id))
        conn.commit()

        logger.info(f"Ingested {total_inserted}/{total_read} rows in {elapsed_sec}s for batch {batch_id}")

        # Trigger n8n Workflow B via webhook
        n8n_response = notify_n8n_webhook(batch_id, total_inserted, filename)

        return {
            "status": "success",
            "batch_id": batch_id,
            "filename": filename,
            "total_rows_read": total_read,
            "processed_rows_inserted": total_inserted,
            "duration_seconds": elapsed_sec,
            "n8n_triggered": n8n_response
        }
    except Exception as e:
        logger.error(f"Error during batch ingestion: {e}", exc_info=True)
        if engine == "postgres":
            cursor.execute("UPDATE ingestion_batches SET status = 'FAILED', error_message = %s WHERE batch_id = %s;", (str(e), batch_id))
        else:
            cursor.execute("UPDATE ingestion_batches SET status = 'FAILED', error_message = ? WHERE batch_id = ?;", (str(e), batch_id))
        conn.commit()
        raise
    finally:
        cursor.close()
        conn.close()


def notify_n8n_webhook(batch_id: str, count: int, filename: str) -> bool:
    """Invokes n8n Webhook for Workflow B to commence matching."""
    webhook_payload = {
        "event": "CSV_INGESTION_COMPLETED",
        "batch_id": batch_id,
        "processed_rows": count,
        "filename": filename,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        logger.info(f"Triggering n8n webhook at {N8N_WEBHOOK_URL}...")
        res = requests.post(N8N_WEBHOOK_URL, json=webhook_payload, timeout=5)
        logger.info(f"n8n webhook response: {res.status_code}")
        return res.status_code in (200, 201)
    except Exception as e:
        logger.warning(f"Could not reach n8n webhook (n8n container may still be starting): {e}")
        return False


def handler(event, context):
    """
    AWS Lambda handler for S3 Event Notification:
    Triggered when a new CSV object is uploaded to S3.
    """
    logger.info(f"Received S3 Event: {json.dumps(event)}")
    try:
        import boto3
        s3 = boto3.client("s3")
        records = event.get("Records", [])
        results = []

        for record in records:
            bucket_name = record["s3"]["bucket"]["name"]
            object_key = record["s3"]["object"]["key"]

            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            csv_content = response["Body"].read().decode("utf-8")
            stream = io.StringIO(csv_content)

            batch_id = object_key.split("/")[1] if "uploads/" in object_key else None
            filename = os.path.basename(object_key)

            res = ingest_csv_stream(stream, filename=filename, batch_id=batch_id)
            results.append(res)

        return {
            "statusCode": 200,
            "body": json.dumps({"status": "success", "results": results})
        }
    except Exception as e:
        logger.error(f"Lambda S3 ingestion failed: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(e)})
        }


if __name__ == "__main__":
    from backend.database import init_db
    init_db()
    with open("data/users_sample.csv", "r", encoding="utf-8") as f:
        res = ingest_csv_stream(f, filename="users_sample.csv")
    print("Ingestion result:", json.dumps(res, indent=2))
