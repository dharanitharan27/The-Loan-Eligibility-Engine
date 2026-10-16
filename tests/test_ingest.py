import io
import pytest
from backend.database import init_db, query_all, query_one
from backend.ingest_lambda import ingest_csv_stream, clean_row

def test_clean_row():
    raw = {
        "user_id": "b35de23e-755f-4c6a-81d8-f7dd99ce53ef",
        "name": "Dhruv Iyengar",
        "email": "dhruv.iyengar@example.com",
        "monthly_income": "131000",
        "credit_score": "725",
        "employment_status": "Self-Employed",
        "age": "37"
    }
    cleaned = clean_row(raw, batch_id="batch_test")
    assert cleaned is not None
    assert cleaned["user_id"] == "b35de23e-755f-4c6a-81d8-f7dd99ce53ef"
    assert cleaned["monthly_income"] == 131000.0
    assert cleaned["credit_score"] == 725
    assert cleaned["age"] == 37

def test_ingest_sample_csv():
    init_db()
    sample_csv = """user_id,name,email,monthly_income,credit_score,employment_status,age
b35de23e-755f-4c6a-81d8-f7dd99ce53ef,Dhruv Iyengar,dhruv.iyengar@example.com,131000,725,Self-Employed,37
77fce4da-b901-4b27-b1bb-01989567b98b,Tara Khan,tara.khan@example.com,38000,765,Self-Employed,36
2e29429d-17ba-4170-a9bc-ada98b018c58,Ananya Pandey,ananya.pandey@example.com,62000,705,Self-Employed,36
"""
    stream = io.StringIO(sample_csv)
    res = ingest_csv_stream(stream, filename="unit_test.csv", batch_id="batch_unit_test")
    assert res["status"] == "success"
    assert res["processed_rows_inserted"] == 3

    users = query_all("SELECT * FROM users WHERE batch_id = 'batch_unit_test';")
    assert len(users) == 3
