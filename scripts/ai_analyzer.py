from __future__ import annotations
"""
AI Job Analyzer — Gemini-powered deep job-resume matching.

Supports two modes (configurable via BATCH_AI env var):
  - BATCH MODE (default, recommended): All jobs sent in ONE API call → no rate limits
  - SINGLE MODE: Each job analyzed individually → uses more API calls

When AI_ANALYSIS=true, this module completely replaces the keyword-based
scoring with Gemini AI analysis. Each job is evaluated against the user's
resume profile to produce:
  - Match Score (%)
  - Role Fit (Strong Fit / Moderate Fit / Weak Fit / Not a Fit)
  - AI Summary (2-3 sentence assessment)
  - Missing Skills
  - Resume Tips

Includes pre-filtering to skip obviously irrelevant jobs and save API calls.

Usage:
    from ai_analyzer import analyze_jobs, is_ai_enabled
    if is_ai_enabled():
        jobs = analyze_jobs(raw_jobs)  # returns list of scored dicts
"""

import os
import re
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────
from resume_loader import load_resume, get_resume_info
from job_history import JobHistory

# ── Pre-filter: titles containing these keywords are skipped ──────────
IRRELEVANT_TITLE_KEYWORDS = [
    # HR / Recruitment
    "hr ", "hr trainer", "human resource", "recruiter", "recruiting",
    "talent acquisition",
    # Sales / Marketing / Finance
    "sales executive", "sales manager", "tele sales", "telesales",
    "business development", "merchandiser", "marketing executive",
    "digital marketing", "seo executive", "account manager",
    "assistant account", "relationship manager",
    # Customer Service
    "customer care", "customer service", "customer support",
    "call center", "bpo",
    # Non-tech
    "retail designer", "interior designer", "content writer",
    "graphic designer", "video editor", "photographer",
    "teaching faculty", "teacher", "trainer",
    # Finance / Legal
    "chartered accountant", "ca ", "company secretary",
    "legal", "lawyer", "advocate",
    # Medical
    "doctor", "nurse", "pharmacist", "medical",
    # Operations
    "delivery executive", "warehouse", "logistics",
    "driver", "housekeeping",
]


def is_ai_enabled() -> bool:
    """Check if AI analysis is enabled via AI_ANALYSIS env var."""
    val = os.environ.get("AI_ANALYSIS", "false").strip().lower()
    return val in ("true", "1", "yes", "on")


def is_batch_mode() -> bool:
    """Check if batch mode is enabled (default: true).

    Batch mode sends ALL jobs in a single API call to avoid rate limits.
    Set BATCH_AI=false to use per-job analysis instead.
    """
    val = os.environ.get("BATCH_AI", "true").strip().lower()
    return val in ("true", "1", "yes", "on")


def _is_relevant_job(title: str) -> bool:
    """Check if a job title is relevant (not in the irrelevant list)."""
    title_lower = title.lower().strip()
    for keyword in IRRELEVANT_TITLE_KEYWORDS:
        if keyword in title_lower:
            return False
    return True


# ═════════════════════════════════════════════════════════════════════
#  BATCH PROMPT — All jobs in one call
# ═════════════════════════════════════════════════════════════════════
def _build_batch_prompt(profile: str, jobs_list: list[dict]) -> str:
    """Build a single prompt that asks Gemini to score ALL jobs at once."""
    jobs_text = ""
    for idx, job in enumerate(jobs_list, 1):
        desc_truncated = job["description"][:2000]
        jobs_text += f"""
--- JOB {idx} ---
Title: {job["title"]}
Company: {job["company"]}
Location: {job["location"]}
Experience Required: {job["exp_required"]}
Description:
{desc_truncated}
"""

    return f"""You are an expert job-resume matching analyst. Analyze how well this candidate matches EACH of the following {len(jobs_list)} job postings.

=== CANDIDATE PROFILE ===
{profile}

=== JOB POSTINGS ===
{jobs_text}

=== INSTRUCTIONS ===
Analyze the match between the candidate and EACH job posting above.

Return ONLY a valid JSON array with {len(jobs_list)} objects (one per job, in the same order).
No markdown, no code fences, no extra text — just the raw JSON array.

Each object must have these exact keys:
{{
  "job_index": <integer, 1-based index matching the job number above>,
  "match_score": <integer 0-100>,
  "role_fit": "<exactly one of: Strong Fit, Moderate Fit, Weak Fit, Not a Fit>",
  "ai_summary": "<2-3 sentences explaining why this is or isn't a good match>",
  "missing_skills": "<comma-separated list of skills the candidate lacks, or 'None'>",
  "resume_tips": "<1-2 specific, actionable tips to tailor resume for this role>"
}}

Scoring guide:
- 80-100: Strong Fit — core skills match, experience level right, strong overlap
- 60-79: Moderate Fit — many skills match but some gaps
- 40-59: Weak Fit — partial overlap, significant gaps
- 0-39: Not a Fit — different tech stack or seniority level

Be realistic and specific. Do not inflate scores."""


