# Bangalore Startup Job Finder

Automated daily job discovery and evaluation engine for **Azure Cloud Engineer** (4+ years IT experience). Runs daily at **08:00 AM Asia/Kolkata (IST)**, filters vacancies with strict location priority and verified freshness, and emails the HTML report to `chethankumarkv123@gmail.com`.

---

## Architecture & Priority Hierarchy

* **Priority 1: Bengaluru / Bangalore** — Onsite, hybrid, and remote roles (Hasura, Zerodha, Postman, Razorpay, BrowserStack, Sarvam AI, Atlan, Jupiter, Pixxel, CRED).
* **Priority 2: Anywhere in India** — Engineering hubs in Chennai, Pune, Hyderabad, Mumbai, Delhi NCR (Freshworks, Persistent, HighRadius, Zoho).
* **Priority 3: Worldwide Remote** — Remote-first global companies (Canonical, GitLab, Elastic, CrowdStrike) explicitly hiring candidates residing in India.
* **Priority 4: LinkedIn Jobs** — Dedicated section for verified past-24-hours engineering openings.
* **Priority 5: Wellfound** — Early-stage Bangalore startups (with degree/backlog exemption).

---

## Automated Schedule (08:00 AM IST)

### 1. GitHub Actions (Cloud — Runs 24/7 without PC)
* Configured in [`.github/workflows/daily_jobs.yml`](.github/workflows/daily_jobs.yml).
* Triggers every day at `02:30 UTC` (**08:00 AM IST**).
* Can be triggered on-demand with one tap from the **GitHub Mobile App** or Web UI (`Actions` &rarr; `Run workflow`).

### 2. Windows Task Scheduler (Local PC Backup)
* Task Name: `BangaloreStartupJobFinderDaily`
* Schedule: Daily at `08:00 AM IST`.
* Re-register or update via:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\schedule_task.ps1 -Time "08:00"
  ```

---

## Email Notification Setup

To receive the interactive HTML report directly at `chethankumarkv123@gmail.com`:

1. Go to your Google Account: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
2. Create an App Password named **JobFinder**.
3. Add it as a GitHub Secret in this repository:
   * Go to **Settings** &rarr; **Secrets and variables** &rarr; **Actions**.
   * Click **New repository secret**.
   * Name: `GMAIL_APP_PASSWORD`
   * Value: `<your-16-character-app-password>`
4. *(Optional for local runs)*: Set in your local terminal:
   ```powershell
   [System.Environment]::SetEnvironmentVariable('GMAIL_APP_PASSWORD', 'your_password', 'User')
   ```

---

## Daily Reports Generated

* **Interactive Dashboard**: `reports/latest.html` (tap-to-apply links, mobile-ready)
* **Spreadsheet Table**: `reports/latest.csv`
* **JSON Payload**: `reports/latest.json`
* **Dated Archives**: `reports/archive/`
* **Deduplication Audit History**: `data/jobs_history.json`
