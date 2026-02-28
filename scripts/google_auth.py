"""
Google Auth Helper — shared OAuth2 credentials for Gmail API + Drive API.

Builds credentials from environment variables:
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  GOOGLE_REFRESH_TOKEN

Usage:
    from google_auth import get_credentials
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)
"""

import os
from google.oauth2.credentials import Credentials

# Scopes required for Gmail sending + Drive file upload
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
]

TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_credentials() -> Credentials:
    """Build OAuth2 credentials from environment variables."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        missing = []
        if not client_id:
            missing.append("GOOGLE_CLIENT_ID")
        if not client_secret:
            missing.append("GOOGLE_CLIENT_SECRET")
        if not refresh_token:
            missing.append("GOOGLE_REFRESH_TOKEN")
        raise RuntimeError(
            f"Missing Google OAuth2 env vars: {', '.join(missing)}\n"
            "Run 'python scripts/setup_google_auth.py' to set up credentials."
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    return creds
