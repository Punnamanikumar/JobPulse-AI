"""
Apify Token Manager — simplified single-token mode.

Reads APIFY_TOKEN from environment (or falls back to APIFY_TOKEN_1 for
backward compatibility).

Usage:
    from apify_token import get_apify_token, is_auth_error
    token = get_apify_token()
    resp = requests.post(..., params={"token": token})
"""

import os
import requests
from datetime import date


# ── Load token from env ───────────────────────────────────────────────
def _load_token() -> tuple[str, str]:
    """Load a single Apify token.

    Priority:
      1. APIFY_TOKEN (recommended)
      2. APIFY_TOKEN_1 (backward compatibility)
    """
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if token:
        return ("APIFY_TOKEN", token)

    token = os.environ.get("APIFY_TOKEN_1", "").strip()
    if token:
        return ("APIFY_TOKEN_1", token)

    return ("", "")


_TOKEN_NAME, _TOKEN_VAL = _load_token()
_has_failed = False


def _mask(token: str) -> str:
    """Mask a token for safe display: apify_api_Oo8m…eA32"""
    if len(token) > 14:
        return token[:14] + "…" + token[-4:]
    return token[:4] + "…" + "****"


def get_apify_token() -> str:
    """Return the configured Apify token."""
    if not _TOKEN_VAL:
        raise RuntimeError(
            "No Apify token found!\n"
            "Set APIFY_TOKEN in your .env file.\n"
            "Get a token at: https://console.apify.com/account/integrations"
        )
    return _TOKEN_VAL


def get_current_token_name() -> str:
    """Return name of the current token (e.g. APIFY_TOKEN)."""
    return _TOKEN_NAME if _TOKEN_NAME else "NONE"


def try_next_token(script_name: str = "") -> str:
    """Legacy compatibility — no more failover with single token.
    Returns empty string to signal no more tokens available."""
    global _has_failed
    _has_failed = True
    print(f"   ❌  {_TOKEN_NAME} failed.")
    _save_warning(script_name)
    return ""


def is_auth_error(status_code: int) -> bool:
    """Check if an HTTP status code indicates a token/auth failure."""
    return status_code in (401, 402, 403)


def get_warnings() -> str:
    """Return any saved Apify warnings (for inclusion in the daily email)."""
    path = "reports/apify_warnings.txt"
    if os.path.exists(path):
        return open(path, "r").read().strip()
    return ""


# ── Warning file + run log ────────────────────────────────────────────
def _save_warning(script_name: str):
    """Save a warning to file and run log (picked up by send_email.py)."""
    os.makedirs("reports", exist_ok=True)
    today = date.today().isoformat()

    warning = f"""🚨 Apify Token Failed!
Script:    {script_name}
Date:      {today}

Token failed: ❌ {_TOKEN_NAME}: {_mask(_TOKEN_VAL)}

The job scraper could NOT run today.
Action: Check https://console.apify.com/account/integrations"""

    # Append to warnings file
    with open("reports/apify_warnings.txt", "a") as f:
        f.write(warning + "\n\n")

    # Also log to run logger
    try:
        from run_logger import get_logger
        lgr = get_logger()
        for line in warning.split("\n"):
            lgr.log(f"  {line}")
    except Exception:
        pass


def log_apify_usage():
    """Log Apify credit usage for the active token to console and run log."""
    if not _TOKEN_VAL:
        print("   ⚠️  No Apify token configured, skipping usage check.")
        return

    try:
        # Get account info (includes plan limits)
        user_resp = requests.get(
            "https://api.apify.com/v2/users/me",
            params={"token": _TOKEN_VAL},
            timeout=10,
        )
        user_resp.raise_for_status()
        user_data = user_resp.json().get("data", {})

        plan = user_data.get("plan", {})
        plan_name = plan.get("id", "unknown")
        monthly_usage_usd = plan.get("monthlyUsageCreditsUsd", 0)

        # Get monthly usage
        usage_resp = requests.get(
            "https://api.apify.com/v2/users/me/usage/monthly",
            params={"token": _TOKEN_VAL},
            timeout=10,
        )
        usage_resp.raise_for_status()
        usage_data = usage_resp.json().get("data", {})

        total_usd = usage_data.get("totalUsageCreditsUsd", 0)

        remaining = max(0, monthly_usage_usd - total_usd)
        pct_used = (total_usd / monthly_usage_usd * 100) if monthly_usage_usd > 0 else 0

        # Print to console
        print(f"\n   💰  Apify Credits ({_TOKEN_NAME}):")
        print(f"       Plan:      {plan_name}")
        print(f"       Used:      ${total_usd:.4f}")
        print(f"       Limit:     ${monthly_usage_usd:.2f}")
        print(f"       Remaining: ${remaining:.4f} ({100 - pct_used:.1f}% left)")

        # Log to run logger if available
        try:
            from run_logger import get_logger
            logger = get_logger()
            logger.log(f"")
            logger.log(f"── Apify Credits ({_TOKEN_NAME}) ─────────────────────────")
            logger.log(f"  Plan:      {plan_name}")
            logger.log(f"  Used:      ${total_usd:.4f}")
            logger.log(f"  Limit:     ${monthly_usage_usd:.2f}")
            logger.log(f"  Remaining: ${remaining:.4f} ({100 - pct_used:.1f}% left)")
            if pct_used >= 90:
                logger.log(f"  ⚠️  WARNING: Credits nearly exhausted!")
                logger.log_error(f"Apify credits for {_TOKEN_NAME} at {pct_used:.0f}% — only ${remaining:.4f} left")
        except Exception:
            pass

    except Exception as e:
        print(f"   ⚠️  Could not check Apify usage for {_TOKEN_NAME}: {e}")
