from __future__ import annotations
"""
Naukri India Job Scraper & Scorer
Calls Apify API (codemaverick/naukri-job-scraper-latest) → normalises data →
scores jobs using the same logic as LinkedIn → saves ranked .xlsx report

This actor uses only Apify compute credits (no per-event fee).
"""

import os
import sys
import time
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

# Import logger (init happens after all imports below)
from run_logger import new_logger, get_logger

# Add scripts directory to path so we can import from scrape_and_score
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrape_and_score import (
    score_job, build_excel, TODAY, YESTERDAY,
)
from ai_analyzer import is_ai_enabled, analyze_jobs as ai_analyze_jobs

# ═════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════
from apify_token import get_apify_token, try_next_token, is_auth_error, get_current_token_name

# Initialize Naukri logger AFTER all imports (scrape_and_score import must not overwrite it)
_logger = new_logger(section="Naukri Scraper")

ACTOR_ID = "codemaverick~naukri-job-scraper-latest"

# ── Naukri search URLs ───────────────────────────────────────────────
# Configurable via SEARCH_KEYWORDS and SEARCH_LOCATION env vars.
# If not set, falls back to default URLs below.
def _build_naukri_urls() -> list[str]:
    """Build Naukri search URLs from env vars or use defaults."""
    keywords_raw = os.environ.get("SEARCH_KEYWORDS", "").strip()
    location = os.environ.get("SEARCH_LOCATION", "India").strip()

    if keywords_raw:
        keywords_list = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        urls = []
        for kw in keywords_list:
            slug = kw.lower().replace(" ", "-").replace(".", "-")
            encoded = kw.replace(" ", "%20")
            urls.append(
                f"https://www.naukri.com/{slug}-jobs?k={encoded}"
                f"&experience=2&nignbelow_salary=500000&jobAge=1"
            )
        return urls

    # Default: hardcoded URLs (Node.js focused)
    return [
        "https://www.naukri.com/node-js-developer-jobs?k=node.js%20developer&experience=2&nignbelow_salary=500000&jobAge=1",
        "https://www.naukri.com/mern-stack-developer-jobs?k=mern%20stack%20developer&experience=2&nignbelow_salary=500000&jobAge=1",
        "https://www.naukri.com/backend-developer-jobs?k=backend%20developer%20node&experience=2&nignbelow_salary=500000&jobAge=1",
        "https://www.naukri.com/full-stack-developer-jobs?k=full%20stack%20developer%20node%20react&experience=2&nignbelow_salary=500000&jobAge=1",
    ]

NAUKRI_SEARCH_URLS = _build_naukri_urls()


# ═════════════════════════════════════════════════════════════════════
# APIFY  —  run actor & fetch results
# ═════════════════════════════════════════════════════════════════════
def run_naukri_actor() -> list[dict]:
    """Trigger the Naukri Apify actor and collect results.
    Cascades through APIFY_TOKEN_1, _2, _3... on auth failure."""
    base  = "https://api.apify.com/v2"
    token = get_apify_token()
    while True:
        result = _try_naukri_run(base, token)
        if result is not None:
            return result
        token = try_next_token("scrape_naukri.py (Naukri)")
        if not token:
            print("   ⚠️  All tokens exhausted. Returning empty.")
            return []


def _try_naukri_run(base: str, token: str) -> list[dict] | None:
    """Attempt a Naukri actor run. Returns None on auth failure."""
    params = {"token": token}

    print(f"\n▶  Starting Naukri actor … ({get_current_token_name()})")
    run_resp = requests.post(
        f"{base}/acts/{ACTOR_ID}/runs",
        params=params,
        json={
            "startUrls": [{"url": u} for u in NAUKRI_SEARCH_URLS],
            "maxItems":  100,
        },
        timeout=30,
    )

    if is_auth_error(run_resp.status_code):
        print(f"   ⚠️  {get_current_token_name()} failed (HTTP {run_resp.status_code})")
        return None

    run_resp.raise_for_status()
    run_id = run_resp.json()["data"]["id"]
    print(f"   Run ID: {run_id}")

    # Poll until finished (max 5 min)
    status = "RUNNING"
    for attempt in range(30):
        time.sleep(10)
        status_resp = requests.get(
            f"{base}/actor-runs/{run_id}", params=params, timeout=15
        )
        status = status_resp.json()["data"]["status"]
        print(f"   [{attempt+1:02d}] Status: {status}")
        if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            break

    if status != "SUCCEEDED":
        print(f"   ⚠️  Naukri run failed — status: {status}")
        return []

    dataset_id = status_resp.json()["data"]["defaultDatasetId"]
    items_resp = requests.get(
        f"{base}/datasets/{dataset_id}/items",
        params={**params, "format": "json", "limit": 200},
        timeout=30,
    )
    items_resp.raise_for_status()
    items = items_resp.json()
    print(f"   Fetched {len(items)} items from Naukri dataset.")
    return items


