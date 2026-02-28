#!/usr/bin/env python3
"""
JobPulse AI — Single entry point for running the daily job tracker.

Usage:
    python run.py                # runs based on PLATFORMS env var (default: both)
    python run.py --linkedin     # LinkedIn only
    python run.py --naukri       # Naukri only
    python run.py --both         # both platforms
    python run.py --no-email     # scrape without sending email
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Ensure scripts/ is in the path
SCRIPTS_DIR = Path(__file__).parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from dotenv import load_dotenv
load_dotenv()


def run_script(script_name: str, description: str) -> bool:
    """Run a Python script and return True on success."""
    script_path = SCRIPTS_DIR / script_name
    print(f"\n{'='*60}")
    print(f"  ▶  {description}")
    print(f"{'='*60}\n")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(Path(__file__).parent),
    )

    if result.returncode != 0:
        print(f"\n  ❌  {description} failed (exit code {result.returncode})")
        return False

    print(f"\n  ✅  {description} completed successfully")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="JobPulse AI — Automated daily job matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                 Run both LinkedIn & Naukri + send email
  python run.py --linkedin      LinkedIn only + send email
  python run.py --naukri        Naukri only + send email
  python run.py --no-email      Scrape without sending email
  python run.py --both --no-email  Scrape both, no email
        """,
    )
    parser.add_argument("--linkedin", action="store_true", help="Run LinkedIn scraper only")
    parser.add_argument("--naukri", action="store_true", help="Run Naukri scraper only")
    parser.add_argument("--both", action="store_true", help="Run both scrapers (default)")
    parser.add_argument("--no-email", action="store_true", help="Skip email sending")

    args = parser.parse_args()

    # Determine platforms
    if args.linkedin:
        platforms = "linkedin"
    elif args.naukri:
        platforms = "naukri"
    elif args.both:
        platforms = "both"
    else:
        # Fall back to env var
        platforms = os.environ.get("PLATFORMS", "both").strip().lower()

    send_email = not args.no_email

    print("╔══════════════════════════════════════════════════════════╗")
    print("║           🤖  JobPulse AI — Daily Job Tracker           ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"\n  Platforms:  {platforms}")
    print(f"  AI Mode:    {os.environ.get('AI_ANALYSIS', 'true')}")
    print(f"  Email:      {'Yes' if send_email else 'No'}")

    success = True

    # Step 1: LinkedIn scraper
    if platforms in ("both", "linkedin"):
        if not run_script("scrape_and_score.py", "LinkedIn Job Scraper"):
            success = False

    # Step 2: Naukri scraper
    if platforms in ("both", "naukri"):
        if not run_script("scrape_naukri.py", "Naukri Job Scraper"):
            success = False

    # Step 3: Email + Drive upload
    if send_email:
        if not run_script("send_email.py", "Email & Drive Upload"):
            success = False

    # Final status
    print(f"\n{'='*60}")
    if success:
        print("  🎉  All steps completed successfully!")
    else:
        print("  ⚠️  Some steps had errors. Check the logs above.")
    print(f"{'='*60}\n")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
