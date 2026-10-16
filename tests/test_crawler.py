import pytest
from backend.database import init_db, query_all
from backend.crawler import crawl_public_sources, save_loan_products, run_discovery

def test_crawler_discovers_products():
    init_db()
    products = crawl_public_sources()
    assert len(products) >= 5, "Crawler should discover at least 5 loan products"
    for p in products:
        assert "product_id" in p
        assert "product_name" in p
        assert "bank_name" in p
        assert p["interest_rate_min"] > 0
        assert p["min_income"] > 0
        assert p["min_credit_score"] >= 600

def test_save_and_persist_products():
    init_db()
    res = run_discovery()
    assert res["status"] == "success"
    assert res["persisted_count"] > 0
    saved = query_all("SELECT * FROM loan_products;")
    assert len(saved) >= res["persisted_count"]
