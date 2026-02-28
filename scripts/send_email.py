#!/usr/bin/env python3
"""
Send Email — Daily job report via Gmail API with Drive uploads.

Finds today's LinkedIn + Naukri .xlsx reports, uploads them to Google Drive,
and sends an HTML email with match summaries + Drive links via Gmail API.
Logs all Drive/email events to the daily run log.

Usage:
    python scripts/send_email.py
"""

import os
import sys
import glob
import base64
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from dotenv import load_dotenv

load_dotenv()

# ── Init logger for this section ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from run_logger import new_logger
logger = new_logger(section="Email & Drive Upload")

TODAY = date.today().isoformat()
GMAIL_USER = os.environ.get("GMAIL_USER", "")
RECIPIENT  = os.environ.get("RECIPIENT_EMAIL", GMAIL_USER)

logger.log(f"  Sender:    {GMAIL_USER}")
logger.log(f"  Recipient: {RECIPIENT}")


# ═════════════════════════════════════════════════════════════════════
# FIND REPORTS & LOGS
# ═════════════════════════════════════════════════════════════════════
def find_reports():
    """Find today's LinkedIn and Naukri .xlsx reports."""
    reports = []

    # LinkedIn
    li_files = glob.glob(f"reports/LinkedIn_India_Jobs_{TODAY}.xlsx")
    if not li_files:
        li_files = sorted(glob.glob("reports/LinkedIn_India_Jobs_*.xlsx"))
    if li_files:
        reports.append(("LinkedIn", li_files[-1]))
        logger.log(f"  📎 Found LinkedIn report: {li_files[-1]}")

    # Naukri
    nk_files = glob.glob(f"reports/Naukri_India_Jobs_{TODAY}.xlsx")
    if not nk_files:
        nk_files = sorted(glob.glob("reports/Naukri_India_Jobs_*.xlsx"))
    if nk_files:
        reports.append(("Naukri", nk_files[-1]))
        logger.log(f"  📎 Found Naukri report: {nk_files[-1]}")

    if not reports:
        logger.log_error("No report files found")
    return reports


def find_run_log():
    """Find today's run log file."""
    log_file = f"reports/run_log_{TODAY}.txt"
    if os.path.exists(log_file):
        logger.log(f"  📎 Found run log: {log_file}")
        return log_file
    logs = sorted(glob.glob("reports/run_log_*.txt"))
    if logs:
        logger.log(f"  📎 Found run log (fallback): {logs[-1]}")
        return logs[-1]
    logger.log(f"  ℹ️  No run log found (will be created)")
    return None


def read_summary(path, fallback_label):
    """Read a summary text file, or return a fallback."""
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    return f"⚠️ {fallback_label} summary not available."


# ═════════════════════════════════════════════════════════════════════
# BUILD EMAIL
# ═════════════════════════════════════════════════════════════════════
reports = find_reports()
if not reports:
    logger.save()
    sys.exit(1)

# Read summaries
li_summary = read_summary("reports/email_summary.txt", "LinkedIn")
nk_summary = read_summary("reports/naukri_email_summary.txt", "Naukri")

# ── Save logger FIRST so run log exists for Drive upload ──────────────
logger.log(f"")
logger.log(f"── Saving run log before Drive upload ─────────────────")
log_path = logger.save()

# ── Upload to Google Drive ────────────────────────────────────────────
drive_links = {}
try:
    from drive_uploader import upload_reports
    drive_links = upload_reports()
    for name, link in drive_links.items():
        if name != "_folder":
            logger.log_drive_event(f"Uploaded {name}", link)
    if "_folder" in drive_links:
        logger.log_drive_event(f"Folder link", drive_links["_folder"])
except Exception as e:
    logger.log_error(f"Drive upload failed: {e}")

# Build Drive links section for email
drive_section = ""
if drive_links:
    folder_link = drive_links.get("_folder", "")
    if folder_link:
        drive_section = f"""
<tr><td colspan="2" style="padding:12px 0;">
  <a href="{folder_link}" style="background:linear-gradient(135deg,#4285f4,#34a853);color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;">
    📂 View All Reports in Google Drive
  </a>
</td></tr>"""

# ── Attachments count for email body ──────────────────────────────────
attachment_names = [os.path.basename(p) for _, p in reports]
run_log = find_run_log()
if run_log:
    attachment_names.append(os.path.basename(run_log))

# ── Compose HTML email ────────────────────────────────────────────────
# Dynamic user name from config
sys.path.insert(0, os.path.dirname(__file__))
from config import get_config
_cfg = get_config()
_user_label = _cfg.user_name if _cfg.user_name else "Your Profile"

subject = f"🇮🇳 LinkedIn + Naukri India Job Report — {TODAY}"