# ═════════════════════════════════════════════════════════════════════
#  SINGLE PROMPT — One job at a time (legacy)
# ═════════════════════════════════════════════════════════════════════
def _build_single_prompt(profile: str, job_title: str, company: str, description: str,
                         location: str, exp_required: str) -> str:
    """Build the Gemini prompt for a single job analysis."""
    return f"""You are an expert job-resume matching analyst. Analyze how well this candidate matches the given job posting.

=== CANDIDATE PROFILE ===
{profile}

=== JOB POSTING ===
Title: {job_title}
Company: {company}
Location: {location}
Experience Required: {exp_required}
Description:
{description[:3000]}

=== INSTRUCTIONS ===
Analyze the match between the candidate and this job posting. Return ONLY a valid JSON object with these exact keys (no markdown, no code fences, no extra text):

{{
  "match_score": <integer 0-100>,
  "role_fit": "<exactly one of: Strong Fit, Moderate Fit, Weak Fit, Not a Fit>",
  "ai_summary": "<2-3 sentences explaining why this is or isn't a good match>",
  "missing_skills": "<comma-separated list of skills the candidate lacks for this role, or 'None' if perfect match>",
  "resume_tips": "<1-2 specific, actionable tips to tailor resume for this role>"
}}

Scoring guide:
- 80-100: Strong Fit — core skills match, experience level right, strong overlap
- 60-79: Moderate Fit — many skills match but some gaps
- 40-59: Weak Fit — partial overlap, significant gaps
- 0-39: Not a Fit — different tech stack or seniority level

Be realistic and specific. Do not inflate scores."""


# ═════════════════════════════════════════════════════════════════════
#  RESPONSE PARSERS
# ═════════════════════════════════════════════════════════════════════
def _parse_single_response(text: str) -> dict | None:
    """Parse Gemini's JSON response for a single job."""
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)

        # If it's a list (Gemini sometimes wraps single result in array)
        if isinstance(data, list):
            data = data[0] if data else None
            if data is None:
                return None

        return _validate_ai_result(data)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"   ⚠️  Failed to parse AI response: {e}")
        print(f"   Raw: {cleaned[:200]}")
        return None


def _parse_batch_response(text: str, expected_count: int) -> list[dict | None]:
    """Parse Gemini's JSON array response for batch analysis.

    Returns a list of parsed results (or None for failed items),
    matching the expected_count length.
    """
    if not text:
        return [None] * expected_count

    cleaned = text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)

        # Handle case where Gemini returns a single object instead of array
        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            print(f"   ⚠️  Batch response is not a JSON array")
            return [None] * expected_count

        results = [None] * expected_count

        for item in data:
            if not isinstance(item, dict):
                continue

            # Find the job index
            idx = item.get("job_index", 0)
            if isinstance(idx, int) and 1 <= idx <= expected_count:
                validated = _validate_ai_result(item)
                results[idx - 1] = validated
            else:
                # Try to place by position in array
                pos = data.index(item)
                if pos < expected_count:
                    validated = _validate_ai_result(item)
                    results[pos] = validated

        return results

    except (json.JSONDecodeError, ValueError) as e:
        print(f"   ⚠️  Failed to parse batch AI response: {e}")
        print(f"   Raw: {cleaned[:300]}")
        return [None] * expected_count


