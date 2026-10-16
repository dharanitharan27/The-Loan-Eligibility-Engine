"""
AI Advisory & Qualitative Evaluation Module (Stage 3 of Optimization Pipeline)
Uses Gemini LLM API (with resilient heuristic fallback) to generate personalized qualitative loan advice.
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("llm_advisor")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def generate_qualitative_advice_batch(
    user_data: Dict[str, Any],
    top_products: List[Dict[str, Any]]
) -> str:
    """
    Synthesizes qualitative financial recommendation for a user and their top matched products.
    Batches the decision to reduce LLM calls from O(U * P) to at most O(U) or O(Batches).
    """
    if not top_products:
        return "No eligible loan products found matching your current financial criteria."

    product_names = [p["product_name"] for p in top_products]
    best_rate = min(float(p["interest_rate_min"]) for p in top_products)
    user_income = float(user_data["monthly_income"])
    user_score = int(user_data["credit_score"])
    emp_status = user_data["employment_status"]

    # 1. Try Gemini API if key is available
    if GEMINI_API_KEY and GEMINI_API_KEY != "your-gemini-api-key-here":
        try:
            import requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            prompt = f"""
You are a senior credit underwriting advisor at a top fintech.
Review this borrower profile:
- Monthly Income: ₹{user_income:,.0f}
- Credit Score: {user_score}
- Employment: {emp_status}
- Age: {user_data.get('age', 30)}

Shortlisted loan products:
{json.dumps([{ 'name': p['product_name'], 'bank': p['bank_name'], 'min_rate': p['interest_rate_min'], 'max_amount': p['max_loan_amount']} for p in top_products], indent=2)}

Generate a 2-3 sentence personalized loan eligibility assessment explaining:
1. Why they qualify and which loan offers the best terms.
2. A key financial tip (e.g., tenure recommendation or negotiation leverage).
Keep it encouraging, professional, and clear.
"""
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 200}
            }
            res = requests.post(url, json=payload, timeout=8)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text
        except Exception as e:
            logger.warning(f"Gemini API call failed, falling back to expert heuristic synthesis: {e}")

    # 2. High-Precision Expert Heuristic Synthesis (Zero-cost, instant, 100% deterministic)
    if user_score >= 750:
        score_sentiment = f"With an exceptional credit score of {user_score}, you are in the top tier of borrowers."
        rate_tip = f"You hold strong leverage to negotiate interest rates starting as low as {best_rate:.2f}% p.a."
    elif user_score >= 700:
        score_sentiment = f"Your healthy credit score of {user_score} qualifies you for prime personal loan rates."
        rate_tip = f"We recommend opting for a 36 to 48-month tenure to maintain optimal Debt-to-Income (DTI) below 40%."
    else:
        score_sentiment = f"Your credit profile ({user_score}) meets the eligibility threshold for select competitive lenders."
        rate_tip = f"Consistent on-time repayments will further elevate your score for balance transfer opportunities."

    if emp_status == "Salaried":
        emp_tip = f"Your steady monthly salaried income of ₹{user_income:,.0f} unlocks instant digital verification."
    else:
        emp_tip = f"Your {emp_status} profile qualifies for tailored business term solutions with flexible drawdown limits."

    best_product = top_products[0]["product_name"]
    return f"{score_sentiment} {emp_tip} {best_product} is currently your highest-value match. {rate_tip}"
