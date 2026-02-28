#!/usr/bin/env python3
"""
Send a failure alert email when the GitHub Actions workflow crashes.
This script is called with `if: failure()` so it only runs when a step fails.

Usage:
    python scripts/send_failure_alert.py "Step that failed" "Error details..."
"""

import os
import sys
import base64
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

load_dotenv()

TODAY = date.today().isoformat()
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
GMAIL_USER = os.environ.get("GMAIL_USER", "")
RECIPIENT = os.environ.get("RECIPIENT_EMAIL", GMAIL_USER)
RUN_URL = os.environ.get("GITHUB_RUN_URL", "")

# Get failure context from env (set by workflow)
FAILED_STEP = os.environ.get("FAILED_STEP", "Unknown step")


def find_run_log():
    """Find today's run log if it exists."""
    log_file = f"reports/run_log_{TODAY}.txt"
    if os.path.exists(log_file):
        return log_file
    import glob
    logs = sorted(glob.glob("reports/run_log_*.txt"))
    return logs[-1] if logs else None


def send_failure_email():
    """Send a failure notification via Gmail API."""
    if not GMAIL_USER:
        print("⚠️  GMAIL_USER not set, cannot send failure alert.")
        return

    subject = f"🚨 JobPulse Workflow FAILED — {TODAY}"

    html_body = f"""<div style="font-family:'Segoe UI',Helvetica,Arial,sans-serif;max-width:620px;margin:auto;color:#333;">

<div style="background:#dc3545;color:white;padding:16px 20px;border-radius:10px 10px 0 0;">
<h2 style="margin:0;color:white;">🚨 JobPulse Workflow Failed</h2>
<p style="margin:4px 0 0 0;opacity:0.9;">Your daily job report was NOT delivered today.</p>
</div>

<div style="background:#fff5f5;border:1px solid #f5c6cb;border-top:none;padding:16px 20px;border-radius:0 0 10px 10px;">

<table style="width:100%;font-size:14px;">
<tr><td style="padding:6px 0;color:#666;"><strong>Date:</strong></td><td>{TODAY}</td></tr>
<tr><td style="padding:6px 0;color:#666;"><strong>Time:</strong></td><td>{NOW} UTC</td></tr>
<tr><td style="padding:6px 0;color:#666;"><strong>Failed at:</strong></td><td style="color:#dc3545;"><strong>{FAILED_STEP}</strong></td></tr>
</table>

<p style="margin-top:16px;font-size:14px;">
<strong>What happened:</strong> The workflow crashed before the report email could be sent.
The run log (if available) is attached below.
</p>

{"<p><a href='" + RUN_URL + "' style='background:#dc3545;color:white;padding:8px 20px;border-radius:6px;text-decoration:none;font-weight:600;display:inline-block;margin-top:8px;'>🔍 View Failed Run on GitHub</a></p>" if RUN_URL else ""}

<p style="font-size:13px;color:#888;margin-top:16px;">
<strong>Common fixes:</strong><br>
• Check Apify tokens — may be expired or out of credits<br>
• Check Gemini API keys — may be rate limited<br>
• Check GitHub Actions logs for the exact error<br>
• Re-run the workflow manually after fixing
</p>

</div>
</div>"""

    # Build MIME message
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"Job Tracker Bot <{GMAIL_USER}>"
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    # Attach run log if it exists
    run_log = find_run_log()
    if run_log:
        try:
            with open(run_log, "rb") as f:
                log_part = MIMEBase("application", "octet-stream")
                log_part.set_payload(f.read())
            encoders.encode_base64(log_part)
            log_fname = os.path.basename(run_log)
            log_part.add_header("Content-Disposition", f'attachment; filename="{log_fname}"')
            msg.attach(log_part)
            print(f"   📎 Attached run log: {log_fname}")
        except Exception as e:
            print(f"   ⚠️  Could not attach run log: {e}")

    # Send via Gmail API
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from google_auth import get_credentials
        from googleapiclient.discovery import build

        creds = get_credentials()
        service = build("gmail", "v1", credentials=creds)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"   🚨 Failure alert sent to {RECIPIENT}")
    except Exception as e:
        print(f"   ❌ Could not send failure alert: {e}")


if __name__ == "__main__":
    send_failure_email()