def _validate_ai_result(data: dict) -> dict | None:
    """Validate and normalize a single AI result dict."""
    required = {"match_score", "role_fit", "ai_summary", "missing_skills", "resume_tips"}
    if not required.issubset(data.keys()):
        missing = required - data.keys()
        print(f"   ⚠️  AI response missing keys: {missing}")
        return None

    # Clamp score
    try:
        data["match_score"] = max(0, min(100, int(data["match_score"])))
    except (ValueError, TypeError):
        data["match_score"] = 0

    # Normalize role_fit
    valid_fits = {"Strong Fit", "Moderate Fit", "Weak Fit", "Not a Fit"}
    if data["role_fit"] not in valid_fits:
        fit_lower = str(data["role_fit"]).lower()
        if "strong" in fit_lower:
            data["role_fit"] = "Strong Fit"
        elif "moderate" in fit_lower:
            data["role_fit"] = "Moderate Fit"
        elif "weak" in fit_lower:
            data["role_fit"] = "Weak Fit"
        else:
            data["role_fit"] = "Not a Fit"

    # Ensure string fields
    for key in ("ai_summary", "missing_skills", "resume_tips"):
        val = data.get(key, "—")
        if isinstance(val, list):
            data[key] = ", ".join(str(v) for v in val)
        elif not isinstance(val, str):
            data[key] = str(val)

    return data


def _fallback_result() -> dict:
    """Return a fallback result when AI analysis fails for a job."""
    return {
        "match_score": 0,
        "role_fit": "AI Unavailable",
        "ai_summary": "AI analysis could not be completed for this job.",
        "missing_skills": "—",
        "resume_tips": "—",
    }


def _extract_exp_simple(desc: str) -> str:
    """Quick experience extraction."""
    m = re.search(r"(\d+)\s*[-–to]+\s*(\d+)\s*years?", desc)
    if m:
        return f"{m.group(1)}–{m.group(2)} yrs"
    m2 = re.search(r"(\d+)\+\s*years?", desc)
    if m2:
        return f"{m2.group(1)}+ yrs"
    return "Not specified"


def _detect_work_mode(desc: str, location: str) -> str:
    """Detect work mode from description and location."""
    desc_lower = desc.lower()[:800]
    loc_lower = location.lower()
    if "fully remote" in desc_lower or "remote" in loc_lower:
        return "Fully Remote"
    if "hybrid" in desc_lower[:400]:
        return "Hybrid"
    if "remote" in desc_lower[:400]:
        return "Remote"
    return "Onsite"


def _extract_skills_from_desc(desc: str) -> str:
    """Extract skill labels from a job description using the skill taxonomy."""
    from scrape_and_score import MUST_HAVE, BACKEND_PLUS, NICE_TO_HAVE, LABEL
    desc_lower = desc.lower()
    found_skills, seen_labels = [], set()
    for s in MUST_HAVE + BACKEND_PLUS + NICE_TO_HAVE:
        if s in desc_lower:
            lbl = LABEL.get(s, s.title())
            if lbl not in seen_labels:
                seen_labels.add(lbl)
                found_skills.append(lbl)
    return ", ".join(found_skills[:10])