# ═════════════════════════════════════════════════════════════════════
# NORMALISE  — codemaverick fields → same dict format expected by score_job()
# ═════════════════════════════════════════════════════════════════════
def normalise_naukri(item: dict) -> dict:
    """Convert a codemaverick/naukri-job-scraper-latest result to the
    format expected by score_job().

    Output keys from the actor:
      Job Title, Company, Description, Location, Skills/Tags,
      Job URL, Salary, Experience Required, Posted Time, Rating, Reviews
    """
    title    = item.get("Job Title", "").strip()
    company  = item.get("Company", "").strip()
    location = item.get("Location", "India").strip() or "India"
    link     = item.get("Job URL", "")
    posted   = item.get("Posted Time", "")

    # Build description from Description + Skills/Tags + Experience
    desc = item.get("Description", "")
    skills = item.get("Skills/Tags", "")
    if skills:
        desc += " " + skills
    exp = item.get("Experience Required", "")
    if exp:
        desc += f" {exp} experience"

    # Detect remote
    loc_lower = location.lower()
    if "remote" in loc_lower or "work from home" in loc_lower:
        desc = "remote " + desc

    return {
        "title":           title,
        "companyName":     company,
        "location":        location,
        "descriptionText": desc,
        "link":            link,
        "postedAt":        posted,
    }


# ═════════════════════════════════════════════════════════════════════
# PROCESS & DEDUPLICATE
# ═════════════════════════════════════════════════════════════════════
def process_naukri_jobs(raw: list[dict]) -> list[dict]:
    """Normalise, score, sort, and deduplicate Naukri jobs."""
    normalised = []
    for item in raw:
        if isinstance(item, dict):
            title = item.get("Job Title", "").strip()
            if title and title != "-":
                normalised.append(normalise_naukri(item))

    print(f"   Valid Naukri job records: {len(normalised)}")

    scored = [score_job(j) for j in normalised]
    scored.sort(key=lambda x: x["score_raw"], reverse=True)

    # Deduplicate
    seen, unique = set(), []
    for j in scored:
        key = (j["title"].lower()[:40], j["company"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(j)

    return unique[:20]


# ═════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ai_mode = is_ai_enabled()
    raw  = run_naukri_actor()

    # Log Apify credit usage after scraping
    from apify_token import log_apify_usage
    log_apify_usage()

    if ai_mode:
        print("\n🤖  AI_ANALYSIS is ON — using Gemini AI for Naukri scoring.")
        # Filter valid items
        valid = [item for item in raw if isinstance(item, dict)
                 and item.get("Job Title", "").strip()
                 and item.get("Job Title", "").strip() != "-"]
        # Normalise to common format for AI analyzer
        normalised = [normalise_naukri(item) for item in valid]
        # Deduplicate before sending to AI
        seen, unique_raw = set(), []
        for j in normalised:
            key = (j.get("title", "").lower()[:40], j.get("companyName", "").lower())
            if key not in seen:
                seen.add(key)
                unique_raw.append(j)
        job_count = int(os.environ.get("JOB_COUNT", "20"))
        unique_raw = unique_raw[:job_count]
        jobs = ai_analyze_jobs(unique_raw, platform="Naukri")
    else:
        print("\n📊  AI_ANALYSIS is OFF — using keyword-based scoring.")
        jobs = process_naukri_jobs(raw)

    if not jobs:
        print("⚠️  No matching Naukri jobs found today. Exiting.")
        exit(0)

    print(f"\n📋  Top {len(jobs)} Naukri jobs selected.")
    for i, j in enumerate(jobs, 1):
        print(f"  {i:2}. {j['match_score']:2}% | {j['interview_prob']:>15} | {j['title'][:40]} | {j['company'][:25]}")

    out_path = f"reports/Naukri_India_Jobs_{TODAY}.xlsx"
    os.makedirs("reports", exist_ok=True)
    build_excel(jobs, out_path, platform="Naukri", ai_mode=ai_mode)

    # Write summary for email step
    mode_tag = "🤖 AI" if ai_mode else "📊 Keyword"
    summary_lines = [
        f"📅 Date: {TODAY}",
        f"📊 Naukri jobs scraped & ranked: {len(jobs)} ({mode_tag} scoring)",
        "",
        "Top 5 Naukri Matches:",
    ]
    for i, j in enumerate(jobs[:5], 1):
        summary_lines.append(f"  {i}. [{j['match_score']}% | {j['interview_prob']}] {j['title']} @ {j['company']} ({j['work_mode']})")
    summary_lines += ["", "Full Naukri report attached as .xlsx ✅"]

    with open("reports/naukri_email_summary.txt", "w") as f:
        f.write("\n".join(summary_lines))

    print("\n📧  Naukri email summary written.")
    print("\n".join(summary_lines))

    # Always save run log
    _logger.save()
