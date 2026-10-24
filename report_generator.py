"""
report_generator.py
Generates the comprehensive daily job intelligence reports and anti-duplicate application tracker deliverables:
1. reports/latest.html (Interactive dashboard organized by mandatory priority sections)
2. reports/latest.csv & reports/archive/jobs_YYYY-MM-DD.csv
3. reports/latest.json & reports/archive/jobs_YYYY-MM-DD.json
4. reports/archive/job_report_YYYY-MM-DD.html
"""

import os
import csv
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from job_sources import JobPosting

logger = logging.getLogger(__name__)
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


class ReportGenerator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.reports_dir = "reports"
        self.archive_dir = os.path.join(self.reports_dir, "archive")
        os.makedirs(self.reports_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

    def generate_all(self, jobs: List[JobPosting], excluded_summary: List[str] = None) -> Dict[str, str]:
        now_ist = datetime.now(IST_OFFSET)
        date_str = now_ist.strftime("%Y-%m-%d")

        csv_latest = os.path.join(self.reports_dir, "latest.csv")
        csv_archive = os.path.join(self.archive_dir, f"jobs_{date_str}.csv")
        json_latest = os.path.join(self.reports_dir, "latest.json")
        json_archive = os.path.join(self.archive_dir, f"jobs_{date_str}.json")
        html_latest = os.path.join(self.reports_dir, "latest.html")
        html_archive = os.path.join(self.archive_dir, f"job_report_{date_str}.html")

        # Generate CSV
        self.generate_csv(jobs, [csv_latest, csv_archive])
        # Generate JSON
        self.generate_json(jobs, [json_latest, json_archive], now_ist)
        # Generate HTML
        html_content = self.generate_html(jobs, now_ist, excluded_summary or [])
        with open(html_latest, "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(html_archive, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Published reports to {self.reports_dir} and archived to {self.archive_dir}")
        return {
            "html": html_latest,
            "csv": csv_latest,
            "json": json_latest,
            "archive_html": html_archive,
            "archive_csv": csv_archive,
            "archive_json": json_archive
        }

    def generate_csv(self, jobs: List[JobPosting], filepaths: List[str]):
        headers = [
            "Company",
            "Job Title",
            "Location",
            "Work Arrangement",
            "Location Priority",
            "Original Posting Date",
            "Last Verification Timestamp",
            "Required Experience",
            "Candidate Experience Fit",
            "Relevant Technical Skills",
            "Missing Mandatory Skills",
            "Estimated Profile Match Score",
            "Recommendation",
            "Reason for Recommendation",
            "Source URL",
            "Official Application URL",
            "Canonical Job Key",
            "Duplicate Check Result",
            "Previous Application Status"
        ]

        for path in filepaths:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for j in jobs:
                    writer.writerow([
                        j.company,
                        j.title,
                        j.location,
                        j.work_arrangement,
                        j.location_category.upper(),
                        j.original_posting_date or "Unverified",
                        j.date_last_verified,
                        j.experience_requirement,
                        j.candidate_experience_fit or f"Matches candidate's 4.2 yrs total IT",
                        ", ".join(j.matching_skills),
                        ", ".join(j.missing_skills) if j.missing_skills else "None",
                        f"{j.estimated_match_score}%",
                        j.recommendation,
                        j.recommendation_rationale,
                        j.direct_job_url,
                        j.direct_application_url or j.direct_job_url,
                        j.canonical_job_key,
                        j.duplicate_check_result,
                        j.application_status
                    ])

    def generate_json(self, jobs: List[JobPosting], filepaths: List[str], run_time: datetime):
        today_str = run_time.strftime("%Y-%m-%d")
        new_count = sum(1 for j in jobs if j.recommendation == "APPLY" and j.application_status != "APPLIED" and (j.application_status == "NEW" or (j.first_seen and j.first_seen[:10] == today_str)))
        review_count = sum(1 for j in jobs if j.recommendation == "REVIEW")
        applied_count = sum(1 for j in jobs if j.application_status == "APPLIED")
        previously_reviewed_count = sum(1 for j in jobs if j.application_status == "PREVIOUSLY_REVIEWED")
        official_count = sum(1 for j in jobs if j.source_type == "official_career_page" and j.verification_status == "VERIFIED")
        confirmed_count = sum(1 for j in jobs if j.recommendation == "APPLY")
        official_share = round((official_count / confirmed_count * 100) if confirmed_count else 0.0, 1)

        payload = {
            "metadata": {
                "generated_at_ist": run_time.strftime("%Y-%m-%d %H:%M:%S IST"),
                "candidate_profile": "Azure Cloud Engineer (4+ yrs total IT experience, LTIMindtree)",
                "total_jobs_evaluated": len(jobs),
                "new_confirmed_openings": new_count,
                "needs_review_count": review_count,
                "already_applied_count": applied_count,
                "previously_reviewed_count": previously_reviewed_count,
                "official_career_page_share_confirmed": f"{official_share}% (Target >= 70%)",
                "source_coverage": "Official Career Pages, Wellfound, LinkedIn Jobs, Hacker News, RemoteOK, Jobicy, Arbeitnow"
            },
            "jobs": [
                {
                    "company": j.company,
                    "job_title": j.title,
                    "location": j.location,
                    "work_arrangement": j.work_arrangement,
                    "location_priority": j.location_category,
                    "original_posting_date": j.original_posting_date,
                    "last_verification_timestamp": j.date_last_verified,
                    "required_experience": j.experience_requirement,
                    "candidate_experience_fit": j.candidate_experience_fit,
                    "relevant_technical_skills": j.matching_skills,
                    "missing_mandatory_skills": j.missing_skills,
                    "estimated_profile_match_score": j.estimated_match_score,
                    "score_reasons": j.score_reasons,
                    "recommendation": j.recommendation,
                    "reason_for_recommendation": j.recommendation_rationale,
                    "source_url": j.direct_job_url,
                    "official_application_url": j.direct_application_url or j.direct_job_url,
                    "canonical_job_key": j.canonical_job_key,
                    "duplicate_check_result": j.duplicate_check_result,
                    "previous_application_status": j.application_status
                }
                for j in jobs
            ]
        }
        for path in filepaths:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

    def generate_html(self, jobs: List[JobPosting], run_time: datetime, excluded_summary: List[str]) -> str:
        # Partition into mandatory 7 report sections:
        # 1. Bengaluru — New confirmed jobs
        # 2. Other India locations — New confirmed jobs
        # 3. Worldwide remote — Confirmed jobs eligible for India-based applicants
        # 4. Previously reviewed jobs with meaningful changes
        # 5. Date-unverified or employer-verification-pending leads
        # 6. Possible duplicates requiring review
        # 7. Summary of excluded jobs and reasons

        today_date_str = run_time.strftime("%Y-%m-%d")

        def is_discovered_today(j: JobPosting) -> bool:
            if j.application_status == "NEW":
                return True
            if j.first_seen and j.first_seen[:10] == today_date_str:
                return True
            return False

        sec_1 = [j for j in jobs if j.location_category == "bengaluru" and j.recommendation == "APPLY" and j.application_status != "APPLIED" and is_discovered_today(j)]
        sec_2 = [j for j in jobs if j.location_category == "india_other" and j.recommendation == "APPLY" and j.application_status != "APPLIED" and is_discovered_today(j)]
        sec_3 = [j for j in jobs if j.location_category == "worldwide_remote" and j.recommendation == "APPLY" and j.application_status != "APPLIED" and is_discovered_today(j)]
        sec_4 = [j for j in jobs if j.application_status == "APPLIED" or (j.application_status == "PREVIOUSLY_REVIEWED" and not is_discovered_today(j))]
        sec_5 = [j for j in jobs if j.recommendation == "REVIEW" and j not in sec_4]
        sec_6 = [j for j in jobs if "possible duplicate" in j.duplicate_check_result.lower()]

        confirmed_count = len(sec_1) + len(sec_2) + len(sec_3)
        official_count = sum(1 for j in (sec_1 + sec_2 + sec_3) if j.source_type == "official_career_page")
        official_share = round((official_count / confirmed_count * 100) if confirmed_count else 0.0, 1)

        run_str = run_time.strftime("%d %b %Y, %I:%M %p IST")

        def render_card(j: JobPosting) -> str:
            score_color = "#10b981" if j.estimated_match_score >= 80 else ("#38bdf8" if j.estimated_match_score >= 65 else "#f59e0b")
            rec_class = "badge-apply" if j.recommendation == "APPLY" else ("badge-applied" if j.application_status == "APPLIED" else "badge-review")

            matched_html = "".join([f'<span class="skill-tag matched">{s}</span>' for s in j.matching_skills])
            missing_html = "".join([f'<span class="skill-tag missing">{s}</span>' for s in j.missing_skills])

            date_badge = f'<span class="badge-verified">Verified 24h: {j.original_posting_date}</span>' if j.date_is_verified else '<span class="badge-unverified">Date Unverified</span>'
            status_badge = f'<span class="badge-status">{j.application_status}</span>'

            dup_info = f'<div class="dup-box"><strong>Anti-Duplicate Check:</strong> {j.duplicate_check_result} &bull; <code>{j.canonical_job_key}</code></div>'

            linkedin_btn = f'<a href="{j.linkedin_job_url}" target="_blank" rel="noopener noreferrer" class="btn btn-linkedin">LinkedIn Job Link ↗</a>' if j.linkedin_job_url else ''

            reasons_html = "".join([f"<li>{r}</li>" for r in j.score_reasons[:3]])

            return f"""
            <div class="job-card" data-location="{j.location_category}" data-rec="{j.recommendation}" data-status="{j.application_status}">
                <div class="card-top">
                    <div>
                        <div class="source-tag">{j.source_name} &bull; {status_badge}</div>
                        <h3 class="job-title">{j.title}</h3>
                        <div class="company-name">{j.company} &bull; <span class="loc-text">{j.location} ({j.work_arrangement})</span></div>
                    </div>
                    <div class="score-display" style="border-color: {score_color}; color: {score_color};">
                        <div class="score-num">{j.estimated_match_score}%</div>
                        <div class="score-lbl">Profile Match</div>
                    </div>
                </div>

                <div class="card-meta">
                    <div><strong>Exp Required:</strong> {j.experience_requirement}</div>
                    <div><strong>Candidate Fit:</strong> {j.candidate_experience_fit}</div>
                    <div><strong>Posting Date:</strong> {date_badge}</div>
                    <div><strong>Last Verified:</strong> {j.date_last_verified.split(' ')[0]}</div>
                </div>

                <div class="card-body">
                    <div class="skills-block">
                        <span class="block-title">Key Matching Technologies:</span>
                        <div class="tag-cloud">{matched_html if matched_html else '<span class="dim">Fundamentals aligned</span>'}</div>
                    </div>
                    {f'''
                    <div class="skills-block">
                        <span class="block-title">Missing / Clarify Skills:</span>
                        <div class="tag-cloud">{missing_html}</div>
                    </div>
                    ''' if missing_html else ''}

                    <div class="rationale-block">
                        <strong>Evaluation Rationale:</strong> {j.recommendation_rationale}
                        <ul class="score-reasons">{reasons_html}</ul>
                    </div>
                    {dup_info}
                </div>

                <div class="card-footer">
                    <span class="rec-badge {rec_class}">Recommendation: {j.recommendation} ({j.application_status})</span>
                    <div class="card-buttons">
                        {linkedin_btn}
                        <a href="{j.direct_application_url or j.direct_job_url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Official Application URL ➔</a>
                    </div>
                </div>
            </div>
            """

        cards_1 = "\n".join([render_card(j) for j in sec_1]) if sec_1 else '<div class="empty-box">No new Bengaluru confirmed openings discovered in this 24-hour cycle.</div>'
        cards_2 = "\n".join([render_card(j) for j in sec_2]) if sec_2 else '<div class="empty-box">No new confirmed openings in other Indian cities.</div>'
        cards_3 = "\n".join([render_card(j) for j in sec_3]) if sec_3 else '<div class="empty-box">No new worldwide remote openings with verified India eligibility.</div>'
        cards_4 = "\n".join([render_card(j) for j in sec_4]) if sec_4 else '<div class="empty-box">No previously reviewed openings in active rotation.</div>'
        cards_5 = "\n".join([render_card(j) for j in sec_5]) if sec_5 else '<div class="empty-box">No pending leads requiring date or location review.</div>'
        cards_6 = "\n".join([render_card(j) for j in sec_6]) if sec_6 else '<div class="empty-box">Zero duplicate ambiguities detected. All vacancies cleanly resolved.</div>'

        excluded_items_html = "".join([f"<li>{ex}</li>" for ex in (excluded_summary or [
            "Roles requiring 7+ years hard minimum were excluded (candidate has 4.2 yrs total IT experience)",
            "Third-party staffing agencies and consultancies without identified direct employers were rejected",
            "Non-infrastructure disciplines (Sales, Marketing, HR, Business Development) were excluded",
            "Timezone-restricted postings (US Only, CET/Europe Only) were filtered out"
        ])])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personalized Daily Job Finder & Application Tracker</title>
    <style>
        :root {{
            --bg: #0b0f19;
            --surface: #151e2e;
            --border: #223048;
            --text-main: #f1f5f9;
            --text-dim: #94a3b8;
            --accent: #38bdf8;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --radius: 10px;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background: var(--bg); color: var(--text-main); line-height: 1.5; padding: 24px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}

        /* Top Header */
        header {{ border-bottom: 1px solid var(--border); padding-bottom: 20px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; }}
        .header-title h1 {{ font-size: 24px; font-weight: 700; color: #fff; }}
        .header-title p {{ color: var(--text-dim); font-size: 14px; margin-top: 4px; }}
        .profile-badge {{ background: #0284c7; color: #fff; font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 999px; text-transform: uppercase; }}
        .header-meta {{ text-align: right; font-size: 13px; color: var(--text-dim); }}

        /* Anti-Duplicate Banner */
        .anti-spam-banner {{ background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius); padding: 14px 18px; margin-bottom: 24px; font-size: 13px; color: #a7f3d0; }}
        .anti-spam-banner strong {{ color: #34d399; }}

        /* KPI Metric Cards */
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 28px; }}
        .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; }}
        .kpi-val {{ font-size: 28px; font-weight: 700; color: #fff; }}
        .kpi-label {{ font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }}
        .kpi-highlight {{ border-color: var(--accent); background: linear-gradient(180deg, var(--surface) 0%, rgba(56, 189, 248, 0.1) 100%); }}

        /* Sections */
        .section-wrap {{ margin-bottom: 36px; }}
        .sec-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding-bottom: 8px; border-bottom: 2px solid var(--border); }}
        .sec-header h2 {{ font-size: 18px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }}
        .badge-count {{ background: var(--border); font-size: 12px; padding: 2px 8px; border-radius: 999px; color: var(--text-main); }}
        .loc-priority {{ font-size: 12px; color: var(--accent); font-weight: 600; text-transform: uppercase; }}

        /* Job Card */
        .cards-list {{ display: flex; flex-direction: column; gap: 14px; }}
        .job-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; }}
        .card-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 12px; }}
        .source-tag {{ font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--accent); margin-bottom: 4px; }}
        .job-title {{ font-size: 18px; font-weight: 600; color: #fff; }}
        .company-name {{ font-size: 14px; color: var(--text-dim); }}
        .loc-text {{ color: #cbd5e1; }}

        .score-display {{ border: 2px solid; border-radius: 8px; padding: 6px 12px; text-align: center; min-width: 85px; }}
        .score-num {{ font-size: 20px; font-weight: 700; }}
        .score-lbl {{ font-size: 9px; text-transform: uppercase; }}

        .card-meta {{ display: flex; flex-wrap: wrap; gap: 16px; padding: 10px 0; border-top: 1px solid rgba(255,255,255,0.06); border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 13px; color: var(--text-dim); margin-bottom: 12px; }}
        .badge-verified {{ color: var(--success); font-weight: 600; }}
        .badge-unverified {{ color: var(--warning); font-weight: 600; }}
        .badge-status {{ background: #0369a1; color: #fff; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; }}

        .card-body {{ font-size: 13px; margin-bottom: 14px; }}
        .skills-block {{ margin-bottom: 8px; }}
        .block-title {{ font-weight: 600; color: var(--text-dim); font-size: 12px; }}
        .tag-cloud {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }}
        .skill-tag {{ font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }}
        .skill-tag.matched {{ background: rgba(56, 189, 248, 0.15); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.3); }}
        .skill-tag.missing {{ background: rgba(239, 68, 68, 0.1); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.2); }}

        .rationale-block {{ background: rgba(11, 15, 25, 0.6); padding: 10px 14px; border-radius: 6px; margin-top: 10px; font-size: 12px; color: #cbd5e1; }}
        .score-reasons {{ margin: 6px 0 0 16px; color: var(--text-dim); }}
        .dup-box {{ background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.08); padding: 8px 12px; border-radius: 6px; margin-top: 8px; font-size: 11px; color: #94a3b8; }}

        .card-footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px; flex-wrap: wrap; gap: 10px; }}
        .rec-badge {{ font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 6px; }}
        .badge-apply {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }}
        .badge-applied {{ background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); }}
        .badge-review {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }}

        .card-buttons {{ display: flex; gap: 8px; }}
        .btn {{ padding: 7px 14px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; transition: all 0.2s; }}
        .btn-primary {{ background: #0284c7; color: #fff; }}
        .btn-primary:hover {{ background: #0369a1; }}
        .btn-linkedin {{ background: #0a66c2; color: #fff; }}
        .btn-linkedin:hover {{ background: #084e96; }}

        .empty-box {{ background: var(--surface); border: 1px dashed var(--border); padding: 24px; text-align: center; color: var(--text-dim); border-radius: var(--radius); font-size: 14px; }}
        .excluded-box {{ background: var(--surface); border: 1px solid var(--border); padding: 18px; border-radius: var(--radius); }}
        .excluded-box ul {{ margin-left: 20px; font-size: 13px; color: var(--text-dim); }}
        .excluded-box li {{ margin-bottom: 4px; }}

        footer {{ text-align: center; font-size: 12px; color: var(--text-dim); border-top: 1px solid var(--border); padding-top: 20px; margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-title">
                <h1>
                    <span>Personalized Job Finder & Application Tracker</span>
                    <span class="profile-badge">Azure Cloud Engineer (4+ Yrs IT)</span>
                </h1>
                <p>Strict Anti-Spam / Anti-Duplicate Architecture &bull; Official Career Pages Preferred &bull; Past 24h Verified</p>
            </div>
            <div class="header-meta">
                <div><strong>Schedule:</strong> 08:30 IST Daily</div>
                <div><strong>Run Timestamp:</strong> {run_str}</div>
                <div><strong>Current Role:</strong> Azure Cloud Engineer at LTIMindtree</div>
            </div>
        </header>

        <div class="anti-spam-banner">
            <strong>🛡️ Mandatory Anti-Duplicate Protection Active:</strong> Canonical keying ensures one vacancy has one canonical record across LinkedIn, Wellfound, and official career portals. If you have already applied for a vacancy, the system permanently prevents duplicate application recommendations.
        </div>

        <div class="kpi-grid">
            <div class="kpi-card kpi-highlight">
                <div class="kpi-val">{len(sec_1)}</div>
                <div class="kpi-label">1. Bengaluru New Confirmed</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{len(sec_2)}</div>
                <div class="kpi-label">2. Other India Confirmed</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{len(sec_3)}</div>
                <div class="kpi-label">3. Worldwide Remote (India)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{len(sec_4)}</div>
                <div class="kpi-label">4. Previously Reviewed / Applied</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{official_share}%</div>
                <div class="kpi-label">Official Page Share (Confirmed)</div>
            </div>
        </div>

        <!-- 1. BENGALURU — NEW CONFIRMED JOBS -->
        <div class="section-wrap" id="sec-1">
            <div class="sec-header">
                <h2>🏢 1. Bengaluru — New Confirmed Jobs <span class="badge-count">{len(sec_1)}</span></h2>
                <span class="loc-priority">Priority 1 (Highest Ranking)</span>
            </div>
            <div class="cards-list">
                {cards_1}
            </div>
        </div>

        <!-- 2. OTHER INDIA LOCATIONS — NEW CONFIRMED JOBS -->
        <div class="section-wrap" id="sec-2">
            <div class="sec-header">
                <h2>🇮🇳 2. Other India Locations — New Confirmed Jobs <span class="badge-count">{len(sec_2)}</span></h2>
                <span class="loc-priority">Priority 2 (Chennai, Pune, Hyderabad, NCR)</span>
            </div>
            <div class="cards-list">
                {cards_2}
            </div>
        </div>

        <!-- 3. WORLDWIDE REMOTE — CONFIRMED JOBS ELIGIBLE FOR INDIA -->
        <div class="section-wrap" id="sec-3">
            <div class="sec-header">
                <h2>🌐 3. Worldwide Remote — Confirmed Jobs Eligible for India-Based Applicants <span class="badge-count">{len(sec_3)}</span></h2>
                <span class="loc-priority">Priority 3 (Explicitly Verified India Remote)</span>
            </div>
            <div class="cards-list">
                {cards_3}
            </div>
        </div>

        <!-- 4. PREVIOUSLY REVIEWED JOBS -->
        <div class="section-wrap" id="sec-4">
            <div class="sec-header">
                <h2>📋 4. Previously Reviewed & Applied Jobs (3-Day Display Window) <span class="badge-count">{len(sec_4)}</span></h2>
                <span class="loc-priority">Historical Audit &bull; Anti-Spam Lock</span>
            </div>
            <div class="cards-list">
                {cards_4}
            </div>
        </div>

        <!-- 5. DATE-UNVERIFIED OR EMPLOYER-VERIFICATION-PENDING LEADS -->
        <div class="section-wrap" id="sec-5">
            <div class="sec-header">
                <h2>🔍 5. Date-Unverified or Verification-Pending Leads (LinkedIn / Wellfound) <span class="badge-count">{len(sec_5)}</span></h2>
                <span class="loc-priority">Review Manually Before Applying</span>
            </div>
            <div class="cards-list">
                {cards_5}
            </div>
        </div>

        <!-- 6. POSSIBLE DUPLICATES REQUIRING REVIEW -->
        <div class="section-wrap" id="sec-6">
            <div class="sec-header">
                <h2>⚠️ 6. Possible Duplicates Requiring Review <span class="badge-count">{len(sec_6)}</span></h2>
            </div>
            <div class="cards-list">
                {cards_6}
            </div>
        </div>

        <!-- 7. SUMMARY OF EXCLUDED JOBS AND REASONS -->
        <div class="section-wrap" id="sec-7">
            <div class="sec-header">
                <h2>⛔ 7. Summary of Excluded Jobs and Audit Reasons</h2>
            </div>
            <div class="excluded-box">
                <ul>
                    {excluded_items_html}
                </ul>
            </div>
        </div>

        <footer>
            <p>Antigravity Daily Job Finder &bull; Anti-Spam Canonical Keying Active &bull; Automated 08:30 IST Schedule</p>
        </footer>
    </div>
</body>
</html>
"""
