from __future__ import annotations
"""
Gemini API Key Manager — simplified single-key mode with rate limiting.

Reads GEMINI_API_KEY from environment (or falls back to GEMINI_KEY_1 for
backward compatibility).

Enforces Gemini free-tier rate limits (15 RPM for Flash-Lite).
Integrates with RunLogger for end-to-end tracking.

Usage:
    from gemini_token import GeminiKeyManager
    mgr = GeminiKeyManager()
    response = mgr.generate(prompt)  # auto-handles rate limits
"""

import os
import time
import base64
from datetime import date
from email.mime.text import MIMEText
from run_logger import get_logger

# Gemini free-tier limits per key (Flash-Lite)
RPM_LIMIT = 14           # stay 1 below the 15 RPM hard cap
COOLDOWN_SECONDS = 62    # wait this long when key hits its RPM window
MAX_RETRIES = 5          # max retries per request


# ── Load Gemini key from env ──────────────────────────────────────────
def _load_key() -> tuple[str, str]:
    """Load a single Gemini API key.

    Priority:
      1. GEMINI_API_KEY (recommended)
      2. GEMINI_KEY_1 (backward compatibility)
    """
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return ("GEMINI_API_KEY", key)

    # Backward compat: check GEMINI_KEY_1
    key = os.environ.get("GEMINI_KEY_1", "").strip()
    if key:
        return ("GEMINI_KEY_1", key)

    return ("", "")


def _mask(key: str) -> str:
    """Mask a key for safe display: AIzaSy…xY9z"""
    if len(key) > 10:
        return key[:6] + "…" + key[-4:]
    return key[:3] + "…****"


class GeminiKeyManager:
    """Single Gemini API key manager with rate limiting."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        key_name, key_val = _load_key()
        if not key_val:
            raise RuntimeError(
                "No Gemini API key found!\n"
                "Set GEMINI_API_KEY in your .env file.\n"
                "Get a free key at: https://aistudio.google.com/apikey"
            )

        self._key_name = key_name
        self._key_val = key_val
        self._model_name = model_name
        self._request_times: list[float] = []
        self._is_dead = False
        self._logger = get_logger()

        self._logger.log_config(
            keys_loaded=1,
            key_names=[key_name],
            model=model_name,
            rpm_limit=RPM_LIMIT,
        )

    # ── Rate limiting ─────────────────────────────────────────────────
    def _wait_for_rate_limit(self):
        """If the key has hit RPM_LIMIT in the last 60s, sleep until a slot opens."""
        now = time.time()
        # Prune old timestamps (older than 60s)
        self._request_times = [t for t in self._request_times if now - t < 60]

        if len(self._request_times) >= RPM_LIMIT:
            oldest = self._request_times[0]
            wait = 60 - (now - oldest) + 1  # +1s safety margin
            if wait > 0:
                self._logger.log(f"   ⏳  {self._key_name} at RPM limit, waiting {wait:.0f}s …")
                time.sleep(wait)
                # Re-prune after sleeping
                now = time.time()
                self._request_times = [t for t in self._request_times if now - t < 60]

    def _record_request(self):
        """Record a request timestamp for rate tracking."""
        self._request_times.append(time.time())

    def get_current_key_name(self) -> str:
        """Get the name of the current key (for external logging)."""
        return self._key_name

    # ── Public API ────────────────────────────────────────────────────
    def generate(self, prompt: str, retries: int = 0) -> str | None:
        """Send a prompt to Gemini, handling rate limits.

        Returns the response text, or None if all retries exhausted.
        """
        if retries >= MAX_RETRIES:
            self._logger.log("   ❌  Max retries reached.")
            return None

        if self._is_dead:
            return None

        # Rate limit check
        self._wait_for_rate_limit()

        try:
            from google import genai

            client = genai.Client(api_key=self._key_val)

            self._record_request()
            self._logger.log_key_event(self._key_name, "request")

            response = client.models.generate_content(
                model=self._model_name,
                contents=prompt,
            )

            self._logger.log_key_event(self._key_name, "success")
            return response.text

        except Exception as e:
            err_str = str(e).lower()

            # Rate limit (429) — wait and retry
            if "429" in str(e) or "resource_exhausted" in err_str or "quota" in err_str:
                self._logger.log_key_event(self._key_name, "rate_limited", str(e)[:100])
                self._logger.log(f"   ⏳  Rate limited. Waiting {COOLDOWN_SECONDS}s …")
                time.sleep(COOLDOWN_SECONDS)
                return self.generate(prompt, retries + 1)

            # Auth error — mark key as dead
            if "401" in str(e) or "403" in str(e) or "invalid" in err_str or "api_key" in err_str:
                self._logger.log_key_event(self._key_name, "failed", str(e)[:150])
                self._is_dead = True
                self._send_failed_alert(str(e)[:200])
                return None

            # Unknown error — retry
            self._logger.log(f"   ⚠️  {self._key_name} error: {e}")
            self._logger.log_key_event(self._key_name, "rate_limited", f"Unknown: {str(e)[:100]}")
            return self.generate(prompt, retries + 1)

    def get_alive_count(self) -> int:
        return 0 if self._is_dead else 1

    # Keep this for compatibility with ai_analyzer.py
    @property
    def _keys(self):
        return [(self._key_name, self._key_val)]

    # ── Alert email ───────────────────────────────────────────────────
    def _send_failed_alert(self, error: str):
        today = date.today().isoformat()
        body = f"""🚨 Gemini API Key Failed!

Date:      {today}
Key:       {self._key_name}: {_mask(self._key_val)}
Error:     {error}

AI analysis could NOT run. Falling back to keyword-based scoring.

Action needed:
  1. Check your key at https://aistudio.google.com/apikey
  2. Regenerate or replace the key in .env / GitHub Secrets.
"""
        self._send_alert_email(
            f"🚨 Gemini Key Failed — AI Analysis Skipped | {today}",
            body,
        )

    def _send_alert_email(self, subject: str, body: str):
        gmail_user = os.environ.get("GMAIL_USER", "")
        recipient = os.environ.get("RECIPIENT_EMAIL", "")

        if not all([gmail_user, recipient]):
            self._logger.log("   ⚠️  Cannot send Gemini alert — email credentials not configured.")
            return
        try:
            from google_auth import get_credentials
            from googleapiclient.discovery import build

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = f"Job Tracker Bot <{gmail_user}>"
            msg["To"] = recipient

            creds = get_credentials()
            service = build("gmail", "v1", credentials=creds)
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            self._logger.log(f"   📧  Gemini alert sent to {recipient}")
        except Exception as e:
            self._logger.log(f"   ⚠️  Failed to send Gemini alert: {e}")
