"""
Job History Tracker — tracks previously seen jobs to highlight NEW vs repeated.

Stores a JSON file in reports/job_history.json with:
  - Job hash (title + company)
  - First seen date
  - Last seen date
  - Platform
  - Match score (latest)

Usage:
    from job_history import JobHistory
    history = JobHistory()
    status = history.check_job(title, company)  # "✨ NEW" or "🔁 Seen 2d ago"
    history.save()
"""

from __future__ import annotations

import json
import hashlib
from datetime import date, datetime
from pathlib import Path


HISTORY_FILE = Path(__file__).parent.parent / "reports" / "job_history.json"
MAX_HISTORY_DAYS = 30  # Remove jobs not seen in 30 days


class JobHistory:
    """Track job listings across days to identify new vs repeated jobs."""

    def __init__(self, path: str = ""):
        self.path = Path(path) if path else HISTORY_FILE
        self.data: dict[str, dict] = {}
        self.stats = {"new": 0, "seen": 0}
        self._load()

    def _load(self):
        """Load existing history from JSON file."""
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.data = {}

    def _job_key(self, title: str, company: str) -> str:
        """Generate a unique key for a job listing."""
        normalized = f"{title.lower().strip()[:60]}|{company.lower().strip()[:40]}"
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def check_job(self, title: str, company: str, platform: str = "",
                  score: int = 0) -> str:
        """Check if a job has been seen before and update history.

        Returns a status string:
          - "✨ NEW"           — first time seeing this job
          - "🔁 Seen 1d ago"   — seen yesterday
          - "🔁 Seen 3d ago"   — seen 3 days ago

        Also updates the history entry with latest seen date and score.
        """
        key = self._job_key(title, company)
        today = date.today().isoformat()

        if key in self.data:
            entry = self.data[key]
            first_seen = entry.get("first_seen", today)
            entry["last_seen"] = today
            entry["times_seen"] = entry.get("times_seen", 1) + 1
            if score > 0:
                entry["score"] = score
            if platform:
                entry["platform"] = platform

            # Calculate days since first seen
            try:
                first_date = datetime.strptime(first_seen, "%Y-%m-%d").date()
                days_ago = (date.today() - first_date).days
                if days_ago == 0:
                    status = "🔁 Seen today"
                elif days_ago == 1:
                    status = "🔁 Seen 1d ago"
                else:
                    status = f"🔁 Seen {days_ago}d ago"
            except ValueError:
                status = "🔁 Seen before"

            self.stats["seen"] += 1
            return status
        else:
            # New job!
            self.data[key] = {
                "title": title[:80],
                "company": company[:50],
                "first_seen": today,
                "last_seen": today,
                "times_seen": 1,
                "platform": platform,
                "score": score,
            }
            self.stats["new"] += 1
            return "✨ NEW"

    def get_stats(self) -> dict:
        """Return stats about the current batch: how many new vs seen."""
        return {
            "new": self.stats["new"],
            "seen": self.stats["seen"],
            "total_tracked": len(self.data),
        }

    def cleanup_old(self, max_days: int = MAX_HISTORY_DAYS):
        """Remove entries not seen in the last max_days days."""
        cutoff = date.today()
        to_remove = []
        for key, entry in self.data.items():
            try:
                last_seen = datetime.strptime(entry["last_seen"], "%Y-%m-%d").date()
                if (cutoff - last_seen).days > max_days:
                    to_remove.append(key)
            except (ValueError, KeyError):
                to_remove.append(key)

        for key in to_remove:
            del self.data[key]

        return len(to_remove)

    def save(self):
        """Save history to JSON file, cleaning up old entries first."""
        removed = self.cleanup_old()

        # Ensure reports/ directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

        return removed


# ═══════════════════════════════════════════════════════════════════════
# Test
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("  Job History — Quick Test")
    print("=" * 50)

    h = JobHistory("/tmp/test_job_history.json")

    # First time — should be NEW
    s1 = h.check_job("MERN Stack Developer", "Infosys", "LinkedIn", 85)
    assert "NEW" in s1, f"Expected NEW, got {s1}"
    print(f"✅ First check: {s1}")

    # Second time — should be Seen
    s2 = h.check_job("MERN Stack Developer", "Infosys", "LinkedIn", 85)
    assert "Seen" in s2, f"Expected Seen, got {s2}"
    print(f"✅ Second check: {s2}")

    # Different job — should be NEW
    s3 = h.check_job("Python Developer", "Google", "LinkedIn", 90)
    assert "NEW" in s3, f"Expected NEW, got {s3}"
    print(f"✅ Different job: {s3}")

    # Stats
    stats = h.get_stats()
    print(f"✅ Stats: {stats}")
    assert stats["new"] == 2
    assert stats["seen"] == 1

    # Save
    h.save()
    print(f"✅ Saved to /tmp/test_job_history.json")

    # Reload and check persistence
    h2 = JobHistory("/tmp/test_job_history.json")
    s4 = h2.check_job("MERN Stack Developer", "Infosys")
    assert "Seen" in s4
    print(f"✅ After reload: {s4}")

    print("\n✅ All tests passed!")

    # Cleanup
    Path("/tmp/test_job_history.json").unlink(missing_ok=True)
