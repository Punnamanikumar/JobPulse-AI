# 🤖 JobPulse AI — AI-Powered Daily Job Match Tracker

> **🚀 Fully automated AI job matching — runs daily on GitHub Actions, zero manual effort.**

**An AI automation that scrapes 100+ jobs daily from LinkedIn + Naukri, scores each one against your resume using Google Gemini AI (in a single API call), uploads reports to Google Drive, and emails you a ranked Excel report with match scores, missing skills, and resume tailoring tips — runs entirely on GitHub Actions for free.**

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python) ![Gemini AI](https://img.shields.io/badge/Gemini_AI-2.5_Flash-orange?logo=google) ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated-green?logo=githubactions) ![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

- 🔍 **Multi-Platform Scraping** — LinkedIn + Naukri via Apify API (run both or just one)
- 🤖 **AI-Powered Scoring** — Gemini 2.5 Flash-Lite analyzes each job against your full resume
- 📦 **Batch AI Mode** — All jobs scored in a single API call (no rate limits!)
- 🔄 **Auto-Retry** — Failed jobs automatically retried individually
- 📄 **Multi-Format Resume** — Supports PDF, DOCX, TXT, and MD resume files
- 📊 **Smart Excel Reports** — Match Score, Role Fit, AI Summary, Missing Skills, Resume Tips
- 📧 **Gmail API Email** — OAuth2-secured email delivery (no app passwords)
- ☁️ **Google Drive Uploads** — Reports auto-uploaded to organized date folders
- 📝 **End-to-End Run Logs** — Detailed execution logs attached to email and uploaded to Drive
- 🛡️ **Failover & Alerts** — Email alerts on API failures
- ⏰ **Fully Automated** — GitHub Actions cron, zero manual effort
- ⚡ **100% Free** — All services used are free tier

---

## 📁 Project Structure

```
jobpulse-ai/
├── .github/workflows/
│   └── daily_job_report.yml        ← GitHub Actions cron (3 AM IST)
├── scripts/
│   ├── config.py                   ← 🔧 Centralized configuration
│   ├── resume_loader.py            ← 📄 Multi-format resume loader (PDF/DOCX/TXT/MD)
│   ├── scrape_and_score.py         ← LinkedIn scraper + scorer + Excel builder
│   ├── scrape_naukri.py            ← Naukri scraper (reuses scoring logic)
│   ├── ai_analyzer.py              ← 🤖 Gemini AI job-resume matching
│   ├── gemini_token.py             ← Gemini API key manager (rate limiting)
│   ├── apify_token.py              ← Apify token manager
│   ├── send_email.py               ← Gmail API sender + Drive uploader
│   ├── drive_uploader.py           ← Google Drive upload & folder sharing
│   ├── google_auth.py              ← OAuth2 credentials builder
│   ├── setup_google_auth.py        ← One-time OAuth2 setup wizard
│   └── run_logger.py               ← End-to-end execution logger
├── resume/
│   ├── sample_profile.txt          ← Sample resume (replace with yours)
│   └── your_resume.pdf/docx/txt    ← Your resume file (gitignored)
├── run.py                          ← 🚀 Single entry point
├── requirements.txt
├── .env.example                    ← Environment variable template
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Punnamanikumar/JobPulse-AI.git
cd JobPulse-AI
pip install -r requirements.txt
```

### 2. Add Your Resume

Copy your resume into the `resume/` directory. Supported formats:

| Format | File Types | Notes |
|--------|-----------|-------|
| **PDF** | `.pdf` | Text-based PDFs only (scanned images won't work) |
| **Word** | `.docx` | Microsoft Word format |
| **Text** | `.txt`, `.md` | Plain text or Markdown |

The system auto-detects your resume file. See `resume/sample_profile.txt` for the expected format and tips.

> 💡 **Tip:** The more detailed your resume, the more accurate the AI matching will be. Include specific technologies, years of experience, and measurable achievements.

### 3. Get API Keys

You need **3 services** set up (all free or very cheap):

---

#### 🔑 Gemini API Key (Free)

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click **"Create API Key"**
4. Copy the key (starts with `AIzaSy...`)

> The free tier gives you **15 requests per minute** and **1,000 requests per day** — more than enough for daily job matching.

---

#### 🔑 Apify API Token (Free — $5 credits for new users)

1. Go to [Apify Console](https://console.apify.com)
2. Sign up for a free account (you get **$5 free credits** on signup)
3. Go to **Settings** → **Integrations** → **API Tokens**
4. Click **"+ Create token"**
5. Copy the token (starts with `apify_api_...`)

> Apify is used to scrape LinkedIn and Naukri job listings. New users get **$5 free credits** on signup. LinkedIn scraping costs ~$0.03–0.05 per run, Naukri uses minimal compute credits. The free credits last several months of daily usage.

---

#### 🔑 Google OAuth2 (Gmail API + Drive — Free)

This is needed to send emails via Gmail and upload reports to Google Drive.

**Step A: Create Google Cloud Project**

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click the project dropdown → **"New Project"**
3. Name it `JobPulse AI` → Click **"Create"**

**Step B: Enable APIs**

1. Go to **APIs & Services** → **Library**
2. Search **"Gmail API"** → Click → **Enable**
3. Search **"Google Drive API"** → Click → **Enable**

**Step C: Configure OAuth Consent Screen**

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **"External"** → Click **"Create"**
3. Fill in:
   - App name: `JobPulse AI`
   - User support email: Your email
   - Developer contact: Your email
4. Click **"Save and Continue"** through all steps
5. On **"Test users"** page → **"Add Users"** → Add your Gmail address
6. Click **"Save and Continue"** → **"Back to Dashboard"**

**Step D: Create OAuth Credentials**

1. Go to **APIs & Services** → **Credentials**
2. Click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. Application type: **"Desktop app"**
4. Name: `JobPulse AI Desktop`
5. Click **"Create"**
6. Download the JSON file → Save as `credentials.json` in the project root

**Step E: Run Setup Wizard**

```bash
python scripts/setup_google_auth.py
```

This opens a browser window for authorization. After allowing access, you'll get:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

> ⚠️ The refresh token does NOT expire as long as the app runs at least once every 6 months (the daily cron ensures this).

---

### 4. Configure Environment

Copy the template and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# API Keys
GEMINI_API_KEY=AIzaSy...your_key_here
APIFY_TOKEN=apify_api_...your_token_here

# Platform: "both", "linkedin", or "naukri"
PLATFORMS=both

# AI Analysis: "true" for Gemini AI, "false" for keyword-based
AI_ANALYSIS=true

# Search keywords (comma-separated) — what jobs to search for
# If not set, defaults to Node.js/MERN/Full Stack searches
SEARCH_KEYWORDS=Backend Developer Node.js, MERN Stack Developer, Full Stack Developer
SEARCH_LOCATION=India

# Your name (optional — shown in reports and emails)
USER_NAME=Your Name

# Email
GMAIL_USER=your-email@gmail.com
RECIPIENT_EMAIL=your-email@gmail.com

# Google OAuth2 (from setup_google_auth.py)
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
GOOGLE_REFRESH_TOKEN=1//xxxxx
```

### 5. Run Locally

```bash
# Run everything (scrape + email)
python run.py

# LinkedIn only
python run.py --linkedin

# Naukri only
python run.py --naukri

# Scrape without sending email
python run.py --no-email
```

### 6. Set Up GitHub Actions (Automated Daily Runs)

This is the **recommended way** to run JobPulse AI — it runs automatically every day on GitHub's free servers.

**Step A: Add your resume to the repo**

Since your resume is gitignored by default, you need to force-add it:

```bash
git add -f resume/your_resume.pdf  # or .docx or .txt
```

> ⚠️ Your resume will be in your GitHub repo. If it's a **private repo**, this is fine. If public, consider using a `.txt` version with only professional info.

**Step B: Add secrets**

In your repo → **Settings** → **Secrets and variables** → **Actions**, add these secrets:

| Secret Name | Required | Value |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Your Gemini API key |
| `APIFY_TOKEN` | ✅ | Your Apify token |
| `GMAIL_USER` | ✅ | Sender Gmail address |
| `RECIPIENT_EMAIL` | ✅ | Where to receive reports |
| `GOOGLE_CLIENT_ID` | ✅ | OAuth2 Client ID |
| `GOOGLE_CLIENT_SECRET` | ✅ | OAuth2 Client Secret |
| `GOOGLE_REFRESH_TOKEN` | ✅ | OAuth2 Refresh Token |
| `AI_ANALYSIS` | ❌ | `true` (default) |
| `PLATFORMS` | ❌ | `both` / `linkedin` / `naukri` (default: `both`) |
| `BATCH_AI` | ❌ | `true` (default) — all jobs in 1 API call |
| `SEARCH_KEYWORDS` | ❌ | Comma-separated job keywords (default: Node.js searches) |
| `SEARCH_LOCATION` | ❌ | Job location (default: `India`) |
| `USER_NAME` | ❌ | Your name (shown in reports) |
| `JOB_COUNT` | ❌ | Max jobs to analyze (default: `20`) |

**Step C: Push and deploy**

```bash
git add .
git commit -m "Setup JobPulse AI"
git push
```

The workflow runs **automatically at 3 AM IST daily**. You can also:
- **Trigger manually**: Actions tab → **Daily Job Report** → **Run workflow**
- **Change schedule**: Edit the cron in `.github/workflows/daily_job_report.yml` (see [⏰ Schedule](#-schedule) section)

---

## 🔄 How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Actions (3 AM IST)                    │
│                        or: python run.py                         │
├─────────────┬─────────────────┬─────────────────────────────────┤
│  Step 1     │  Step 2         │  Step 3                         │
│  LinkedIn   │  Naukri         │  Email + Drive                  │
│  Scraper    │  Scraper        │  Upload & Send                  │
│  (100 jobs) │  (100 jobs)     │  (3 attachments + Drive links)  │
└──────┬──────┴────────┬────────┴──────────┬──────────────────────┘
       │               │                   │
       ▼               ▼                   ▼
  ┌──────────────────────────┐   ┌──────────────────────┐
  │   AI_ANALYSIS = true?    │   │  Google Drive Upload  │
  ├──────────┬───────────────┤   │  + Folder Sharing     │
  │  YES 🤖  │  NO 📊        │   │  + Gmail API Send     │
  │  Gemini  │  Keyword      │   │  + Run Log Attached   │
  │  AI      │  Matching     │   └──────────────────────┘
  └────┬─────┴──────┬────────┘
       │            │
       ▼            ▼
   Top 20 jobs ranked by Match Score
```

1. **Your Resume** is loaded (PDF, DOCX, or TXT — auto-detected)
2. **Scrape** — Fetches jobs from LinkedIn and/or Naukri using Apify
3. **Score** — Each job is analyzed by Gemini AI against your resume, or keyword-matched (fallback)
4. **Upload** — Reports + run log uploaded to Google Drive (organized by date)
5. **Email** — Sends email via Gmail API with `.xlsx` reports + run log attached + Drive links

---

## 🤖 AI Analysis (Gemini-Powered)

When `AI_ANALYSIS=true`, each job is analyzed by **Google Gemini 2.5 Flash-Lite** against your full resume.

### Batch Mode (Default — Recommended)

By default, **all jobs are sent to Gemini in a single API call** (`BATCH_AI=true`). This:
- ✅ Avoids rate limits completely (only 1 API call instead of 20)
- ✅ Runs 10x faster
- ✅ Works perfectly on the free Gemini tier

Set `BATCH_AI=false` in `.env` to switch to per-job analysis (legacy mode).

### AI Output Fields

| Field | Description |
|-------|-------------|
| **Match Score (%)** | 0–100% match between your resume and the job |
| **Role Fit** | Strong Fit · Moderate Fit · Weak Fit · Not a Fit |
| **AI Summary** | 2–3 sentence assessment of why you match (or don't) |
| **Missing Skills** | Skills you'd need to develop for this role |
| **Resume Tips** | Specific suggestions to tailor your resume for this job |

### Keyword Scoring (Fallback)

When `AI_ANALYSIS=false`, jobs are scored using a weighted keyword system based on your configured skills. You can customize the skill categories in `scrape_and_score.py`:

- **MUST_HAVE** — Core skills (15 pts each)
- **BACKEND_PLUS** — Secondary skills (5 pts each)
- **NICE_TO_HAVE** — Bonus skills (2 pts each)

---

## ☁️ Google Drive Integration

Reports are automatically uploaded to Google Drive:

```
JobPulse Reports/
├── 2026-02-28/
│   ├── LinkedIn_India_Jobs_2026-02-28.xlsx
│   ├── Naukri_India_Jobs_2026-02-28.xlsx
│   └── run_log_2026-02-28.txt
├── 2026-03-01/
│   └── ...
```

- **Auto-shared** with your recipient email (writer access)
- **Drive link** included in the email body
- **Run log** uploaded alongside reports

---

## 📧 What You Receive Daily

**Subject:** `🇮🇳 LinkedIn + Naukri India Job Report — YYYY-MM-DD`

**Email body:** Top 5 matches from each platform with AI scores + Drive folder link

**Attachments (3):**
- `LinkedIn_India_Jobs_YYYY-MM-DD.xlsx`
- `Naukri_India_Jobs_YYYY-MM-DD.xlsx`
- `run_log_YYYY-MM-DD.txt` — full execution log

### Excel Report Columns (AI Mode)

| # | Column | Description |
|---|--------|-------------|
| 1 | Job Title | Position name |
| 2 | Company Name | Hiring company |
| 3 | Location | City/Region |
| 4 | Work Mode | Remote / Hybrid / Onsite |
| 5 | Posted Date | When the job was listed |
| 6 | Exp Required | Years of experience needed |
| 7 | Key Skills | Technologies mentioned |
| 8 | Match Score (%) | AI-generated match 0–100% |
| 9 | Role Fit | Strong / Moderate / Weak / Not a Fit |
| 10 | AI Summary | Why you match or don't |
| 11 | Missing Skills | What you'd need to learn |
| 12 | Resume Tips | How to tailor your resume |
| 13 | Job Link | Direct link to apply |

---

## 🔧 Customisation

| What | Where |
|------|-------|
| **Search keywords** | `SEARCH_KEYWORDS` in `.env` |
| **Search location** | `SEARCH_LOCATION` in `.env` (default: India) |
| Platform selection | `PLATFORMS` in `.env` (`both` / `linkedin` / `naukri`) |
| LinkedIn search queries | `SEARCH_URLS` in `scrape_and_score.py` (fallback) |
| Naukri search URLs | `NAUKRI_SEARCH_URLS` in `scrape_naukri.py` (fallback) |
| Number of results | `"count": 100` / `"maxItems": 100` in scraper files |
| Schedule | `cron` in `.github/workflows/daily_job_report.yml` |
| Resume | Any file in `resume/` (PDF, DOCX, TXT, MD) |
| AI vs Keyword scoring | `AI_ANALYSIS` in `.env` |
| Batch vs Single AI mode | `BATCH_AI` in `.env` (default: `true`) |
| Skills & keyword weights | `MUST_HAVE`, `BACKEND_PLUS`, `NICE_TO_HAVE` in `scrape_and_score.py` |
| Max jobs to analyze | `JOB_COUNT` in `.env` (default: 20) |
| Drive folder name | `ROOT_FOLDER_NAME` in `drive_uploader.py` |
| Your name in reports | `USER_NAME` in `.env` |

---

## ⏰ Schedule

The default schedule is **3:00 AM IST** (9:30 PM UTC). You can change this by editing the cron expression in `.github/workflows/daily_job_report.yml`:

```yaml
schedule:
  - cron: "30 21 * * *"  # ← Change this
```

### Common Cron Examples

| When | Cron Expression | UTC Time |
|------|----------------|----------|
| 3:00 AM IST | `30 21 * * *` | 9:30 PM UTC |
| 6:00 AM IST | `30 0 * * *` | 12:30 AM UTC |
| 8:00 AM IST | `30 2 * * *` | 2:30 AM UTC |
| 9:00 AM EST | `0 14 * * *` | 2:00 PM UTC |
| 7:00 AM PST | `0 15 * * *` | 3:00 PM UTC |
| 8:00 AM GMT | `0 8 * * *` | 8:00 AM UTC |
| Mon-Fri only | `30 21 * * 1-5` | Weekdays at 9:30 PM UTC |
| Every 12 hours | `0 */12 * * *` | Twice daily |

> **Cron format:** `minute hour day month weekday` (all in UTC)
>
> Use [crontab.guru](https://crontab.guru) to create your own schedule.

---

## 💰 Cost

| Service | Cost |
|---------|------|
| GitHub Actions | **Free** (~5 min/day) |
| Apify (LinkedIn + Naukri) | **Free** ($5 credits on signup, lasts months) |
| Gemini AI | **Free** (free tier: 1000 req/day) |
| Gmail API | **Free** (OAuth2) |
| Google Drive | **Free** (15 GB) |
| **Total** | **Free** (with free tier credits) |

---

## 🐛 Troubleshooting

| Problem | Fix |
|---------|-----|
| Email not arriving | Check spam; verify OAuth2 credentials with `python scripts/setup_google_auth.py` |
| OAuth2 "access_denied" | Add sender email as test user in Google Cloud Console → OAuth consent screen |
| Refresh token expired | Re-run `python scripts/setup_google_auth.py` to get a new one |
| Drive upload fails | Check `GOOGLE_CLIENT_ID`/`SECRET`/`REFRESH_TOKEN` secrets; run setup wizard |
| Apify error | Check token in Secrets; verify credits at [console.apify.com](https://console.apify.com) |
| Gemini 429 errors | Normal — rate limiting handles this automatically. Wait and retry |
| AI scoring shows "AI Unavailable" | Check Gemini key at [aistudio.google.com](https://aistudio.google.com) |
| No jobs found | LinkedIn may have throttled — try again or adjust search URLs |
| PDF resume not loading | Ensure it's a text-based PDF, not a scanned image |
| ModuleNotFoundError | Run `pip install -r requirements.txt` to install all dependencies |

---

## 🛡️ Security

- All API keys and credentials stored as **GitHub Secrets** (encrypted)
- `.env`, `credentials.json`, `token.json` are **gitignored** — never committed
- OAuth2 refresh token used instead of app passwords (more secure)
- Your resume is **gitignored** — only `sample_profile.txt` is committed
- Gemini API keys are masked in logs

---

## 📜 Tech Stack

| Technology | Usage |
|-----------|-------|
| Python 3.9+ | Core language |
| Google Gemini AI | Job-resume matching |
| Gmail API (OAuth2) | Email delivery |
| Google Drive API | Report storage & sharing |
| Apify | Web scraping (LinkedIn + Naukri) |
| openpyxl | Excel report generation |
| PyPDF2 | PDF resume parsing |
| python-docx | DOCX resume parsing |
| GitHub Actions | CI/CD automation |

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test locally: `python run.py --no-email`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

Built with ❤️ by **[Mani Kumar Punna](https://manikumarportfolio.netlify.app/)** · [GitHub Repo](https://github.com/Punnamanikumar/JobPulse-AI) · Open Source · Contributions Welcome
