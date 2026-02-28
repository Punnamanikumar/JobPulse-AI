"""
Centralized Configuration — single source of truth for all settings.

All configuration is read from environment variables (or .env file).
This replaces scattered os.environ.get() calls across the codebase.

Usage:
    from config import get_config
    cfg = get_config()
    print(cfg.gemini_api_key, cfg.platforms, cfg.user_name)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).parent.parent
RESUME_DIR = PROJECT_ROOT / "resume"


@dataclass
class Config:
    """All application settings in one place."""

    # ── API Keys ──────────────────────────────────────────────────────
    gemini_api_key: str = ""
    apify_token: str = ""

    # ── Platform Toggle ───────────────────────────────────────────────
    # "both" | "linkedin" | "naukri"
    platforms: str = "both"

    # ── AI Settings ───────────────────────────────────────────────────
    ai_analysis: bool = True
    job_count: int = 20

    # ── User Info (optional — for personalizing reports) ──────────────
    user_name: str = ""

    # ── Email Settings ────────────────────────────────────────────────
    gmail_user: str = ""
    recipient_email: str = ""

    # ── Google OAuth2 ─────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""

    # ── Google Drive ──────────────────────────────────────────────────
    drive_folder_id: str = ""

    # ── Resume ────────────────────────────────────────────────────────
    resume_path: str = ""  # auto-detected if empty

    def run_linkedin(self) -> bool:
        return self.platforms in ("both", "linkedin")

    def run_naukri(self) -> bool:
        return self.platforms in ("both", "naukri")


def _resolve_api_keys() -> tuple[str, str]:
    """Resolve Gemini and Apify keys with backward compatibility.

    Priority:
      1. GEMINI_API_KEY / APIFY_TOKEN  (new single-key format)
      2. GEMINI_KEY_1 / APIFY_TOKEN_1  (legacy multi-key format, uses first)
    """
    # Gemini
    gemini = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini:
        gemini = os.environ.get("GEMINI_KEY_1", "").strip()

    # Apify
    apify = os.environ.get("APIFY_TOKEN", "").strip()
    if not apify:
        apify = os.environ.get("APIFY_TOKEN_1", "").strip()

    return gemini, apify


def _detect_resume() -> str:
    """Auto-detect resume file in the resume/ directory.

    Priority order: .pdf > .docx > .doc > .txt > .md
    Returns absolute path string, or empty string if not found.
    """
    if not RESUME_DIR.exists():
        return ""

    priority = [".pdf", ".docx", ".doc", ".txt", ".md"]
    for ext in priority:
        files = list(RESUME_DIR.glob(f"*{ext}"))
        # Skip sample files
        files = [f for f in files if "sample" not in f.name.lower()]
        if files:
            return str(files[0])

    # Fallback: any file in resume/ that's not a sample
    all_files = [f for f in RESUME_DIR.iterdir()
                 if f.is_file() and "sample" not in f.name.lower()]
    if all_files:
        return str(all_files[0])

    return ""


def get_config() -> Config:
    """Load configuration from environment variables."""
    gemini, apify = _resolve_api_keys()

    platforms = os.environ.get("PLATFORMS", "both").strip().lower()
    if platforms not in ("both", "linkedin", "naukri"):
        print(f"⚠️  Invalid PLATFORMS value '{platforms}', defaulting to 'both'")
        platforms = "both"

    ai_val = os.environ.get("AI_ANALYSIS", "true").strip().lower()
    ai_analysis = ai_val in ("true", "1", "yes", "on")

    resume_path = os.environ.get("RESUME_PATH", "").strip()
    if not resume_path:
        resume_path = _detect_resume()

    recipient = os.environ.get("RECIPIENT_EMAIL", "").strip()
    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    if not recipient:
        recipient = gmail_user

    return Config(
        gemini_api_key=gemini,
        apify_token=apify,
        platforms=platforms,
        ai_analysis=ai_analysis,
        job_count=int(os.environ.get("JOB_COUNT", "20")),
        user_name=os.environ.get("USER_NAME", "").strip(),
        gmail_user=gmail_user,
        recipient_email=recipient,
        google_client_id=os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        google_client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
        google_refresh_token=os.environ.get("GOOGLE_REFRESH_TOKEN", "").strip(),
        drive_folder_id=os.environ.get("DRIVE_FOLDER_ID", "").strip(),
        resume_path=resume_path,
    )
