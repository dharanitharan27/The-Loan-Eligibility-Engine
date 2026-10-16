import io
import pytest
from backend.database import init_db, query_all
from backend.crawler import run_discovery
from backend.ingest_lambda import ingest_csv_stream
from backend.matcher import execute_matching_pipeline, calculate_score

def test_calculate_score():
    sample_product = {
        "product_id": "test-loan",
        "product_name": "Test Loan",
        "bank_name": "Test Bank",
        "interest_rate_min": 10.5,
        "min_income": 30000.0,
        "min_credit_score": 700
    }
    score, reasons = calculate_score(
        user_income=60000.0,
        user_score=750,
        user_age=30,
        emp_status="Salaried",
        product=sample_product
    )
    assert 50 <= score <= 100, f"Expected valid score, got {score}"
    assert len(reasons) >= 3

def test_optimization_funnel():
    init_db()
    # 1. Populate products
    run_discovery()

    # 2. Ingest test sample batch
    sample_csv = """user_id,name,email,monthly_income,credit_score,employment_status,age
b35de23e-755f-4c6a-81d8-f7dd99ce53ef,Dhruv Iyengar,dhruv.iyengar@example.com,131000,725,Self-Employed,37
77fce4da-b901-4b27-b1bb-01989567b98b,Tara Khan,tara.khan@example.com,38000,765,Self-Employed,36
2e29429d-17ba-4170-a9bc-ada98b018c58,Ananya Pandey,ananya.pandey@example.com,62000,705,Self-Employed,36
b0c5eb7b-3826-4f6c-ae09-8c8523bdf0a7,Shaurya Iyer,shaurya.iyer@example.com,31000,705,Self-Employed,43
363f26a0-3c05-49f1-a293-fc17bffca6e9,Ishaan Trivedi,ishaan.trivedi@example.com,35000,800,Salaried,34
"""
    stream = io.StringIO(sample_csv)
    ingest_csv_stream(stream, filename="matching_test.csv", batch_id="batch_matcher_test")

    # 3. Execute matching pipeline
    res = execute_matching_pipeline(batch_id="batch_matcher_test", run_llm=True)
    assert res["status"] == "success"
    assert res["total_users"] == 5
    assert res["final_matches_persisted"] > 0
    # Check that Top-3 capping per user holds
    matches = query_all("SELECT user_id, COUNT(*) as c FROM matches GROUP BY user_id;")
    for m in matches:
        assert m["c"] <= 3, "Each user should have at most Top 3 matches"
