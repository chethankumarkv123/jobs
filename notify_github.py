"""
notify_github.py
Dispatches the daily job finder report to chethankumarkv123@gmail.com via GitHub's
native notification system (Zero Password / Zero Secret required).

How it works:
1. Formats the daily report into a GitHub Issue with direct application links.
2. Directly tags and assigns @chethankumarkv123 to trigger GitHub's notification engine.
3. Uses the built-in GITHUB_TOKEN (provided automatically by GitHub Actions).
4. GitHub sends an email notification with the full report to the repo
   owner's registered email address (chethankumarkv123@gmail.com).
5. No Gmail App Password, SMTP setup, or personal credentials are required.
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("notify_github")
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def load_latest_json(json_path: str = "reports/latest.json") -> dict:
    if not os.path.exists(json_path):
        logger.error(f"Report file not found: {json_path}")
        return {}
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_markdown_body(data: dict) -> str:
    metadata = data.get("metadata", {})
    jobs = data.get("jobs", [])
    now_ist = datetime.now(IST_OFFSET).strftime("%d %b %Y, %I:%M %p IST")
    today_str = datetime.now(IST_OFFSET).strftime("%Y-%m-%d")

    # Categories
    today_str = datetime.now(IST_OFFSET).strftime("%Y-%m-%d")

    def is_discovered_today(j) -> bool:
        if j.get("previous_application_status") == "NEW":
            return True
        first_s = j.get("first_seen") or j.get("original_posting_date")
        if first_s and str(first_s)[:10] == today_str:
            return True
        return False

    sec_1 = [j for j in jobs if j.get("location_priority") == "bengaluru" and j.get("recommendation") == "APPLY" and j.get("previous_application_status") != "APPLIED" and is_discovered_today(j)]
    sec_2 = [j for j in jobs if j.get("location_priority") == "india_other" and j.get("recommendation") == "APPLY" and j.get("previous_application_status") != "APPLIED" and is_discovered_today(j)]
    sec_3 = [j for j in jobs if j.get("location_priority") == "worldwide_remote" and j.get("recommendation") == "APPLY" and j.get("previous_application_status") != "APPLIED" and is_discovered_today(j)]
    sec_4 = [j for j in jobs if j.get("previous_application_status") == "APPLIED" or (j.get("previous_application_status") == "PREVIOUSLY_REVIEWED" and not is_discovered_today(j))]
    sec_5 = [j for j in jobs if j.get("recommendation") == "REVIEW" and j not in sec_4]

    new_apply_count = len(sec_1) + len(sec_2) + len(sec_3)
    repo = os.environ.get("GITHUB_REPOSITORY", "chethankumarkv123/jobs")
    owner = repo.split("/")[0] if "/" in repo else "chethankumarkv123"

    md = []
    md.append(f"Hey @{owner} — Here are your verified daily job recommendations for today!\n")
    md.append(f"# 🎯 Daily Job Intelligence Report — {today_str}\n")
    md.append(f"> **Candidate:** Chethan Gowda | **Role:** Azure Cloud Engineer (4.2 yrs IT experience, LTIMindtree)")
    md.append(f"> **Run Timestamp:** {now_ist} | **New Confirmed Openings:** `{new_apply_count}` | **Review Openings:** `{len(sec_5)}`")
    md.append(f"> **Official Career Page Share:** `{metadata.get('official_career_page_share_confirmed', '100%')}` (Target >= 70%)\n")

    md.append(f"### 📱 View Interactive HTML Dashboard\n")
    md.append(f"- **[Click Here to Open latest.html](https://htmlpreview.github.io/?https://github.com/{repo}/blob/main/reports/latest.html)**")
    md.append(f"- **[Direct Raw HTML File](https://raw.githubusercontent.com/{repo}/main/reports/latest.html)**\n")

    # Section 1: Bengaluru Confirmed
    md.append(f"## 1. 🏢 Bengaluru — Confirmed Matches (Priority 1: Highest)")
    if sec_1:
        md.append("| Company | Role | Work Arrangement | Match Score | Direct Application URL |")
        md.append("| :--- | :--- | :--- | :---: | :--- |")
        for j in sec_1:
            app_url = j.get("official_application_url") or j.get("source_url")
            md.append(f"| **{j.get('company')}** | {j.get('job_title')} | `{j.get('work_arrangement')}` | **`{j.get('estimated_match_score')}`** | [Apply Directly ↗]({app_url}) |")
    else:
        md.append("_No new confirmed Bengaluru openings posted in the last 24h._")
    md.append("")

    # Section 2: Other India Confirmed
    md.append(f"## 2. 🇮🇳 Other Indian Locations — Confirmed Matches (Priority 2)")
    if sec_2:
        md.append("| Company | Role | Location & Arrangement | Match Score | Direct Application URL |")
        md.append("| :--- | :--- | :--- | :---: | :--- |")
        for j in sec_2:
            app_url = j.get("official_application_url") or j.get("source_url")
            md.append(f"| **{j.get('company')}** | {j.get('job_title')} | {j.get('location')} ({j.get('work_arrangement')}) | **`{j.get('estimated_match_score')}`** | [Apply Directly ↗]({app_url}) |")
    else:
        md.append("_No other new India confirmed openings found today._")
    md.append("")

    # Section 3: Worldwide Remote Open to India
    md.append(f"## 3. 🌐 Worldwide Remote — Confirmed Matches Open to India (Priority 3)")
    if sec_3:
        md.append("| Company | Role | Match Score | Direct Application URL |")
        md.append("| :--- | :--- | :---: | :--- |")
        for j in sec_3:
            app_url = j.get("official_application_url") or j.get("source_url")
            md.append(f"| **{j.get('company')}** | {j.get('job_title')} | **`{j.get('estimated_match_score')}`** | [Apply Directly ↗]({app_url}) |")
    else:
        md.append("_No new worldwide remote confirmed openings open to India today._")
    md.append("")

    # Section 4: Previously Reviewed / Applied
    if sec_4:
        md.append(f"## 4. 🛡️ Anti-Duplicate Tracker ({len(sec_4)} Openings Monitored)")
        md.append("<details><summary>Click to expand previously reviewed / applied openings</summary>\n")
        md.append("| Company | Role | Status | Note |")
        md.append("| :--- | :--- | :---: | :--- |")
        for j in sec_4[:20]:
            md.append(f"| {j.get('company')} | {j.get('job_title')} | `{j.get('previous_application_status')}` | {j.get('duplicate_check_result', '')[:40]} |")
        md.append("\n</details>\n")

    # Section 5: Date Unverified / Review Manually
    if sec_5:
        md.append(f"## 5. 🔍 Date Unverified / Review Manually ({len(sec_5)} Leads)")
        md.append("<details><summary>Click to view manual review openings</summary>\n")
        md.append("| Company | Role | Location | Match Score | Link |")
        md.append("| :--- | :--- | :--- | :---: | :--- |")
        for j in sec_5:
            url = j.get("official_application_url") or j.get("source_url")
            md.append(f"| {j.get('company')} | {j.get('job_title')} | {j.get('location')} | `{j.get('estimated_match_score')}` | [Review Link ↗]({url}) |")
        md.append("\n</details>\n")

    md.append("---")
    md.append("*Sent automatically via Antigravity Personalized Job Finder — Zero password required.*")

    return "\n".join(md)


def create_github_issue(title: str, body: str, token: str, repo: str) -> bool:
    """Creates an issue using GitHub REST API, assigning the owner so GitHub delivers an email notification."""
    api_url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "JobFinder-Notifier"
    }

    owner = repo.split("/")[0] if "/" in repo else "chethankumarkv123"

    # 1. Close older daily run issues to keep the tracker clean
    try:
        req_list = urllib.request.Request(f"{api_url}?state=open&labels=daily-job-report", headers=headers)
        with urllib.request.urlopen(req_list) as resp:
            old_issues = json.loads(resp.read().decode("utf-8"))
            for old in old_issues:
                close_url = f"{api_url}/{old['number']}"
                close_data = json.dumps({"state": "closed"}).encode("utf-8")
                req_close = urllib.request.Request(close_url, data=close_data, headers=headers, method="PATCH")
                urllib.request.urlopen(req_close)
                logger.info(f"Closed previous daily report issue #{old['number']}.")
    except Exception as e:
        logger.warning(f"Could not close old issues (harmless): {e}")

    # 2. Create the new issue with explicit assignment
    payload = {
        "title": title,
        "body": body,
        "assignees": [owner],
        "labels": ["daily-job-report", "azure-cloud-jobs"]
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(api_url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            issue_url = res_data.get("html_url")
            logger.info(f"Created daily report issue: {issue_url}")
            logger.info(f"Assigned to @{owner} — GitHub email notification dispatched to chethankumarkv123@gmail.com.")
            return True
    except urllib.error.HTTPError as e:
        logger.error(f"GitHub API Error: {e.code} {e.reason}")
        try:
            err_body = e.read().decode("utf-8")
            logger.error(f"Error body: {err_body}")
        except Exception:
            pass
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating GitHub issue: {e}")
        return False


def main():
    data = load_latest_json()
    if not data:
        logger.warning("No data found in reports/latest.json.")
        return

    today_str = datetime.now(IST_OFFSET).strftime("%Y-%m-%d")
    jobs = data.get("jobs", [])
    new_apply_count = sum(1 for j in jobs if j.get("recommendation") == "APPLY" and j.get("previous_application_status") == "NEW")

    title = f"🎯 Daily Azure Cloud Jobs ({today_str}): {new_apply_count} Confirmed Openings"
    body = build_markdown_body(data)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "chethankumarkv123/jobs")

    if not token:
        logger.info(
            "Running outside GitHub Actions or no GITHUB_TOKEN provided.\n"
            "On GitHub Actions, GITHUB_TOKEN is injected automatically and sends this report\n"
            "straight to chethankumarkv123@gmail.com without needing any personal password."
        )
        return

    success = create_github_issue(title, body, token, repo)
    if success:
        logger.info("Report delivered successfully via GitHub Native Notifications.")


if __name__ == "__main__":
    main()
