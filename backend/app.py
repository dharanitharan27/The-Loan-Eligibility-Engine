"""
FastAPI Server for Loan Eligibility Engine.
Provides REST APIs for CSV ingestion, pipeline orchestration, database inspection, and UI dashboard.
"""
import os
import io
import json
import logging
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from backend.database import init_db, query_all, query_one, get_active_engine
from backend.presign_lambda import generate_presigned_url
from backend.ingest_lambda import ingest_csv_stream
from backend.crawler import run_discovery
from backend.matcher import execute_matching_pipeline
from backend.email_service import dispatch_all_pending_notifications

logger = logging.getLogger("api_server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Loan Eligibility Engine API",
    description="End-to-End Automated Loan Matching & Notification Architecture",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info(f"Database initialized. Active engine: {get_active_engine()}")


@app.get("/api/health")
def health_check():
    engine = get_active_engine()
    return {
        "status": "healthy",
        "database_engine": engine,
        "n8n_url": os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/match-users"),
        "ses_region": os.getenv("AWS_REGION", "ap-south-1")
    }


class PresignRequest(BaseModel):
    filename: str = "users.csv"
    file_size: int = 0


@app.post("/api/upload/presign")
def create_presigned_url(payload: PresignRequest):
    """Generate S3 Pre-signed URL for direct bulk upload."""
    return generate_presigned_url(payload.filename, payload.file_size)


@app.post("/api/upload/direct")
async def direct_upload_csv(
    file: UploadFile = File(...),
    batch_id: Optional[str] = Query(None)
):
    """
    Direct CSV file upload handler.
    Streams CSV rows directly into database with memory-bounded chunking.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    content = await file.read()
    stream = io.StringIO(content.decode("utf-8", errors="replace"))

    result = ingest_csv_stream(stream, filename=file.filename, batch_id=batch_id)
    return result


@app.post("/api/pipeline/discover")
def trigger_discovery():
    """Trigger Workflow A: Discover and crawl loan products."""
    res = run_discovery()
    return res


class MatchRequest(BaseModel):
    batch_id: Optional[str] = None
    limit_users: Optional[int] = None
    run_llm: bool = True


@app.post("/api/pipeline/match")
def trigger_matching(payload: MatchRequest):
    """Trigger Workflow B: Multi-stage optimized matching."""
    res = execute_matching_pipeline(
        batch_id=payload.batch_id,
        limit_users=payload.limit_users,
        run_llm=payload.run_llm
    )
    return res


class NotifyRequest(BaseModel):
    limit: int = 5
    test_recipient: Optional[str] = None


@app.post("/api/pipeline/notify")
def trigger_notification(payload: NotifyRequest):
    """Trigger Workflow C: Send personalized email notifications to safe test inbox."""
    res = dispatch_all_pending_notifications(
        limit=payload.limit,
        test_recipient=payload.test_recipient
    )
    return res


@app.get("/api/stats")
def get_stats():
    """Returns platform KPI metrics and pipeline summary."""
    users_count = query_one("SELECT COUNT(*) as c FROM users")
    products_count = query_one("SELECT COUNT(*) as c FROM loan_products WHERE is_active = 1 OR is_active = TRUE")
    matches_count = query_one("SELECT COUNT(*) as c FROM matches")
    engine = get_active_engine()
    if engine == "postgres":
        notified_count = query_one("SELECT COUNT(*) as c FROM matches WHERE notified = TRUE")
    else:
        notified_count = query_one("SELECT COUNT(*) as c FROM matches WHERE notified = 1")
    batches_count = query_one("SELECT COUNT(*) as c FROM ingestion_batches")

    u_c = users_count["c"] if users_count else 0
    p_c = products_count["c"] if products_count else 0
    m_c = matches_count["c"] if matches_count else 0
    n_c = notified_count["c"] if notified_count else 0
    b_c = batches_count["c"] if batches_count else 0

    cartesian = u_c * p_c
    prune_ratio = round((1.0 - (m_c / max(1, cartesian))) * 100, 2) if cartesian > 0 else 0

    return {
        "total_users": u_c,
        "active_loan_products": p_c,
        "total_matches": m_c,
        "total_notifications_sent": n_c,
        "total_batches": b_c,
        "theoretical_cartesian_pairs": cartesian,
        "optimization_prune_rate_pct": prune_ratio,
        "database_engine": engine
    }


@app.get("/api/users")
def get_users(limit: int = 50, offset: int = 0):
    return query_all(f"SELECT * FROM users ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}")


@app.get("/api/products")
def get_products():
    return query_all("SELECT * FROM loan_products ORDER BY interest_rate_min ASC")


@app.get("/api/matches")
def get_matches(limit: int = 50, offset: int = 0):
    sql = """
    SELECT m.match_id, m.user_id, m.product_id, m.eligibility_score, m.match_reasons,
           m.ai_recommendation, m.notified, m.notified_at, m.created_at,
           u.name as user_name, u.email as user_email, u.monthly_income, u.credit_score, u.employment_status,
           p.product_name, p.bank_name, p.interest_rate_min, p.max_loan_amount
    FROM matches m
    JOIN users u ON m.user_id = u.user_id
    JOIN loan_products p ON m.product_id = p.product_id
    ORDER BY m.eligibility_score DESC
    LIMIT %s OFFSET %s;
    """ if get_active_engine() == "postgres" else """
    SELECT m.match_id, m.user_id, m.product_id, m.eligibility_score, m.match_reasons,
           m.ai_recommendation, m.notified, m.notified_at, m.created_at,
           u.name as user_name, u.email as user_email, u.monthly_income, u.credit_score, u.employment_status,
           p.product_name, p.bank_name, p.interest_rate_min, p.max_loan_amount
    FROM matches m
    JOIN users u ON m.user_id = u.user_id
    JOIN loan_products p ON m.product_id = p.product_id
    ORDER BY m.eligibility_score DESC
    LIMIT ? OFFSET ?;
    """
    return query_all(sql, (limit, offset))


@app.get("/api/emails/latest")
def get_latest_email_preview():
    """Returns the most recently generated email HTML for browser viewing."""
    archive_dir = os.path.join("data", "sent_emails")
    if not os.path.exists(archive_dir):
        return HTMLResponse("<h3>No emails sent yet. Run Workflow C to generate preview.</h3>")

    files = [os.path.join(archive_dir, f) for f in os.listdir(archive_dir) if f.endswith(".html")]
    if not files:
        return HTMLResponse("<h3>No emails sent yet. Run Workflow C to generate preview.</h3>")

    files.sort(key=os.path.getmtime, reverse=True)
    with open(files[0], "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# Serve frontend static assets
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
