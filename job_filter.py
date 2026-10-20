"""
job_filter.py
Intelligent filtering, resume-specific scoring (0-100), location prioritization,
cross-source deduplication, and application history tracking engine.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Set
from job_sources import JobPosting
from application_tracker import ApplicationTracker, clean_tracking_params, generate_canonical_key

logger = logging.getLogger(__name__)


class JobFilterEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tracker = ApplicationTracker("data/application_history.json")

        self.history_file = config.get("storage", {}).get("jobs_history_file", "data/jobs_history.json")
        self.history_data: Dict[str, Any] = self._load_history()

        candidate = config.get("candidate", {})
        self.candidate_role = candidate.get("current_role", "Azure Cloud Engineer")
        self.candidate_total_exp = candidate.get("total_experience_years", 4.2)
        self.az104_status = candidate.get("az104_status", "in_progress")

        exp_filter = config.get("experience_filter", {})
        self.target_min_exp = exp_filter.get("target_min_years", 3)
        self.target_max_exp = exp_filter.get("target_max_years", 6)
        self.preferred_years = exp_filter.get("preferred_years", [4, 5])
        self.hard_exclude_min_exp = exp_filter.get("hard_exclude_min_years", 7)

        self.thresholds = config.get("thresholds", {"apply_min_score": 65, "review_min_score": 40})
        self.agency_keywords = [
            "confidential client", "hiring for a client", "staffing", "recruitment agency",
            "manpower", "talent acquisition consultancy", "client of", "randstad", "michael page",
            "adecco", "teamlease", "allegis", "kelly services", "recruise"
        ]

        self.excluded_reasons_log: List[str] = []

    def _load_history(self) -> Dict[str, Any]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading {self.history_file}: {e}")
        return {"version": "3.0.0", "last_updated": None, "total_tracked": 0, "jobs": {}}

    def save_history(self):
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            self.history_data["last_updated"] = datetime.now(timezone.utc).isoformat()
            self.history_data["total_tracked"] = len(self.history_data.get("jobs", {}))
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history_data, f, indent=2, ensure_ascii=False)
            self.tracker.save()
            logger.info(f"Updated job history ({self.history_data['total_tracked']} jobs recorded).")
        except Exception as e:
            logger.error(f"Failed to save job history: {e}")

    def is_recruitment_agency(self, job: JobPosting) -> bool:
        combined = f"{job.company} {job.title} {job.description}".lower()
        for kw in self.agency_keywords:
            if kw in combined:
                return True
        return False

    def is_disqualified_discipline(self, job: JobPosting) -> Tuple[bool, str]:
        title_lower = job.title.lower()
        disqualified = [
            "sales", "account executive", "marketing", "recruiter", "talent acquisition",
            "bpo", "telecaller", "customer support", "content writer", "copywriter",
            "business development", "product manager", "ui/ux designer", "finance lead",
            "supply chain", "legal counsel", "chief of staff", "graphic designer",
            "logistics", "specialist — logistics", "specialist - data engineering"
        ]
        for bad in disqualified:
            if bad in title_lower:
                return True, f"Non-infrastructure discipline: '{bad}'"
        return False, ""

    def evaluate_location(self, job: JobPosting) -> Tuple[float, str, str, bool]:
        loc_lower = f"{job.location} {job.work_arrangement}".lower()
        desc_lower = job.description.lower()

        bangalore_tokens = ["bangalore", "bengaluru", "blr", "koramangala", "hsr", "indiranagar", "whitefield", "bellandur", "jp nagar"]
        is_blr = any(b in loc_lower for b in bangalore_tokens) or any(b in desc_lower for b in bangalore_tokens)

        if is_blr:
            return 10.0, "bengaluru", f"Bengaluru ({job.work_arrangement}) — Priority 1", True

        other_india_tokens = ["hyderabad", "pune", "chennai", "mumbai", "noida", "gurgaon", "delhi", "gurugram", "kolkata", "ahmedabad", "kochi", "india"]
        is_other_india = any(c in loc_lower for c in other_india_tokens) or any(c in desc_lower for c in other_india_tokens)

        if is_other_india:
            return 10.0, "india_other", f"India Location: {job.location} — Priority 2", True

        foreign_excl = [
            "us only", "usa only", "uk only", "eu only", "germany only", "canada only",
            "cet", "cest", "pst", "est", "san francisco", "berlin", "germany", "london"
        ]
        has_foreign = any(f in loc_lower for f in foreign_excl)

        if has_foreign and not (is_blr or is_other_india):
            return 0.0, "foreign_restricted", f"Ineligible Foreign Location / Timezone ({job.location})", False

        if any(w in loc_lower for w in ["worldwide", "anywhere", "remote worldwide", "remote - india", "india eligible"]):
            return 8.0, "worldwide_remote", "Worldwide Remote (India Eligible) — Priority 3", True

        if "remote" in loc_lower and not has_foreign:
            return 6.0, "worldwide_remote", f"Remote (Pending India Eligibility Verification: {job.location})", True

        return 0.0, "foreign_restricted", f"Location Ineligible: {job.location}", False

    def calculate_match_score(self, job: JobPosting, loc_pts: float, loc_cat: str) -> Tuple[float, List[str], List[str], List[str]]:
        reasons: List[str] = []
        combined_text = f"{job.title} {job.description} {' '.join(job.technical_skills)}".lower()

        # 1. Technical Skills Match (Max 35 pts)
        core_tech = [
            ("Azure", ["azure", "aks", "microsoft azure", "vnet", "azure devops", "azure monitor", "app service", "key vault"]),
            ("Kubernetes", ["kubernetes", "k8s", "aks", "container orchestration"]),
            ("Linux", ["linux", "rhel", "ubuntu", "centos", "systemd", "shell", "bash"]),
            ("Terraform", ["terraform", "iac", "infrastructure as code"]),
            ("Ansible", ["ansible", "configuration management"]),
            ("CI/CD", ["ci/cd", "github actions", "azure devops", "pipeline"]),
            ("Docker", ["docker", "containers"]),
            ("Monitoring", ["monitoring", "prometheus", "grafana", "log analytics", "azure monitor", "telemetry"]),
            ("Security/Hardening", ["devsecops", "qualys", "cis hardening", "vulnerability", "defender for cloud", "cve", "bigfix"]),
            ("Scripting", ["python", "bash", "shell scripting"])
        ]
        matched_skills = []
        missing_skills = []

        for skill_name, tokens in core_tech:
            if any(t in combined_text for t in tokens):
                matched_skills.append(skill_name)
            else:
                missing_skills.append(skill_name)

        tech_score = min(len(matched_skills) * 3.5, 35.0)
        reasons.append(f"Core Tech: Matched {len(matched_skills)}/10 skill domains ({', '.join(matched_skills[:4])})")

        # 2. Responsibilities Match (Max 20 pts)
        duties = [
            ("Provisioning & IaC", ["provision", "iac", "deploy", "architecture", "terraform"]),
            ("Cloud Operations & Patching", ["operations", "patching", "maintenance", "lifecycle", "drift", "support"]),
            ("Incident Response & SRE", ["incident", "servicenow", "rca", "on-call", "post-mortem", "sla", "mttr", "sre"]),
            ("Hardening & Compliance", ["hardening", "compliance", "cis", "qualys", "vulnerability", "audit", "security"]),
            ("Automation", ["automation", "automate", "scripting", "ansible", "bash", "python"])
        ]
        matched_duties = [d[0] for d in duties if any(t in combined_text for t in d[1])]
        duty_score = len(matched_duties) * 4.0
        reasons.append(f"Duties: Aligned on {', '.join(matched_duties[:3])}")

        # 3. Experience Fit (Max 15 pts)
        # Evaluates total IT experience (4.2 yrs) vs cloud engineering tenure (since 2024).
        exp_score = 0.0
        if job.min_years_exp is not None:
            if 4.0 <= job.min_years_exp <= 5.0:
                exp_score = 15.0
                job.candidate_experience_fit = f"Ideal Fit ({job.experience_requirement} vs candidate's 4.2 yrs total IT)"
                reasons.append(f"Experience: {job.candidate_experience_fit}")
            elif job.min_years_exp == 3.0:
                exp_score = 14.0
                job.candidate_experience_fit = f"Strong Fit ({job.experience_requirement} vs candidate's 4.2 yrs)"
                reasons.append(f"Experience: {job.candidate_experience_fit}")
            elif 5.0 < job.min_years_exp <= 6.0:
                exp_score = 12.0
                job.candidate_experience_fit = f"Acceptable Reach ({job.experience_requirement} - candidate has 4.2 yrs overall IT, Azure Engineer since 2024)"
                reasons.append(f"Experience: {job.candidate_experience_fit}")
            elif job.min_years_exp < 3.0:
                exp_score = 12.0
                job.candidate_experience_fit = f"Early Career Bracket ({job.experience_requirement})"
                reasons.append(f"Experience: {job.candidate_experience_fit}")
            else:
                exp_score = 0.0
                job.candidate_experience_fit = f"Experience Mismatch ({job.experience_requirement})"
        else:
            exp_score = 10.0
            job.candidate_experience_fit = "Unspecified Experience (Startup Flexible - Candidate has 4.2 yrs total IT)"
            reasons.append("Experience: Unspecified in posting (Startup flexible)")

        # 4. Location & India Work Eligibility (Max 10 pts)
        location_score = loc_pts
        reasons.append(f"Location Fit: {loc_cat.upper()} ({location_score}/10 pts)")

        # 5. Production Achievements & Scale (Max 10 pts)
        scale_score = 0.0
        scale_tokens = ["high availability", "scale", "production", "99.9", "microservices", "100+ servers", "distributed", "critical", "compliance"]
        matched_scale = [t for t in scale_tokens if t in combined_text]
        if len(matched_scale) >= 2:
            scale_score = 10.0
        elif len(matched_scale) == 1:
            scale_score = 7.0
        else:
            scale_score = 5.0

        # 6. Role & Employer Fit (Max 5 pts)
        role_employer_score = 5.0 if job.source_type in ("official_career_page", "wellfound") else 3.5

        # 7. Evidence Quality & Verification (Max 5 pts)
        evidence_score = 5.0 if (job.source_type == "official_career_page" and job.date_is_verified) else (3.5 if job.date_is_verified else 2.0)

        total_score = round(tech_score + duty_score + exp_score + location_score + scale_score + role_employer_score + evidence_score, 1)
        return min(total_score, 100.0), matched_skills, missing_skills[:4], reasons

    def evaluate_and_deduplicate(self, raw_jobs: List[JobPosting]) -> List[JobPosting]:
        evaluated_jobs: List[JobPosting] = []
        history_jobs = self.history_data.setdefault("jobs", {})

        # In-run deduplication map
        in_run_seen: Dict[str, JobPosting] = {}

        for job in raw_jobs:
            # 1. Employer Rule: Check if recruitment agency
            if self.is_recruitment_agency(job):
                job.is_agency = True
                job.recommendation = "SKIP"
                job.recommendation_rationale = "Recruitment agency / consultancy listing without identified direct employer"
                self.excluded_reasons_log.append(f"Agency rejected: {job.company} - {job.title}")
                logger.info(f"Skipping agency listing: {job.company} - {job.title}")
                continue

            # 2. Discipline Check (Exclude Sales, Marketing, Recruiter, Design, etc.)
            disqualified_role, role_reason = self.is_disqualified_discipline(job)
            if disqualified_role:
                job.recommendation = "SKIP"
                job.recommendation_rationale = role_reason
                self.excluded_reasons_log.append(f"Non-target discipline: {job.company} - {job.title} ({role_reason})")
                logger.info(f"Skipping {job.company} - {job.title}: {role_reason}")
                continue

            # 3. Location Eligibility & Priority Check
            loc_pts, loc_cat, loc_notes, loc_eligible = self.evaluate_location(job)
            job.location_category = loc_cat
            if not loc_eligible:
                job.recommendation = "SKIP"
                job.recommendation_rationale = loc_notes
                self.excluded_reasons_log.append(f"Ineligible location: {job.company} - {job.title} ({loc_notes})")
                logger.info(f"Skipping ineligible location: {job.location}")
                continue

            # 4. Experience Hard Filter (Exclude 7+ years)
            if job.min_years_exp is not None and job.min_years_exp >= self.hard_exclude_min_exp:
                job.recommendation = "SKIP"
                job.recommendation_rationale = f"Exceeds experience cap: Requires {job.min_years_exp}+ yrs (Limit is 6 yrs)"
                self.excluded_reasons_log.append(f"Experience > 6 yrs: {job.company} - {job.title} ({job.experience_requirement})")
                logger.info(f"Skipping {job.company} - {job.title}: Demands {job.min_years_exp}+ yrs")
                continue

            # 5. Clean URLs
            job.direct_job_url = clean_tracking_params(job.direct_job_url)
            job.direct_application_url = clean_tracking_params(job.direct_application_url or job.direct_job_url)

            # 6. Profile Match Scoring
            score, matched_skills, missing_skills, reasons = self.calculate_match_score(job, loc_pts, loc_cat)
            job.estimated_match_score = score
            job.matching_skills = matched_skills
            job.missing_skills = missing_skills
            job.score_reasons = reasons

            # 7. ANTI-DUPLICATE & APPLICATION HISTORY TRACKER
            can_key, app_status, dup_result, is_new_opening = self.tracker.evaluate_and_track(job.to_dict())
            job.canonical_job_key = can_key
            job.application_status = app_status
            job.duplicate_check_result = dup_result
            job.is_new = is_new_opening

            # 8. Recommendation Decision Engine
            if not job.is_active:
                job.recommendation = "SKIP"
                job.recommendation_rationale = "Vacancy link inactive or broken"
            elif app_status == "APPLIED":
                # NEVER recommend applying again to a vacancy already applied to!
                job.recommendation = "SKIP"
                job.recommendation_rationale = "ALREADY APPLIED: You have already applied for this opening. Do not submit duplicate application."
            elif app_status == "PREVIOUSLY_REVIEWED":
                cutoff_days = self.config.get("history_display", {}).get("previously_reviewed_cutoff_days", 3)
                days_discovered = self.tracker.get_days_since_first_discovered(can_key)
                if days_discovered > cutoff_days:
                    # Suppress from daily report once older than 3 days
                    job.recommendation = "SKIP"
                    job.recommendation_rationale = f"Previously reviewed {days_discovered:.1f} days ago (exceeds {cutoff_days}-day display cutoff). Kept in history."
                    continue
                job.recommendation = "REVIEW"
                job.recommendation_rationale = f"Previously reviewed vacancy (Day {int(days_discovered) + 1} of {cutoff_days} display window). No new application recommended unless requirements have changed."
            elif (
                job.estimated_match_score >= self.thresholds.get("apply_min_score", 65)
                and job.date_is_verified
                and job.source_type == "official_career_page"
            ):
                job.recommendation = "APPLY"
                job.recommendation_rationale = "Strong technical fit, verified within 24h on official company career page, direct application route"
            elif job.source_type == "linkedin":
                job.recommendation = "REVIEW"
                job.recommendation_rationale = "Discovered on LinkedIn past 24h feed. Official employer career site verification pending"
            elif job.source_type == "wellfound":
                job.recommendation = "REVIEW"
                job.recommendation_rationale = "Wellfound startup lead. Official employer website cross-verification pending"
            elif not job.date_is_verified:
                job.recommendation = "REVIEW"
                job.recommendation_rationale = "Posting date unverified from source. Routed to manual review section"
            elif job.estimated_match_score >= self.thresholds.get("review_min_score", 40):
                job.recommendation = "REVIEW"
                job.recommendation_rationale = "Partial technical match or location eligibility requires manual review"
            else:
                job.recommendation = "SKIP"
                job.recommendation_rationale = f"Score ({job.estimated_match_score}) below review threshold"

            # 9. In-run Cross-Source Deduplication (Merge records across sites)
            if can_key in in_run_seen:
                existing = in_run_seen[can_key]
                # Prioritize official career page URL as primary application link
                if job.source_type == "official_career_page" and existing.source_type != "official_career_page":
                    existing.direct_job_url = job.direct_job_url
                    existing.direct_application_url = job.direct_application_url
                    existing.source_type = "official_career_page"
                    existing.verification_status = "VERIFIED"
                    existing.date_is_verified = True
                    existing.recommendation = "APPLY"
                    existing.recommendation_rationale = "Merged cross-source listing; upgraded to official career page"
                if job.direct_job_url and job.direct_job_url not in existing.all_source_urls:
                    existing.all_source_urls.append(job.direct_job_url)
                if job.linkedin_job_url:
                    existing.linkedin_job_url = job.linkedin_job_url
                continue
            else:
                in_run_seen[can_key] = job

            # History file update
            if job.id in history_jobs:
                prev = history_jobs[job.id]
                job.first_seen = prev.get("first_seen", job.first_seen)
                prev["last_seen"] = job.last_seen
                prev["score"] = job.estimated_match_score
                prev["recommendation"] = job.recommendation
                prev["status"] = job.application_status
            else:
                history_jobs[job.id] = {
                    "id": job.id,
                    "canonical_job_key": job.canonical_job_key,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "source_name": job.source_name,
                    "official_application_url": job.direct_application_url or job.direct_job_url,
                    "score": job.estimated_match_score,
                    "recommendation": job.recommendation,
                    "application_status": job.application_status,
                    "first_seen": job.first_seen,
                    "last_seen": job.last_seen,
                }

            # Retain non-skipped or review jobs in final report
            if job.recommendation in ("APPLY", "REVIEW") or job.application_status == "APPLIED":
                evaluated_jobs.append(job)

        # Ranking rules:
        # 1st: Location Priority (Bengaluru -> Other India -> Worldwide Remote)
        # 2nd: Recommendation (APPLY before REVIEW before SKIP)
        # 3rd: Application Status (NEW before PREVIOUSLY_REVIEWED before APPLIED)
        # 4th: Score descending
        loc_order = {"bengaluru": 0, "india_other": 1, "worldwide_remote": 2, "foreign_restricted": 3}
        rec_order = {"APPLY": 0, "REVIEW": 1, "SKIP": 2}
        status_order = {"NEW": 0, "PREVIOUSLY_REVIEWED": 1, "APPLIED": 2, "CLOSED": 3}

        evaluated_jobs.sort(key=lambda j: (
            status_order.get(j.application_status, 1),
            loc_order.get(j.location_category, 3),
            rec_order.get(j.recommendation, 2),
            -j.estimated_match_score
        ))

        self.save_history()
        return evaluated_jobs
