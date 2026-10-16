"""
Database Access Layer for Loan Eligibility Engine.
Supports PostgreSQL (RDS or local Docker) with fallback to SQLite for lightweight local unit testing.
"""
import os
import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "loan_engine")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgrespassword")
FORCE_SQLITE = os.getenv("FORCE_SQLITE", "false").lower() in ("true", "1")

# Track which engine is active
_active_engine = "postgres"


def _get_pg_connection():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
        connect_timeout=3
    )


def _get_sqlite_connection():
    os.makedirs("data", exist_ok=True)
    db_path = os.path.join("data", "local_loan_engine.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_connection():
    """Return an active database connection (PostgreSQL or SQLite fallback)."""
    global _active_engine
    if FORCE_SQLITE:
        _active_engine = "sqlite"
        return _get_sqlite_connection()

    try:
        conn = _get_pg_connection()
        _active_engine = "postgres"
        return conn
    except Exception:
        # Fallback to local SQLite for offline resilience
        _active_engine = "sqlite"
        return _get_sqlite_connection()


def get_active_engine() -> str:
    return _active_engine


def init_db(schema_file: str = "schema.sql"):
    """Initialize database tables and indexes."""
    global _active_engine
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if _active_engine == "postgres":
            if os.path.exists(schema_file):
                with open(schema_file, "r", encoding="utf-8") as f:
                    ddl = f.read()
                cursor.execute(ddl)
                conn.commit()
        else:
            # SQLite DDL equivalent
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_batches (
                batch_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                total_rows INTEGER DEFAULT 0,
                processed_rows INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'PENDING',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                monthly_income REAL NOT NULL,
                credit_score INTEGER NOT NULL,
                employment_status TEXT NOT NULL,
                age INTEGER NOT NULL,
                batch_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_income_credit ON users (monthly_income, credit_score);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_employment ON users (employment_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_age ON users (age);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_batch ON users (batch_id);")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS loan_products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                bank_name TEXT NOT NULL,
                interest_rate_min REAL NOT NULL,
                interest_rate_max REAL NOT NULL,
                processing_fee TEXT DEFAULT '1.0% - 2.5%',
                min_income REAL NOT NULL,
                min_credit_score INTEGER NOT NULL,
                allowed_employment_types TEXT NOT NULL DEFAULT '[\"Salaried\",\"Self-Employed\",\"Business\"]',
                min_age INTEGER NOT NULL DEFAULT 21,
                max_age INTEGER NOT NULL DEFAULT 60,
                max_loan_amount REAL NOT NULL,
                tenure_months_min INTEGER NOT NULL DEFAULT 12,
                tenure_months_max INTEGER NOT NULL DEFAULT 60,
                features TEXT NOT NULL DEFAULT '{}',
                source_url TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_criteria ON loan_products (min_income, min_credit_score, is_active);")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                eligibility_score REAL NOT NULL,
                match_reasons TEXT NOT NULL DEFAULT '[]',
                ai_recommendation TEXT,
                notified INTEGER NOT NULL DEFAULT 0,
                notified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, product_id)
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_user_id ON matches (user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_notified ON matches (notified);")
            conn.commit()
    finally:
        cursor.close()
        conn.close()


def query_all(sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    """Execute a SELECT query and return list of dicts."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        if _active_engine == "postgres":
            return [dict(r) for r in rows]
        else:
            return [dict(r) for r in rows]
    finally:
        cursor.close()
        conn.close()


def query_one(sql: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
    """Execute a SELECT query and return a single dict."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        cursor.close()
        conn.close()


def execute_stmt(sql: str, params: Tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE statement and commit."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        conn.close()
