-- Loan Eligibility Engine Database Schema (PostgreSQL)
-- Supports high-performance indexed queries for multi-stage matching optimization

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Table 1: Ingestion Batches (Audit & Monitoring)
CREATE TABLE IF NOT EXISTS ingestion_batches (
    batch_id VARCHAR(100) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    total_rows INTEGER DEFAULT 0,
    processed_rows INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING', -- PENDING, PROCESSING, COMPLETED, FAILED
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Table 2: Users (Ingested via scalable batch pipeline)
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    monthly_income NUMERIC(12, 2) NOT NULL,
    credit_score INTEGER NOT NULL,
    employment_status VARCHAR(50) NOT NULL, -- Salaried, Self-Employed, Business
    age INTEGER NOT NULL,
    batch_id VARCHAR(100) REFERENCES ingestion_batches(batch_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indices for ultra-fast matching query optimization (Treasure Hunt Stage 1)
CREATE INDEX IF NOT EXISTS idx_users_income_credit ON users (monthly_income, credit_score);
CREATE INDEX IF NOT EXISTS idx_users_employment ON users (employment_status);
CREATE INDEX IF NOT EXISTS idx_users_age ON users (age);
CREATE INDEX IF NOT EXISTS idx_users_batch ON users (batch_id);

-- Table 3: Loan Products (Discovered by autonomous web crawler)
CREATE TABLE IF NOT EXISTS loan_products (
    product_id VARCHAR(100) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    bank_name VARCHAR(255) NOT NULL,
    interest_rate_min NUMERIC(5, 2) NOT NULL,
    interest_rate_max NUMERIC(5, 2) NOT NULL,
    processing_fee VARCHAR(255) DEFAULT '1.0% - 2.5%',
    min_income NUMERIC(12, 2) NOT NULL,
    min_credit_score INTEGER NOT NULL,
    allowed_employment_types TEXT[] NOT NULL DEFAULT ARRAY['Salaried', 'Self-Employed', 'Business'],
    min_age INTEGER NOT NULL DEFAULT 21,
    max_age INTEGER NOT NULL DEFAULT 60,
    max_loan_amount NUMERIC(12, 2) NOT NULL,
    tenure_months_min INTEGER NOT NULL DEFAULT 12,
    tenure_months_max INTEGER NOT NULL DEFAULT 60,
    features JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_url TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_products_criteria ON loan_products (min_income, min_credit_score, is_active);

-- Table 4: Matches (Eligibility Results & AI Recommendations)
CREATE TABLE IF NOT EXISTS matches (
    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    product_id VARCHAR(100) NOT NULL REFERENCES loan_products(product_id) ON DELETE CASCADE,
    eligibility_score NUMERIC(5, 2) NOT NULL, -- 0.00 to 100.00
    match_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    ai_recommendation TEXT,
    notified BOOLEAN NOT NULL DEFAULT FALSE,
    notified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_user_id ON matches (user_id);
CREATE INDEX IF NOT EXISTS idx_matches_notified ON matches (notified);
CREATE INDEX IF NOT EXISTS idx_matches_user_notified ON matches (user_id, notified);
