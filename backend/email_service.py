"""
Workflow C: User Notification Service
Constructs personalized, responsive HTML emails with matched loan products and AI advice.
Dispatches via AWS SES (or mock/local preview) strictly to designated test inboxes.
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from backend.database import get_connection, get_active_engine, query_all, execute_stmt

logger = logging.getLogger("email_service")
logging.basicConfig(level=logging.INFO)

SES_SENDER_EMAIL = os.getenv("SES_SENDER_EMAIL", "loans@clickpe.verify")
TEST_RECIPIENT_EMAIL = os.getenv("TEST_RECIPIENT_EMAIL", "dharanitharan27+testloan@gmail.com")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")


def build_email_html(user: Dict[str, Any], matches: List[Dict[str, Any]], test_target: str) -> str:
    """Builds an email template for the user's matched loan products."""
    user_name = user.get("name", "Valued Applicant")
    credit_score = user.get("credit_score", "N/A")
    income = float(user.get("monthly_income", 0))
    emp = user.get("employment_status", "Salaried")

    # Generate product cards HTML
    product_cards_html = ""
    for idx, m in enumerate(matches, 1):
        reasons_list = m.get("match_reasons", [])
        if isinstance(reasons_list, str):
            try:
                reasons_list = json.loads(reasons_list)
            except Exception:
                reasons_list = [reasons_list]

        reasons_html = "".join([f"<li style='margin-bottom: 4px; color: #475569;'>✓ {r}</li>" for r in reasons_list[:3]])

        product_cards_html += f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.04);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                <div>
                    <span style="background: #eff6ff; color: #2563eb; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 6px; text-transform: uppercase; letter-spacing: 0.5px;">{m.get('bank_name', 'Bank')}</span>
                    <h3 style="margin: 8px 0 4px 0; color: #0f172a; font-size: 18px; font-weight: 700;">{m.get('product_name', 'Personal Loan')}</h3>
                </div>
                <div style="text-align: right; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 6px 12px;">
                    <div style="font-size: 11px; color: #047857; font-weight: 600;">Match Score</div>
                    <div style="font-size: 18px; color: #065f46; font-weight: 800;">{float(m.get('eligibility_score', 90)):.1f}%</div>
                </div>
            </div>
            
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 12px;">
                <tr>
                    <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Starting Rate:</td>
                    <td style="padding: 6px 0; font-weight: 700; color: #0f172a; font-size: 14px; text-align: right;">{m.get('interest_rate_min', '10.5')}% p.a.</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Max Loan Amount:</td>
                    <td style="padding: 6px 0; font-weight: 700; color: #0f172a; font-size: 14px; text-align: right;">₹{float(m.get('max_loan_amount', 2500000)):,.0f}</td>
                </tr>
                <tr>
                    <td style="padding: 6px 0; color: #64748b; font-size: 13px;">Processing Fee:</td>
                    <td style="padding: 6px 0; font-weight: 600; color: #334155; font-size: 13px; text-align: right;">{m.get('processing_fee', '1.5%')}</td>
                </tr>
            </table>

            <div style="background: #f8fafc; border-radius: 8px; padding: 10px 12px; margin-top: 10px;">
                <div style="font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 4px;">Eligibility Factors:</div>
                <ul style="margin: 0; padding-left: 18px; font-size: 12px;">
                    {reasons_html}
                </ul>
            </div>
        </div>
        """

    ai_advice = matches[0].get("ai_recommendation", "You qualify for prime borrowing privileges with instant digital verification.")

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Curated Personal Loan Matches</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f1f5f9; margin: 0; padding: 24px 12px; color: #1e293b;">
    <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
        
        <!-- Header Banner -->
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 32px 28px; text-align: left; color: #ffffff;">
            <div style="display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; margin-bottom: 12px; letter-spacing: 0.5px;">
                CLICKPE ELIGIBILITY ENGINE
            </div>
            <h1 style="margin: 0 0 8px 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">Congratulations, {user_name}!</h1>
            <p style="margin: 0; font-size: 15px; opacity: 0.9; line-height: 1.5;">We found <strong style="color: #fef08a;">{len(matches)} personal loan products</strong> tailored to your financial profile.</p>
        </div>

        <!-- Testing Alias Notice Banner -->
        <div style="background: #fffbeb; border-bottom: 1px solid #fef3c7; padding: 10px 24px; font-size: 12px; color: #92400e; display: flex; align-items: center;">
            <span style="font-weight: 700; margin-right: 6px;">[TEST INBOX NOTICE]</span>
            Target Alias: <code>{test_target}</code> | Original User: {user.get('email', 'N/A')}
        </div>

        <!-- Borrower Health Snapshot -->
        <div style="padding: 24px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;">
            <div style="font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">Borrower Profile Verified</div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; text-align: center;">
                <div style="background: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid #e2e8f0;">
                    <div style="font-size: 11px; color: #64748b;">Credit Score</div>
                    <div style="font-size: 18px; font-weight: 800; color: #2563eb;">{credit_score}</div>
                </div>
                <div style="background: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid #e2e8f0;">
                    <div style="font-size: 11px; color: #64748b;">Monthly Income</div>
                    <div style="font-size: 16px; font-weight: 700; color: #0f172a;">₹{income:,.0f}</div>
                </div>
                <div style="background: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid #e2e8f0;">
                    <div style="font-size: 11px; color: #64748b;">Employment</div>
                    <div style="font-size: 14px; font-weight: 700; color: #0f172a;">{emp}</div>
                </div>
            </div>
        </div>

        <!-- AI Advisor Insights -->
        <div style="padding: 20px 24px; background: #faf5ff; border-left: 4px solid #a855f7; margin: 20px 24px; border-radius: 0 8px 8px 0;">
            <div style="font-size: 13px; font-weight: 700; color: #7e22ce; margin-bottom: 4px; display: flex; align-items: center;">
                🤖 AI Credit Underwriting Advisory
            </div>
            <p style="margin: 0; font-size: 13.5px; line-height: 1.6; color: #4c1d95;">
                {ai_advice}
            </p>
        </div>

        <!-- Product Matches List -->
        <div style="padding: 0 24px;">
            <h2 style="font-size: 17px; font-weight: 700; color: #0f172a; margin: 16px 0 16px 0;">Top Pre-Approved Offers For You:</h2>
            {product_cards_html}
        </div>

        <!-- Action Button -->
        <div style="padding: 20px 24px 32px 24px; text-align: center;">
            <a href="http://localhost:8000" style="display: inline-block; background: #2563eb; color: #ffffff; padding: 14px 32px; border-radius: 8px; font-weight: 700; text-decoration: none; font-size: 15px; box-shadow: 0 4px 12px rgba(37,99,235,0.3);">
                Claim Pre-Approved Offers
            </a>
            <div style="font-size: 11px; color: #94a3b8; margin-top: 14px;">
                No obligation. Rates subject to bank verification of KYC & income documentation.
            </div>
        </div>

        <!-- Footer -->
        <div style="background: #0f172a; padding: 20px 24px; text-align: center; color: #94a3b8; font-size: 11px; border-top: 1px solid #334155;">
            ClickPe Automated Loan Eligibility Engine &bull; Self-Hosted n8n Orchestrated Pipeline<br>
            Sent via Amazon Simple Email Service (SES) Sandbox Testing Mode
        </div>
    </div>
</body>
</html>
"""


