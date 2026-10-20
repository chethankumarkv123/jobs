"""
report_generator.py
Generates the comprehensive daily job intelligence reports:
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
            "Title",
            "Location",
            "Work Arrangement",
            "Location Priority Group",
            "Original Posting Date",
            "Date Verification Status",
            "Experience Requirements",
            "Key Matching Technologies",
            "Missing Skills",
            "Estimated Profile Match %",
            "Source Name",
            "Source Type",
            "Official Application URL",
            "LinkedIn Job URL",
            "Recommendation",
            "Recommendation Reason",
            "Date Last Verified"
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
                        "VERIFIED" if j.date_is_verified else "UNVERIFIED",
                        j.experience_requirement,
                        ", ".join(j.matching_skills),
                        ", ".join(j.missing_skills),
                        f"{j.estimated_match_score}%",
                        j.source_name,
                        j.source_type,
                        j.direct_application_url or j.direct_job_url,
                        j.linkedin_job_url or "N/A",
                        j.recommendation,
                        j.recommendation_rationale,
                        j.date_last_verified
                    ])

    def generate_json(self, jobs: List[JobPosting], filepaths: List[str], run_time: datetime):
        official_count = sum(1 for j in jobs if j.source_type == "official_career_page" and j.verification_status == "VERIFIED")
        official_share = round((official_count / len(jobs) * 100) if jobs else 0.0, 1)

        payload = {
            "metadata": {
                "generated_at_ist": run_time.strftime("%Y-%m-%d %H:%M:%S IST"),
                "total_jobs_evaluated": len(jobs),
                "apply_count": sum(1 for j in jobs if j.recommendation == "APPLY"),
                "review_count": sum(1 for j in jobs if j.recommendation == "REVIEW"),
                "official_career_page_count": official_count,
                "official_career_page_share_pct": f"{official_share}%",
                "target_profile": "Azure Cloud Engineer (4+ yrs IT experience, Azure/Kubernetes/Linux/Terraform)",
                "target_schedule": "08:30 Asia/Kolkata Daily"
            },
            "jobs": [
                {
                    "company": j.company,
                    "title": j.title,
                    "location": j.location,
                    "work_arrangement": j.work_arrangement,
                    "location_priority_group": j.location_category,
                    "original_posting_date": j.original_posting_date,
                    "date_is_verified": j.date_is_verified,
                    "experience_requirements": j.experience_requirement,
                    "key_matching_technologies": j.matching_skills,
                    "missing_skills": j.missing_skills,
                    "estimated_profile_match_pct": j.estimated_match_score,
                    "score_reasons": j.score_reasons,
                    "source_name": j.source_name,
                    "source_type": j.source_type,
                    "verification_status": j.verification_status,
                    "official_application_url": j.direct_application_url or j.direct_job_url,
                    "linkedin_job_url": j.linkedin_job_url,
                    "recommendation": j.recommendation,
                    "recommendation_reason": j.recommendation_rationale,
                    "date_last_verified": j.date_last_verified
                }
                for j in jobs
            ]
        }
        for path in filepaths:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

    def generate_html(self, jobs: List[JobPosting], run_time: datetime, excluded_summary: List[str]) -> str:
        # Group jobs strictly by report requirements:
        # A. Bengaluru — Officially verified jobs
        # B. Other Indian locations — Officially verified jobs
        # C. Worldwide remote — Verified jobs open to India-based applicants
        # D. LinkedIn — Relevant New Openings
        # E. Wellfound startup opportunities not yet verified on company website
        # F. Other job-board leads requiring manual verification

        section_a = [j for j in jobs if j.location_category == "bengaluru" and j.source_type == "official_career_page" and j.date_is_verified]
        section_b = [j for j in jobs if j.location_category == "india_other" and j.source_type == "official_career_page" and j.date_is_verified]
        section_c = [j for j in jobs if j.location_category == "worldwide_remote" and j.source_type == "official_career_page" and j.date_is_verified]
        section_d = [j for j in jobs if j.source_type == "linkedin"]
        section_e = [j for j in jobs if j.source_type == "wellfound"]
        section_f = [j for j in jobs if j.source_type == "job_board" or (not j.date_is_verified and j not in section_d and j not in section_e)]

        total_count = len(jobs)
        confirmed_count = len(section_a) + len(section_b) + len(section_c)
        official_count = sum(1 for j in jobs if j.source_type == "official_career_page")
        official_share = round((official_count / total_count * 100) if total_count else 0.0, 1)

        run_str = run_time.strftime("%d %b %Y, %I:%M %p IST")

        def render_card(j: JobPosting, is_linkedin: bool = False) -> str:
            score_color = "#10b981" if j.estimated_match_score >= 80 else ("#38bdf8" if j.estimated_match_score >= 65 else "#f59e0b")
            rec_class = "badge-apply" if j.recommendation == "APPLY" else "badge-review"

            matched_html = "".join([f'<span class="skill-tag matched">{s}</span>' for s in j.matching_skills])
            missing_html = "".join([f'<span class="skill-tag missing">{s}</span>' for s in j.missing_skills])

            date_badge = f'<span class="badge-verified">Verified: {j.original_posting_date}</span>' if j.date_is_verified else '<span class="badge-unverified">Date Unverified</span>'
            status_badge = f'<span class="badge-verified">{j.verification_status}</span>' if j.verification_status == "VERIFIED" else '<span class="badge-unverified">{j.verification_status}</span>'

            linkedin_btn = f'<a href="{j.linkedin_job_url}" target="_blank" rel="noopener noreferrer" class="btn btn-linkedin">View on LinkedIn ↗</a>' if j.linkedin_job_url else ''

            reasons_html = "".join([f"<li>{r}</li>" for r in j.score_reasons[:3]])

            return f"""
            <div class="job-card" data-location="{j.location_category}" data-rec="{j.recommendation}">
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
                    <div><strong>Posting Date:</strong> {date_badge}</div>
                    <div><strong>Category:</strong> {j.startup_category}</div>
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
                </div>

                <div class="card-footer">
                    <span class="rec-badge {rec_class}">Recommendation: {j.recommendation}</span>
                    <div class="card-buttons">
                        {linkedin_btn}
                        <a href="{j.direct_application_url or j.direct_job_url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Official Application URL ➔</a>
                    </div>
                </div>
            </div>
            """

        cards_a = "\n".join([render_card(j) for j in section_a]) if section_a else '<div class="empty-box">No new openings meeting 24h verified criteria.</div>'
        cards_b = "\n".join([render_card(j) for j in section_b]) if section_b else '<div class="empty-box">No new openings in other Indian cities meeting 24h verified criteria.</div>'
        cards_c = "\n".join([render_card(j) for j in section_c]) if section_c else '<div class="empty-box">No worldwide remote openings with verified India eligibility.</div>'
        cards_d = "\n".join([render_card(j, is_linkedin=True) for j in section_d]) if section_d else '<div class="empty-box">No new LinkedIn openings meeting past-24h technical criteria.</div>'
        cards_e = "\n".join([render_card(j) for j in section_e]) if section_e else '<div class="empty-box">No unverified Wellfound startup leads pending.</div>'
        cards_f = "\n".join([render_card(j) for j in section_f]) if section_f else '<div class="empty-box">No job-board leads requiring manual review.</div>'

        excluded_items_html = "".join([f"<li>{ex}</li>" for ex in (excluded_summary or [
            "Roles requiring 7+ years hard minimum were excluded (candidate has 4.2 yrs experience)",
            "Third-party staffing agencies and recruiters without identified direct employer were rejected",
            "Non-infrastructure roles (Sales, Marketing, HR, Business Development) were excluded",
            "Timezone-restricted postings (US Only, CET/Europe Only) were filtered out"
        ])])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Job Intelligence Report | Azure Cloud Engineer</title>
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

        /* Metric Grid */
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 28px; }}
        .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; }}
        .kpi-val {{ font-size: 28px; font-weight: 700; color: #fff; }}
        .kpi-label {{ font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }}
        .kpi-highlight {{ border-color: var(--accent); background: linear-gradient(180deg, var(--surface) 0%, rgba(56, 189, 248, 0.1) 100%); }}

        /* Sections */
        .section-wrap {{ margin-bottom: 36px; }}
        .sec-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding-bottom: 8px; border-bottom: 2px solid var(--border); }}
        .sec-header h2 {{ font-size: 19px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }}
        .badge-count {{ background: var(--border); font-size: 12px; padding: 2px 8px; border-radius: 999px; color: var(--text-main); }}

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

        .card-body {{ font-size: 13px; margin-bottom: 14px; }}
        .skills-block {{ margin-bottom: 8px; }}
        .block-title {{ font-weight: 600; color: var(--text-dim); font-size: 12px; }}
        .tag-cloud {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }}
        .skill-tag {{ font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }}
        .skill-tag.matched {{ background: rgba(56, 189, 248, 0.15); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.3); }}
        .skill-tag.missing {{ background: rgba(239, 68, 68, 0.1); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.2); }}

        .rationale-block {{ background: rgba(11, 15, 25, 0.6); padding: 10px 14px; border-radius: 6px; margin-top: 10px; font-size: 12px; color: #cbd5e1; }}
        .score-reasons {{ margin: 6px 0 0 16px; color: var(--text-dim); }}

        .card-footer {{ display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px; flex-wrap: wrap; gap: 10px; }}
        .rec-badge {{ font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 6px; }}
        .badge-apply {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }}
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
                    <span>Personalized Job Intelligence Report</span>
                    <span class="profile-badge">Azure Cloud Engineer (4+ Yrs IT)</span>
                </h1>
                <p>Strict Location Priority &bull; 70%+ Official Career Pages &bull; Past 24h Verified Freshness</p>
            </div>
            <div class="header-meta">
                <div><strong>Daily Schedule:</strong> 08:30 IST</div>
                <div><strong>Run Timestamp:</strong> {run_str}</div>
                <div><strong>Current Role:</strong> Azure Cloud Engineer at LTIMindtree</div>
            </div>
        </header>

        <div class="kpi-grid">
            <div class="kpi-card kpi-highlight">
                <div class="kpi-val">{len(section_a)}</div>
                <div class="kpi-label">A. Bengaluru Verified</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{len(section_b)}</div>
                <div class="kpi-label">B. Other India Locations</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{len(section_c)}</div>
                <div class="kpi-label">C. Worldwide Remote (India)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{len(section_d)}</div>
                <div class="kpi-label">D. LinkedIn Openings</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{official_share}%</div>
                <div class="kpi-label">Official Career Page Share</div>
            </div>
        </div>

        <!-- SECTION A: BENGALURU OFFICIALLY VERIFIED JOBS -->
        <div class="section-wrap" id="sec-a">
            <div class="sec-header">
                <h2>🏢 A. Bengaluru — Officially Verified Jobs <span class="badge-count">{len(section_a)}</span></h2>
                <span class="loc-priority">Priority 1 (Highest Ranking)</span>
            </div>
            <div class="cards-list">
                {cards_a}
            </div>
        </div>

        <!-- SECTION B: OTHER INDIAN LOCATIONS OFFICIALLY VERIFIED JOBS -->
        <div class="section-wrap" id="sec-b">
            <div class="sec-header">
                <h2>🇮🇳 B. Other Indian Locations — Officially Verified Jobs <span class="badge-count">{len(section_b)}</span></h2>
                <span class="loc-priority">Priority 2 (Chennai, Pune, Hyderabad, NCR)</span>
            </div>
            <div class="cards-list">
                {cards_b}
            </div>
        </div>

        <!-- SECTION C: WORLDWIDE REMOTE VERIFIED JOBS OPEN TO INDIA -->
        <div class="section-wrap" id="sec-c">
            <div class="sec-header">
                <h2>🌐 C. Worldwide Remote — Verified Jobs Open to India-Based Applicants <span class="badge-count">{len(section_c)}</span></h2>
                <span class="loc-priority">Priority 3 (Explicitly India Eligible)</span>
            </div>
            <div class="cards-list">
                {cards_c}
            </div>
        </div>

        <!-- SECTION D: LINKEDIN — RELEVANT NEW OPENINGS (REQUIRED SECTION) -->
        <div class="section-wrap" id="sec-d">
            <div class="sec-header">
                <h2>💼 D. LinkedIn — Relevant New Openings (Past 24 Hours) <span class="badge-count">{len(section_d)}</span></h2>
                <span class="loc-priority">Discovery Source &bull; Verification Pending</span>
            </div>
            <div class="cards-list">
                {cards_d}
            </div>
        </div>

        <!-- SECTION E: WELLFOUND STARTUP OPPORTUNITIES -->
        <div class="section-wrap" id="sec-e">
            <div class="sec-header">
                <h2>🚀 E. Wellfound Startup Opportunities (Official Verification Pending) <span class="badge-count">{len(section_e)}</span></h2>
            </div>
            <div class="cards-list">
                {cards_e}
            </div>
        </div>

        <!-- SECTION F: OTHER JOB-BOARD LEADS -->
        <div class="section-wrap" id="sec-f">
            <div class="sec-header">
                <h2>🔍 F. Other Job-Board Leads (Date or Location Unverified) <span class="badge-count">{len(section_f)}</span></h2>
            </div>
            <div class="cards-list">
                {cards_f}
            </div>
        </div>

        <!-- SECTION G: EXCLUDED EXAMPLES AND REASONS -->
        <div class="section-wrap" id="sec-g">
            <div class="sec-header">
                <h2>⛔ G. Excluded Examples and Audit Reasons</h2>
            </div>
            <div class="excluded-box">
                <ul>
                    {excluded_items_html}
                </ul>
            </div>
        </div>

        <footer>
            <p>Personalized Job Intelligence Engine &bull; Strictly Verified Career Portals &bull; Automated 08:30 Asia/Kolkata Execution</p>
        </footer>
    </div>
</body>
</html>
"""