html_body = f"""<div style="font-family:'Segoe UI',Helvetica,Arial,sans-serif;max-width:620px;margin:auto;color:#333;">

<h2 style="color:#1a73e8;">🇮🇳 LinkedIn + Naukri India — Daily Job Match Report</h2>
<p style="color:#666;">{TODAY} · Automated by GitHub Actions</p>
<p style="background:#f0f4ff;padding:10px 14px;border-radius:8px;font-size:14px;">
<strong>{_user_label}</strong> · AI-Powered Job Matching · Automated Daily Reports
</p>

<table cellpadding="0" cellspacing="0" style="width:100%;">

<tr><td colspan="2"><h3 style="color:#0b66c3;">🔗 LinkedIn</h3></td></tr>
<tr><td colspan="2" style="white-space:pre-line;font-size:14px;line-height:1.7;">{li_summary}</td></tr>

<tr><td colspan="2"><h3 style="color:#e65100;">📋 Naukri</h3></td></tr>
<tr><td colspan="2" style="white-space:pre-line;font-size:14px;line-height:1.7;">{nk_summary}</td></tr>

{drive_section}

</table>

"""

# ── Add warnings section if any ───────────────────────────────────────
try:
    from apify_token import get_warnings
    warnings_text = get_warnings()
    if warnings_text:
        html_body += f"""<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:12px 16px;margin:12px 0;">
<strong style="color:#856404;">⚠️ Apify Token Warnings</strong>
<pre style="font-size:13px;color:#856404;margin:8px 0 0 0;white-space:pre-wrap;">{warnings_text}</pre>
</div>
"""
        logger.log(f"  ⚠️  Included Apify warnings in email")
        # Clean up warnings file after including
        try:
            os.remove("reports/apify_warnings.txt")
        except Exception:
            pass
except Exception:
    pass

html_body += f"""
<p style="font-size:13px;color:#888;margin-top:20px;">
📎 <strong>Attachments ({len(attachment_names)}):</strong><br>
{"<br>".join(attachment_names)}<br>
Contains matched jobs with Match Score, Interview Probability, Key Skills, and direct job links.
</p>

<p style="font-size:12px;color:#aaa;border-top:1px solid #eee;padding-top:10px;margin-top:20px;">
🏷️ Score Legend: &nbsp;🟢 High ≥65% &nbsp;🟡 Medium 48–64% &nbsp;🔴 Low &lt;48%<br>
Automated · GitHub Actions · Apify · LinkedIn + Naukri Scrapers · Runs daily at 07:30 IST
</p>

</div>"""

# ── Build MIME message ────────────────────────────────────────────────
msg = MIMEMultipart()
msg["Subject"] = subject
msg["From"]    = f"Job Tracker Bot <{GMAIL_USER}>"
msg["To"]      = RECIPIENT
msg.attach(MIMEText(html_body, "html"))

# ── Attach all .xlsx files ────────────────────────────────────────────
for platform, xlsx_path in reports:
    with open(xlsx_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    fname = os.path.basename(xlsx_path)
    part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
    msg.attach(part)
    logger.log(f"  📎 Attached: {fname}")

# ── Attach run log ────────────────────────────────────────────────────
if run_log:
    with open(run_log, "rb") as f:
        log_part = MIMEBase("application", "octet-stream")
        log_part.set_payload(f.read())
    encoders.encode_base64(log_part)
    log_fname = os.path.basename(run_log)
    log_part.add_header("Content-Disposition", f'attachment; filename="{log_fname}"')
    msg.attach(log_part)
    logger.log(f"  📎 Attached: {log_fname}")


# ═════════════════════════════════════════════════════════════════════
# SEND — try Gmail API first, fall back to SMTP
# ═════════════════════════════════════════════════════════════════════
def send_via_gmail_api(message: MIMEMultipart) -> bool:
    """Send email using Gmail API (OAuth2). Returns True on success."""
    try:
        from google_auth import get_credentials
        from googleapiclient.discovery import build

        creds = get_credentials()
        service = build("gmail", "v1", credentials=creds)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        body = {"raw": raw}

        service.users().messages().send(userId="me", body=body).execute()
        logger.log_email_event("Sent via Gmail API", f"to {RECIPIENT}")
        return True
    except Exception as e:
        logger.log_error(f"Gmail API failed: {e}")
        return False


# ── Send email ────────────────────────────────────────────────────────
logger.log(f"")
logger.log(f"── Sending email ──────────────────────────────────────")

if not send_via_gmail_api(msg):
    logger.log_error("Email send failed!")
    logger.save()
    sys.exit(1)

logger.log(f"")
logger.log(f"🎉  Daily job report delivered!")

# Save final log (append email events to the same log file)
logger.save()

