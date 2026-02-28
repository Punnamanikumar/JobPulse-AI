from __future__ import annotations
"""
Run Logger — End-to-end execution logging for JobPulse AI.

Supports multi-process appending: LinkedIn scraper, Naukri scraper, and
send_email.py all append to the same log file for the day.

Usage:
    from run_logger import RunLogger, get_logger
    logger = get_logger()
    logger.log("Starting scrape...")
    logger.log_key_event("GEMINI_KEY_1", "rate_limited", "429 Too Many Requests")
    logger.log_job("Backend Dev", "TechCorp", "GEMINI_KEY_1", "success", score=85, time_s=2.3)
    logger.save()   # appends to reports/run_log_YYYY-MM-DD.txt
"""

import os
import time
from datetime import datetime, date


class RunLogger:
    """Centralized run logger that tracks everything in a single run."""

    def __init__(self, section: str = ""):
        self._start_time = time.time()
        self._section = section  # e.g., "LinkedIn Scraper", "Naukri Scraper", "Email & Drive"
        self._lines: list[str] = []
        self._job_logs: list[dict] = []
        self._key_stats: dict[str, dict] = {}
        self._config: dict = {}
        self._errors: list[str] = []
        self._platform_stats: dict[str, dict] = {}
        self._apify_logs: list[str] = []
        self._drive_logs: list[str] = []
        self._email_logs: list[str] = []

        header = f"  {section}" if section else "  JobPulse AI — Run Log"
        self.log(f"")
        self.log(f"═══════════════════════════════════════════════════════")
        self.log(f"{header}")
        self.log(f"  Date: {date.today().isoformat()}")
        self.log(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"═══════════════════════════════════════════════════════")

    # ── General logging ───────────────────────────────────────────────
    def log(self, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}"
        self._lines.append(line)
        print(line)

    def log_error(self, message: str):
        self._errors.append(message)
        self.log(f"❌ ERROR: {message}")

    # ── Configuration logging ─────────────────────────────────────────
    def log_config(self, keys_loaded: int, key_names: list[str],
                   model: str, rpm_limit: int):
        self._config = {
            "keys_loaded": keys_loaded,
            "key_names": key_names,
            "model": model,
            "rpm_limit": rpm_limit,
        }
        self.log(f"")
        self.log(f"── Configuration ──────────────────────────────────────")
        self.log(f"  Gemini keys loaded: {keys_loaded} ({', '.join(key_names)})")
        self.log(f"  Model: {model}")
        self.log(f"  RPM limit per key: {rpm_limit}")
        self.log(f"  Effective RPM: {keys_loaded * rpm_limit}")

        for name in key_names:
            self._key_stats[name] = {
                "requests": 0, "successes": 0,
                "failures": 0, "rate_limits": 0,
                "status": "alive",
            }

    # ── Key event logging ─────────────────────────────────────────────
    def log_key_event(self, key_name: str, event: str, detail: str = ""):
        if key_name not in self._key_stats:
            self._key_stats[key_name] = {
                "requests": 0, "successes": 0,
                "failures": 0, "rate_limits": 0,
                "status": "alive",
            }
        stats = self._key_stats[key_name]

        if event == "request":
            stats["requests"] += 1
        elif event == "success":
            stats["successes"] += 1
        elif event == "rate_limited":
            stats["rate_limits"] += 1
            self.log(f"  ⚠️  {key_name} rate limited: {detail}")
        elif event == "failed":
            stats["failures"] += 1
            stats["status"] = "dead"
            self.log(f"  ❌  {key_name} permanently failed: {detail}")
        elif event == "recovered":
            self.log(f"  🔄  {key_name} recovered after cooldown")

    # ── Per-job logging ───────────────────────────────────────────────
    def log_job(self, title: str, company: str, key_name: str,
                status: str, score: int = 0, fit: str = "",
                time_s: float = 0, platform: str = "LinkedIn",
                error: str = ""):
        self._job_logs.append({
            "title": title[:50],
            "company": company[:30],
            "key_name": key_name,
            "status": status,
            "score": score,
            "fit": fit,
            "time_s": round(time_s, 2),
            "platform": platform,
            "error": error,
        })

    # ── Platform stats ────────────────────────────────────────────────
    def log_platform_stats(self, platform: str, total: int,
                           ai_scored: int, ai_failed: int, filtered: int = 0):
        self._platform_stats[platform] = {
            "total": total,
            "ai_scored": ai_scored,
            "ai_failed": ai_failed,
            "filtered": filtered,
        }
        self.log(f"")
        self.log(f"── {platform} Results ─────────────────────────────────")
        self.log(f"  Total jobs processed: {total}")
        if filtered > 0:
            self.log(f"  Pre-filtered (irrelevant): {filtered}")
        self.log(f"  AI scored successfully: {ai_scored}")
        self.log(f"  AI failed (fallback): {ai_failed}")

    # ── Apify token logging ───────────────────────────────────────────
    def log_apify_event(self, token_name: str, event: str, detail: str = ""):
        msg = f"  🔑 Apify {token_name}: {event}"
        if detail:
            msg += f" — {detail}"
        self._apify_logs.append(msg)
        self.log(msg)

    # ── Drive upload logging ──────────────────────────────────────────
    def log_drive_event(self, event: str, detail: str = ""):
        msg = f"  ☁️ Drive: {event}"
        if detail:
            msg += f" — {detail}"
        self._drive_logs.append(msg)
        self.log(msg)

    # ── Email send logging ────────────────────────────────────────────
    def log_email_event(self, event: str, detail: str = ""):
        msg = f"  📧 Email: {event}"
        if detail:
            msg += f" — {detail}"
        self._email_logs.append(msg)
        self.log(msg)

    # ── Save log file (APPEND mode) ───────────────────────────────────
    def save(self, directory: str = "reports") -> str:
        """Append this run's log to the daily log file. Returns its path."""
        os.makedirs(directory, exist_ok=True)
        today = date.today().isoformat()
        path = os.path.join(directory, f"run_log_{today}.txt")
        elapsed = time.time() - self._start_time

        lines = list(self._lines)

        # ── Key Usage Summary ─────────────────────────────────────────
        if self._key_stats:
            lines.append("")
            lines.append("═══════════════════════════════════════════════════════")
            lines.append("  KEY USAGE SUMMARY")
            lines.append("═══════════════════════════════════════════════════════")
            for name, stats in self._key_stats.items():
                status_icon = "✅" if stats["status"] == "alive" else "❌"
                lines.append(
                    f"  {status_icon} {name}: "
                    f"{stats['requests']} requests, "
                    f"{stats['successes']} successes, "
                    f"{stats['failures']} failures, "
                    f"{stats['rate_limits']} rate-limits"
                )

            total_requests = sum(s["requests"] for s in self._key_stats.values())
            total_successes = sum(s["successes"] for s in self._key_stats.values())
            alive_keys = sum(1 for s in self._key_stats.values() if s["status"] == "alive")
            dead_keys = sum(1 for s in self._key_stats.values() if s["status"] == "dead")
            lines.append(f"  ────────────────────────────────────")
            lines.append(f"  Total requests: {total_requests}")
            lines.append(f"  Total successes: {total_successes}")
            lines.append(f"  Keys alive: {alive_keys} | Keys dead: {dead_keys}")

        # ── Per-Job Analysis Log ──────────────────────────────────────
        if self._job_logs:
            lines.append("")
            lines.append("═══════════════════════════════════════════════════════")
            lines.append("  PER-JOB ANALYSIS LOG")
            lines.append("═══════════════════════════════════════════════════════")
            lines.append(f"  {'#':>3} | {'Platform':<10} | {'Status':<10} | {'Score':>5} | {'Fit':<15} | {'Key':<14} | {'Time':>5} | Title @ Company")
            lines.append(f"  {'─'*3}─┼─{'─'*10}─┼─{'─'*10}─┼─{'─'*5}─┼─{'─'*15}─┼─{'─'*14}─┼─{'─'*5}─┼─{'─'*40}")

            for i, j in enumerate(self._job_logs, 1):
                status_icon = {"success": "✅", "failed": "⚠️", "filtered": "🚫"}.get(j["status"], "❓")
                score_str = f"{j['score']}%" if j["status"] == "success" else "—"
                fit_str = j["fit"] if j["fit"] else "—"
                time_str = f"{j['time_s']}s" if j["time_s"] > 0 else "—"
                lines.append(
                    f"  {i:3} | {j['platform']:<10} | {status_icon} {j['status']:<8} | {score_str:>5} | "
                    f"{fit_str:<15} | {j['key_name']:<14} | {time_str:>5} | "
                    f"{j['title']} @ {j['company']}"
                )
                if j["error"]:
                    lines.append(f"       └─ Error: {j['error']}")

        # ── Platform Summary ──────────────────────────────────────────
        if self._platform_stats:
            lines.append("")
            lines.append("═══════════════════════════════════════════════════════")
            lines.append("  PLATFORM SUMMARY")
            lines.append("═══════════════════════════════════════════════════════")
            for platform, stats in self._platform_stats.items():
                success_rate = (stats["ai_scored"] / stats["total"] * 100) if stats["total"] > 0 else 0
                lines.append(
                    f"  {platform}: "
                    f"{stats['total']} total, "
                    f"{stats['ai_scored']} AI scored ({success_rate:.0f}%), "
                    f"{stats['ai_failed']} failed"
                    + (f", {stats['filtered']} pre-filtered" if stats["filtered"] else "")
                )

        # ── Errors ────────────────────────────────────────────────────
        if self._errors:
            lines.append("")
            lines.append("═══════════════════════════════════════════════════════")
            lines.append("  ERRORS")
            lines.append("═══════════════════════════════════════════════════════")
            for err in self._errors:
                lines.append(f"  ❌ {err}")

        # ── Section Summary ───────────────────────────────────────────
        lines.append("")
        lines.append("═══════════════════════════════════════════════════════")
        section_label = f"  {self._section} — SUMMARY" if self._section else "  FINAL SUMMARY"
        lines.append(section_label)
        lines.append("═══════════════════════════════════════════════════════")
        lines.append(f"  Runtime: {elapsed:.1f}s ({elapsed/60:.1f} min)")
        if self._key_stats:
            total_requests = sum(s["requests"] for s in self._key_stats.values())
            total_successes = sum(s["successes"] for s in self._key_stats.values())
            lines.append(f"  Total Gemini API calls: {total_requests}")
            lines.append(f"  Successful analyses: {total_successes}")
            if total_requests > 0:
                lines.append(f"  Success rate: {total_successes/total_requests*100:.1f}%")
            alive_keys = sum(1 for s in self._key_stats.values() if s["status"] == "alive")
            dead_keys = sum(1 for s in self._key_stats.values() if s["status"] == "dead")
            lines.append(f"  Keys used: {len(self._key_stats)} ({alive_keys} alive, {dead_keys} dead)")
        lines.append(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"═══════════════════════════════════════════════════════")

        # APPEND to file (multiple processes write to same log)
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        self.log(f"")
        self.log(f"📄 Run log saved → {path}")
        return path


# ── Singleton instance ────────────────────────────────────────────────
_instance: RunLogger | None = None


def get_logger(section: str = "") -> RunLogger:
    """Get or create the singleton RunLogger instance."""
    global _instance
    if _instance is None:
        _instance = RunLogger(section=section)
    return _instance


def new_logger(section: str) -> RunLogger:
    """Create a fresh RunLogger (use when starting a new section/process)."""
    global _instance
    _instance = RunLogger(section=section)
    return _instance
