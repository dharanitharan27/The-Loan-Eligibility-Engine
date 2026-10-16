"""
Complete End-to-End CLI Pipeline Orchestrator.
Executes Discovery (Workflow A), Streaming Ingestion, Multi-stage Matching (Workflow B), and SES Notification (Workflow C).
"""
import os
import sys
import argparse
import json
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.database import init_db, get_active_engine, query_all, query_one
from backend.crawler import run_discovery
from backend.ingest_lambda import ingest_csv_stream
from backend.matcher import execute_matching_pipeline
from backend.email_service import dispatch_all_pending_notifications


def run_full_pipeline(csv_path: str, limit_users: int = 1000, notify_limit: int = 3, test_email: str = "dharanitharan27+testloan@gmail.com"):
    print("\n" + "=" * 70)
    print(">> CLICKPE LOAN ELIGIBILITY ENGINE - END-TO-END AUTOMATION PIPELINE")
    print("=" * 70)

    # Step 0: Database Init
    print("\n[Step 0/4] Initializing Database Schema & Performance Indices...")
    init_db()
    engine = get_active_engine()
    print(f"✓ Database ready. Active engine: {engine.upper()}")

    # Step 1: Workflow A - Loan Product Discovery
    print("\n[Step 1/4] Running Workflow A: Loan Product Discovery (The Web Crawler)...")
    start_wa = time.time()
    disc_res = run_discovery()
    dur_wa = round(time.time() - start_wa, 2)
    print(f"✓ Workflow A Complete ({dur_wa}s): Discovered {disc_res['discovered_count']} loan products.")
    for p in disc_res["products"][:4]:
        print(f"   • {p['bank_name']} - {p['product_name']} | Rate: {p['interest_rate_min']}% | Min Income: ₹{p['min_income']:,.0f} | Min Score: {p['min_credit_score']}")

    # Step 2: Ingestion - Scalable Batch Stream
    print(f"\n[Step 2/4] Ingesting User Data from {csv_path} (Streaming Chunk Pipeline)...")
    if not os.path.exists(csv_path):
        print(f"❌ Error: File not found: {csv_path}")
        return

    start_ingest = time.time()
    with open(csv_path, "r", encoding="utf-8") as f:
        ingest_res = ingest_csv_stream(f, filename=os.path.basename(csv_path))
    dur_ingest = round(time.time() - start_ingest, 2)
    print(f"✓ Ingestion Complete ({dur_ingest}s): {ingest_res['processed_rows_inserted']} rows inserted into '{engine}' database.")
    print(f"✓ Batch ID: {ingest_res['batch_id']}")

    # Step 3: Workflow B - Multi-stage Matching (Optimization Treasure Hunt)
    print("\n[Step 3/4] Running Workflow B: Multi-Stage User-Loan Matching...")
    print("   [Stage 1] Executing indexed relational filter (income, credit score, age, employment)...")
    print("   [Stage 2] Executing algorithmic composite scoring & Top-3 capping...")
    print("   [Stage 3] Synthesizing batched qualitative AI Underwriting Advisory...")

    start_wb = time.time()
    match_res = execute_matching_pipeline(
        batch_id=ingest_res['batch_id'],
        limit_users=limit_users,
        run_llm=True
    )
    dur_wb = round(time.time() - start_wb, 2)
    print(f"✓ Workflow B Complete ({dur_wb}s / {match_res['execution_time_ms']}ms):")
    print(f"   • Users Evaluated: {match_res['total_users']}")
    print(f"   • Theoretical Cartesian Pairs (U × P): {match_res['cartesian_pairs']:,}")
    print(f"   • Stage 1 Surviving Candidates: {match_res['stage1_surviving_pairs']:,}")
    print(f"   • Optimization Sifting Prune Rate: {match_res['pruning_efficiency_percent']}% of pairs pruned before LLM!")
    print(f"   • Final Top-3 Matches Persisted: {match_res['final_matches_persisted']:,}")

    # Step 4: Workflow C - Notification via AWS SES
    print(f"\n[Step 4/4] Running Workflow C: User Notification (Safe Test Inbox Mode)...")
    print(f"   Routing exclusively to test recipient alias: {test_email}")
    start_wc = time.time()
    notify_res = dispatch_all_pending_notifications(limit=notify_limit, test_recipient=test_email)
    dur_wc = round(time.time() - start_wc, 2)
    print(f"✓ Workflow C Complete ({dur_wc}s): {notify_res['users_notified_count']} personalized notification emails processed.")
    for d in notify_res["dispatches"]:
        print(f"   ✉ To: {d['recipient']} | Subject: {d['subject']}")
        print(f"     Preview Archive: {d['archive_preview_file']}")

    print("\n" + "=" * 70)
    print("🏆 PIPELINE EXECUTION SUMMARY & BENCHMARKS")
    print("=" * 70)
    print(f"• Total Process Duration: {round(dur_wa + dur_ingest + dur_wb + dur_wc, 2)}s")
    print(f"• Data Ingestion Rate:    {round(ingest_res['processed_rows_inserted'] / max(0.1, dur_ingest))} rows/sec")
    print(f"• Matching Prune Ratio:   {match_res['pruning_efficiency_percent']}%")
    print(f"• Database Engine:        {engine.upper()}")
    print(f"• SES Test Mode:          Active ({test_email})")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClickPe Loan Engine Pipeline Runner")
    parser.add_argument("--input", default="data/users_sample.csv", help="Path to input users CSV")
    parser.add_argument("--limit", type=int, default=1000, help="Max users to match")
    parser.add_argument("--notify", type=int, default=3, help="Max notification emails to send")
    parser.add_argument("--email", default="dharanitharan27+testloan@gmail.com", help="Test recipient email alias")
    args = parser.parse_args()

    run_full_pipeline(
        csv_path=args.input,
        limit_users=args.limit,
        notify_limit=args.notify,
        test_email=args.email
    )
