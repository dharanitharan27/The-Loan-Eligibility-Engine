"""
AWS Lambda / API Handler for generating secure S3 Pre-signed URLs for CSV uploads.
Solves API Gateway payload limits (10MB limit) & timeouts (29s) by allowing direct client-to-S3 uploads.
"""
import os
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from backend.database import get_connection, get_active_engine, execute_stmt

logger = logging.getLogger("presign_lambda")
logging.basicConfig(level=logging.INFO)

S3_BUCKET = os.getenv("UPLOAD_BUCKET", "loan-eligibility-engine-dev-user-csv-uploads")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")


def generate_presigned_url(filename: str, file_size: int = 0) -> Dict[str, Any]:
    """Generates an S3 pre-signed PUT URL and registers batch in DB."""
    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    clean_name = os.path.basename(filename) or "users.csv"
    s3_key = f"uploads/{batch_id}/{clean_name}"

    # Try creating AWS S3 presigned URL
    presigned_url = None
    try:
        import boto3
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": S3_BUCKET,
                "Key": s3_key,
                "ContentType": "text/csv"
            },
            ExpiresIn=3600
        )
    except Exception as e:
        logger.info(f"Local / non-AWS mode active. Generating local upload target: {e}")
        # In local mode, point directly to local backend ingest endpoint
        presigned_url = f"/api/upload/direct?batch_id={batch_id}&filename={clean_name}"

    # Register batch in database
    conn = get_connection()
    cursor = conn.cursor()
    engine = get_active_engine()
    try:
        if engine == "postgres":
            sql = """
            INSERT INTO ingestion_batches (batch_id, filename, total_rows, processed_rows, status, created_at)
            VALUES (%s, %s, 0, 0, 'PENDING', CURRENT_TIMESTAMP)
            ON CONFLICT (batch_id) DO NOTHING;
            """
            cursor.execute(sql, (batch_id, clean_name))
        else:
            sql = """
            INSERT INTO ingestion_batches (batch_id, filename, total_rows, processed_rows, status, created_at)
            VALUES (?, ?, 0, 0, 'PENDING', CURRENT_TIMESTAMP)
            ON CONFLICT (batch_id) DO NOTHING;
            """
            cursor.execute(sql, (batch_id, clean_name))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return {
        "status": "success",
        "batch_id": batch_id,
        "filename": clean_name,
        "s3_bucket": S3_BUCKET,
        "s3_key": s3_key,
        "upload_url": presigned_url,
        "expires_in_seconds": 3600
    }


def handler(event, context):
    """AWS Lambda entrypoint."""
    body = {}
    if event and "body" in event and event["body"]:
        try:
            body = json.loads(event["body"])
        except Exception:
            body = {}

    filename = body.get("filename", "users.csv")
    file_size = body.get("file_size", 0)

    result = generate_presigned_url(filename, file_size)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps(result)
    }


if __name__ == "__main__":
    res = generate_presigned_url("test_users.csv")
    print(json.dumps(res, indent=2))