def send_notification_email(user: Dict[str, Any], matches: List[Dict[str, Any]], custom_recipient: Optional[str] = None) -> Dict[str, Any]:
    """
    Sends notification email to safe test inbox using AWS SES (or saves HTML artifact).
    Prevents sending to fictitious addresses from sample CSV.
    """
    recipient = custom_recipient or TEST_RECIPIENT_EMAIL
    user_name = user.get("name", "Applicant")
    subject = f"Pre-Approved Loan Offers for {user_name} (Top {len(matches)} Matches)"
    html_content = build_email_html(user, matches, test_target=recipient)

    # Always archive email locally for demonstration preview and verification
    os.makedirs(os.path.join("data", "sent_emails"), exist_ok=True)
    clean_user_id = str(user.get("user_id", "test"))[:8]
    archive_path = os.path.join("data", "sent_emails", f"email_{clean_user_id}_{int(datetime.now(timezone.utc).timestamp())}.html")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    message_id = f"mock-msg-{datetime.now(timezone.utc).timestamp()}"
    ses_success = False

    # Try AWS SES if configured
    try:
        import boto3
        ses = boto3.client("ses", region_name=AWS_REGION)
        resp = ses.send_email(
            Source=SES_SENDER_EMAIL,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html_content, "Charset": "UTF-8"}}
            }
        )
        message_id = resp.get("MessageId", message_id)
        ses_success = True
        logger.info(f"SES Email dispatched to {recipient} with MessageId {message_id}")
    except Exception as e:
        logger.info(f"SES not configured in cloud, saved rendered email to {archive_path}: {e}")

    # Mark matches as notified
    conn = get_connection()
    cursor = conn.cursor()
    engine = get_active_engine()
    uid = str(user["user_id"])
    try:
        if engine == "postgres":
            cursor.execute("UPDATE matches SET notified = TRUE, notified_at = CURRENT_TIMESTAMP WHERE user_id = %s;", (uid,))
        else:
            cursor.execute("UPDATE matches SET notified = 1, notified_at = CURRENT_TIMESTAMP WHERE user_id = ?;", (uid,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return {
        "status": "success",
        "user_id": uid,
        "user_name": user_name,
        "recipient": recipient,
        "subject": subject,
        "ses_dispatched": ses_success,
        "message_id": message_id,
        "archive_preview_file": archive_path
    }


def dispatch_all_pending_notifications(limit: int = 5, test_recipient: Optional[str] = None) -> Dict[str, Any]:
    """Finds users with unnotified matches and dispatches notification emails."""
    # Find distinct users with matches
    engine = get_active_engine()
    if engine == "postgres":
        sql = """
        SELECT DISTINCT u.user_id, u.name, u.email, u.monthly_income, u.credit_score, u.employment_status, u.age
        FROM users u
        JOIN matches m ON u.user_id = m.user_id
        WHERE m.notified = FALSE OR m.notified IS NULL
        LIMIT %s;
        """
        users = query_all(sql, (limit,))
    else:
        sql = """
        SELECT DISTINCT u.user_id, u.name, u.email, u.monthly_income, u.credit_score, u.employment_status, u.age
        FROM users u
        JOIN matches m ON u.user_id = m.user_id
        WHERE m.notified = 0 OR m.notified IS NULL
        LIMIT ?;
        """
        users = query_all(sql, (limit,))

    dispatched = []
    for u in users:
        uid = str(u["user_id"])
        if engine == "postgres":
            match_sql = """
            SELECT m.eligibility_score, m.match_reasons, m.ai_recommendation,
                   p.product_name, p.bank_name, p.interest_rate_min, p.max_loan_amount, p.processing_fee
            FROM matches m
            JOIN loan_products p ON m.product_id = p.product_id
            WHERE m.user_id = %s
            ORDER BY m.eligibility_score DESC
            LIMIT 3;
            """
            matches = query_all(match_sql, (uid,))
        else:
            match_sql = """
            SELECT m.eligibility_score, m.match_reasons, m.ai_recommendation,
                   p.product_name, p.bank_name, p.interest_rate_min, p.max_loan_amount, p.processing_fee
            FROM matches m
            JOIN loan_products p ON m.product_id = p.product_id
            WHERE m.user_id = ?
            ORDER BY m.eligibility_score DESC
            LIMIT 3;
            """
            matches = query_all(match_sql, (uid,))

        if matches:
            res = send_notification_email(u, matches, custom_recipient=test_recipient)
            dispatched.append(res)

    return {
        "status": "success",
        "users_notified_count": len(dispatched),
        "dispatches": dispatched
    }


if __name__ == "__main__":
    res = dispatch_all_pending_notifications(limit=2)
    print("Notification run:", json.dumps(res, indent=2))