# ═════════════════════════════════════════════════════════════════════
#  MAIN: analyze_jobs() — supports both batch and single modes
# ═════════════════════════════════════════════════════════════════════
def analyze_jobs(raw_jobs: list[dict], platform: str = "LinkedIn") -> list[dict]:
    """Analyze jobs using Gemini AI.

    Mode is controlled by BATCH_AI env var (default: true).
    - Batch mode: 1 API call for all jobs (avoids rate limits)
    - Single mode: 1 API call per job

    Args:
        raw_jobs: list of raw job dicts (from Apify scraper)
        platform: "LinkedIn" or "Naukri"

    Returns:
        list of scored job dicts ready for build_excel(), sorted by match_score desc
    """
    from gemini_token import GeminiKeyManager
    from run_logger import get_logger

    profile = load_resume()
    resume_info = get_resume_info()
    mgr = GeminiKeyManager()
    logger = get_logger()
    batch = is_batch_mode()

    logger.log(f"")
    logger.log(f"🤖  Starting AI analysis for {len(raw_jobs)} {platform} jobs …")
    logger.log(f"   Profile loaded: {resume_info['size_chars']} chars from {resume_info['name']} ({resume_info['format']})")
    logger.log(f"   Mode: {'📦 BATCH (all jobs in 1 API call)' if batch else '🔄 SINGLE (1 API call per job)'}")

    # ── Step 1: Prep & filter jobs ────────────────────────────────────
    prepared_jobs = []
    results = []
    total = len(raw_jobs)
    filtered = 0

    for i, job in enumerate(raw_jobs, 1):
        title = (job.get("title", "") or job.get("Job Title", "")).strip()
        company = (job.get("companyName", "") or job.get("Company", "")).strip()
        location = (job.get("location", "") or job.get("Location", "India")).strip() or "India"
        desc = (job.get("descriptionText", "") or job.get("Description", "")).strip()
        link = (job.get("link", "") or job.get("Job URL", "")).strip()
        posted = (job.get("postedAt", "") or job.get("Posted Time", "")).strip()

        skills_tags = job.get("Skills/Tags", "")
        if skills_tags:
            desc += " " + skills_tags

        if not title or not desc:
            continue

        if not _is_relevant_job(title):
            logger.log(f"   [{i:02d}/{total}] 🚫 Filtered (irrelevant): {title[:45]} @ {company[:25]}")
            logger.log_job(title, company, "—", "filtered", platform=platform)
            filtered += 1
            continue

        exp_str = _extract_exp_simple(desc.lower())
        work_mode = _detect_work_mode(desc, location)
        key_skills = _extract_skills_from_desc(desc)

        prepared_jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "description": desc,
            "link": link,
            "posted": posted,
            "exp_required": exp_str,
            "work_mode": work_mode,
            "key_skills": key_skills,
        })

    if not prepared_jobs:
        logger.log("   ⚠️  No relevant jobs to analyze after filtering.")
        return []

    logger.log(f"   📋 {len(prepared_jobs)} jobs to analyze ({filtered} filtered out)")

    # ── Step 2: Call Gemini ────────────────────────────────────────────
    if batch:
        results = _analyze_batch(prepared_jobs, profile, mgr, logger, platform)
    else:
        results = _analyze_single(prepared_jobs, profile, mgr, logger, platform)

    # ── Step 3: Track job history ─────────────────────────────────────
    history = JobHistory()
    for j in results:
        status = history.check_job(j["title"], j["company"], platform, j.get("match_score", 0))
        j["job_status"] = status

    hist_stats = history.get_stats()
    history.save()
    logger.log(f"   📜 Job history: {hist_stats['new']} new, {hist_stats['seen']} seen before ({hist_stats['total_tracked']} total tracked)")

    # ── Step 4: Sort, dedup, return ───────────────────────────────────
    results.sort(key=lambda x: x["score_raw"], reverse=True)

    seen, unique = set(), []
    for j in results:
        key = (j["title"].lower()[:40], j["company"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(j)

    ai_scored = sum(1 for j in unique if j["interview_prob"] != "AI Unavailable")
    ai_failed = sum(1 for j in unique if j["interview_prob"] == "AI Unavailable")
    logger.log_platform_stats(platform, total, ai_scored, ai_failed, filtered)

    alive = mgr.get_alive_count()
    logger.log(f"   API keys still alive: {alive}/{len(mgr._keys)}")

    return unique[:20]


# ═════════════════════════════════════════════════════════════════════
#  BATCH ANALYSIS — All jobs in 1 API call
# ═════════════════════════════════════════════════════════════════════
def _analyze_batch(prepared_jobs: list[dict], profile: str,
                   mgr, logger, platform: str) -> list[dict]:
    """Send ALL jobs in a single Gemini API call and parse batch response.

    If any jobs fail in the batch, they are retried individually.
    """
    n = len(prepared_jobs)
    logger.log(f"   📦 Sending {n} jobs in a single batch API call …")

    start_t = time.time()
    key_name = mgr.get_current_key_name()
    prompt = _build_batch_prompt(profile, prepared_jobs)
    response_text = mgr.generate(prompt)
    elapsed = time.time() - start_t

    logger.log(f"   ⏱️  Batch response received in {elapsed:.1f}s")

    # Parse the batch response
    ai_results = _parse_batch_response(response_text, n)

    # ── Retry failed jobs individually ────────────────────────────────
    failed_indices = [i for i, r in enumerate(ai_results) if r is None]
    if failed_indices:
        logger.log(f"   🔄 Retrying {len(failed_indices)} failed job(s) individually …")
        for idx in failed_indices:
            job = prepared_jobs[idx]
            logger.log(f"      Retrying: {job['title'][:45]} @ {job['company'][:25]} …")
            retry_start = time.time()
            retry_prompt = _build_single_prompt(
                profile, job["title"], job["company"],
                job["description"], job["location"], job["exp_required"]
            )
            retry_response = mgr.generate(retry_prompt)
            retry_elapsed = time.time() - retry_start
            retry_data = _parse_single_response(retry_response) if retry_response else None
            if retry_data:
                ai_results[idx] = retry_data
                logger.log(f"      ✅ Retry succeeded: {retry_data['match_score']}% ({retry_data['role_fit']}) [{retry_elapsed:.1f}s]")
            else:
                logger.log(f"      ❌ Retry also failed [{retry_elapsed:.1f}s]")

    # ── Build results ─────────────────────────────────────────────────
    results = []
    for i, (job, ai_data) in enumerate(zip(prepared_jobs, ai_results)):
        if ai_data is None:
            logger.log(f"   [{i+1:02d}/{n}] ⚠️ {job['title'][:40]} @ {job['company'][:20]} → fallback")
            logger.log_job(job["title"], job["company"], key_name, "failed",
                          time_s=elapsed/n, platform=platform, error="No valid AI response")
            ai_data = _fallback_result()
        else:
            logger.log(f"   [{i+1:02d}/{n}] ✅ {job['title'][:40]} @ {job['company'][:20]} → {ai_data['match_score']}% ({ai_data['role_fit']})")
            logger.log_job(job["title"], job["company"], key_name, "success",
                          score=ai_data["match_score"], fit=ai_data["role_fit"],
                          time_s=elapsed/n, platform=platform)

        results.append({
            "title":          job["title"],
            "company":        job["company"],
            "location":       job["location"],
            "work_mode":      job["work_mode"],
            "posted":         job["posted"],
            "exp_req":        job["exp_required"],
            "key_skills":     job["key_skills"],
            "link":           job["link"],
            "match_score":    ai_data["match_score"],
            "interview_prob": ai_data["role_fit"],
            "ai_summary":     ai_data["ai_summary"],
            "missing_skills": ai_data["missing_skills"],
            "resume_tips":    ai_data["resume_tips"],
            "score_raw":      ai_data["match_score"],
        })

    return results


# ═════════════════════════════════════════════════════════════════════
#  SINGLE ANALYSIS — 1 API call per job (legacy)
# ═════════════════════════════════════════════════════════════════════
def _analyze_single(prepared_jobs: list[dict], profile: str,
                    mgr, logger, platform: str) -> list[dict]:
    """Analyze each job individually with a separate API call."""
    results = []
    n = len(prepared_jobs)

    for i, job in enumerate(prepared_jobs, 1):
        logger.log(f"   [{i:02d}/{n}] Analyzing: {job['title'][:45]} @ {job['company'][:25]} …")

        start_t = time.time()
        key_name = mgr.get_current_key_name()
        prompt = _build_single_prompt(
            profile, job["title"], job["company"],
            job["description"], job["location"], job["exp_required"]
        )
        response_text = mgr.generate(prompt)
        elapsed = time.time() - start_t
        ai_data = _parse_single_response(response_text) if response_text else None

        if ai_data is None:
            logger.log(f"            ⚠️ fallback ({elapsed:.1f}s)")
            logger.log_job(job["title"], job["company"], key_name, "failed",
                          time_s=elapsed, platform=platform, error="No valid AI response")
            ai_data = _fallback_result()
        else:
            logger.log(f"            ✅ {ai_data['match_score']}% ({ai_data['role_fit']}) [{elapsed:.1f}s]")
            logger.log_job(job["title"], job["company"], key_name, "success",
                          score=ai_data["match_score"], fit=ai_data["role_fit"],
                          time_s=elapsed, platform=platform)

        results.append({
            "title":          job["title"],
            "company":        job["company"],
            "location":       job["location"],
            "work_mode":      job["work_mode"],
            "posted":         job["posted"],
            "exp_req":        job["exp_required"],
            "key_skills":     job["key_skills"],
            "link":           job["link"],
            "match_score":    ai_data["match_score"],
            "interview_prob": ai_data["role_fit"],
            "ai_summary":     ai_data["ai_summary"],
            "missing_skills": ai_data["missing_skills"],
            "resume_tips":    ai_data["resume_tips"],
            "score_raw":      ai_data["match_score"],
        })

    return results


# ═══════════════════════════════════════════════════════════════════════
# Test entrypoint
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  AI Analyzer — Quick Test")
    print("=" * 60)

    # Test 1: Profile loading
    try:
        p = load_resume()
        print(f"✅  Profile loaded: {len(p)} chars")
    except (FileNotFoundError, ValueError, ImportError) as e:
        print(f"❌  Profile error: {e}")
        exit(1)

    # Test 2: Pre-filter check
    assert _is_relevant_job("Backend Developer") == True
    assert _is_relevant_job("HR Trainer and Teaching Faculty") == False
    assert _is_relevant_job("Sales Executive") == False
    assert _is_relevant_job("Full Stack Developer") == True
    assert _is_relevant_job("Customer Care Executive") == False
    print("✅  Pre-filter working correctly")

    # Test 3: Mode check
    print(f"✅  Batch mode: {is_batch_mode()}")

    # Test 4: Gemini connectivity
    from gemini_token import GeminiKeyManager
    try:
        mgr = GeminiKeyManager()
        resp = mgr.generate("Reply with exactly: GEMINI_OK")
        if resp and "GEMINI_OK" in resp.upper().replace(" ", "_"):
            print(f"✅  Gemini API connected: {resp.strip()[:50]}")
        else:
            print(f"⚠️  Gemini responded but unexpected: {resp[:100] if resp else 'None'}")
    except Exception as e:
        print(f"❌  Gemini error: {e}")
        exit(1)

    # Test 5: Analyze sample jobs (batch mode)
    sample_jobs = [
        {
            "title": "Senior Node.js Backend Developer",
            "companyName": "Test Corp",
            "location": "Bangalore, India",
            "descriptionText": "We need a Node.js developer with 3-5 years experience. "
                              "Skills: Node.js, Express, MongoDB, React, AWS, Docker, "
                              "Microservices, REST API, TypeScript. Remote friendly.",
            "link": "https://example.com/job/123",
            "postedAt": "2026-02-21",
        },
        {
            "title": "Python Data Engineer",
            "companyName": "DataCo",
            "location": "Hyderabad, India",
            "descriptionText": "Looking for Python Data Engineer with 5+ years. "
                              "Skills: Python, PySpark, Hadoop, SQL, ETL pipelines, "
                              "AWS Glue, Redshift, Airflow.",
            "link": "https://example.com/job/456",
            "postedAt": "2026-02-22",
        },
    ]
    print(f"\n🧪  Analyzing {len(sample_jobs)} sample jobs (batch mode: {is_batch_mode()}) …")
    result = analyze_jobs(sample_jobs)
    if result:
        for j in result:
            print(f"\n📊  {j['title']}:")
            print(f"   Score:    {j['match_score']}%")
            print(f"   Fit:      {j['interview_prob']}")
            print(f"   Summary:  {j['ai_summary'][:100]}")
        print("\n✅  All tests passed!")
    else:
        print("❌  No result returned")
