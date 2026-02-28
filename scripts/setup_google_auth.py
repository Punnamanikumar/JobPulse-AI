#!/usr/bin/env python3
"""
One-time Google OAuth2 Setup Script.

Run this ONCE on your local machine to authorize the app and get a refresh token.
The refresh token is then stored in .env and GitHub Secrets.

Usage:
    pip install google-api-python-client google-auth google-auth-oauthlib
    python scripts/setup_google_auth.py
"""

import json
import sys
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
]

CREDENTIALS_FILE = Path(__file__).parent.parent / "credentials.json"


def main():
    print()
    print("═" * 60)
    print("  🔐  Google OAuth2 Setup for JobPulse AI")
    print("═" * 60)
    print()
    print("This script will authorize the app to:")
    print("  📧  Send emails via Gmail API")
    print("  📁  Upload reports to Google Drive")
    print()

    # ── Step 1: Check for credentials.json ────────────────────────────
    if not CREDENTIALS_FILE.exists():
        print("─" * 60)
        print("  STEP 1: Create Google Cloud OAuth2 Credentials")
        print("─" * 60)
        print()
        print("  Follow these steps:")
        print()
        print("  1. Go to: https://console.cloud.google.com")
        print()
        print("  2. Create a new project (or select existing one)")
        print("     • Click the project dropdown at top → 'New Project'")
        print("     • Name it 'JobPulse AI' → Click 'Create'")
        print()
        print("  3. Enable APIs:")
        print("     • Go to: APIs & Services → Library")
        print("     • Search 'Gmail API' → Click → Enable")
        print("     • Search 'Google Drive API' → Click → Enable")
        print()
        print("  4. Configure OAuth Consent Screen:")
        print("     • Go to: APIs & Services → OAuth consent screen")
        print("     • Select 'External' → Create")
        print("     • Fill in App name: 'JobPulse AI'")
        print("     • Add your email as support email")
        print("     • Add your email in developer contact")
        print("     • Click 'Save and Continue' through all steps")
        print("     • On 'Test users' page, add your Gmail address")
        print("     • Click 'Save and Continue' → 'Back to Dashboard'")
        print()
        print("  5. Create Credentials:")
        print("     • Go to: APIs & Services → Credentials")
        print("     • Click '+ CREATE CREDENTIALS' → 'OAuth client ID'")
        print("     • Application type: 'Desktop app'")
        print("     • Name: 'JobPulse AI Desktop'")
        print("     • Click 'Create'")
        print()
        print("  6. Download the credentials:")
        print("     • Click the download icon (⬇️) next to your OAuth client")
        print("     • Save the file as 'credentials.json' in the project root:")
        print(f"       {CREDENTIALS_FILE}")
        print()
        input("  Press Enter after you've saved credentials.json … ")
        print()

    if not CREDENTIALS_FILE.exists():
        print("  ❌  credentials.json not found at:")
        print(f"      {CREDENTIALS_FILE}")
        print()
        print("  Please download it from Google Cloud Console and save it there.")
        sys.exit(1)

    # Validate credentials.json
    try:
        with open(CREDENTIALS_FILE) as f:
            cred_data = json.load(f)
        # Extract client info
        if "installed" in cred_data:
            client_id = cred_data["installed"]["client_id"]
            client_secret = cred_data["installed"]["client_secret"]
        elif "web" in cred_data:
            client_id = cred_data["web"]["client_id"]
            client_secret = cred_data["web"]["client_secret"]
        else:
            print("  ❌  Invalid credentials.json format.")
            sys.exit(1)
        print(f"  ✅  credentials.json loaded")
        print(f"      Client ID: {client_id[:30]}…")
    except Exception as e:
        print(f"  ❌  Error reading credentials.json: {e}")
        sys.exit(1)

    # ── Step 2: Run OAuth2 flow ───────────────────────────────────────
    print()
    print("─" * 60)
    print("  STEP 2: Authorize with your Google Account")
    print("─" * 60)
    print()
    print("  A browser window will open. Log in with your Gmail account")
    print("  and click 'Allow' to grant access.")
    print()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE), SCOPES
        )
        creds = flow.run_local_server(port=8080, prompt="consent")

        print()
        print("  ✅  Authorization successful!")
        print()
    except Exception as e:
        print(f"  ❌  Authorization failed: {e}")
        sys.exit(1)

    # ── Step 3: Display results ───────────────────────────────────────
    print("─" * 60)
    print("  STEP 3: Your Credentials (copy these!)")
    print("─" * 60)
    print()
    print(f"  GOOGLE_CLIENT_ID={client_id}")
    print(f"  GOOGLE_CLIENT_SECRET={client_secret}")
    print(f"  GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print()

    # ── Step 4: Update .env ───────────────────────────────────────────
    env_file = Path(__file__).parent.parent / ".env"
    print("─" * 60)
    print("  STEP 4: Update .env file")
    print("─" * 60)
    print()

    update = input("  Auto-update .env with these credentials? (y/n): ").strip().lower()
    if update in ("y", "yes"):
        env_content = env_file.read_text() if env_file.exists() else ""

        # Remove old GMAIL_APP_PASS if present
        new_lines = []
        for line in env_content.splitlines():
            if line.strip().startswith("GMAIL_APP_PASS="):
                new_lines.append(f"# {line}  # replaced by OAuth2")
            elif line.strip().startswith("GOOGLE_CLIENT_ID="):
                continue  # will be re-added
            elif line.strip().startswith("GOOGLE_CLIENT_SECRET="):
                continue
            elif line.strip().startswith("GOOGLE_REFRESH_TOKEN="):
                continue
            else:
                new_lines.append(line)

        # Add new credentials
        new_lines.append("")
        new_lines.append("# ── Google OAuth2 (Gmail API + Drive) ──")
        new_lines.append(f"GOOGLE_CLIENT_ID={client_id}")
        new_lines.append(f"GOOGLE_CLIENT_SECRET={client_secret}")
        new_lines.append(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")

        env_file.write_text("\n".join(new_lines) + "\n")
        print(f"  ✅  .env updated!")
    else:
        print("  ℹ️  Skipped. Add them manually to .env")

    # ── Step 5: GitHub Secrets reminder ───────────────────────────────
    print()
    print("─" * 60)
    print("  STEP 5: Add to GitHub Secrets")
    print("─" * 60)
    print()
    print("  Go to: Your GitHub repo → Settings → Secrets and variables → Actions")
    print()
    print("  Add these 3 secrets:")
    print(f"    GOOGLE_CLIENT_ID     = {client_id}")
    print(f"    GOOGLE_CLIENT_SECRET = {client_secret}")
    print(f"    GOOGLE_REFRESH_TOKEN = {creds.refresh_token}")
    print()
    print("")
    print()
    print("═" * 60)
    print("  ✅  Setup complete! You're ready to go.")
    print("═" * 60)


if __name__ == "__main__":
    main()
