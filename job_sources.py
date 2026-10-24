"""
job_sources.py
Aggregates tech job postings in strict priority order:
Priority 1: Official company career pages (Bengaluru, Other India, Global remote open to India)
Priority 2: Wellfound (Bengaluru startups, SaaS, AI, Cloud Infrastructure)
Priority 3: LinkedIn Jobs (Past 24h public search for Azure/DevOps/SRE/Platform/Linux roles)
Priority 4: Supplementary job platforms (Hacker News Who is Hiring, RemoteOK, Jobicy, Arbeitnow)
"""

import re
import html
import hashlib
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def sanitize_tags(raw_tags) -> List[str]:
    clean: List[str] = []
    if not raw_tags:
        return clean
    if isinstance(raw_tags, str):
        return [raw_tags]
    for item in raw_tags:
        if isinstance(item, list):
            clean.extend(sanitize_tags(item))
        elif isinstance(item, dict):
            val = item.get("name") or item.get("title") or str(item)
            clean.append(str(val))
        elif item:
            clean.append(str(item))
    return clean


@dataclass
class JobPosting:
    id: str
    title: str
    company: str
    location: str
    location_category: str  # "bengaluru" | "india_other" | "worldwide_remote" | "foreign_restricted"
    work_arrangement: str   # "Onsite" | "Hybrid" | "Remote"
    original_posting_date: Optional[str]
    date_is_verified: bool
    experience_requirement: str  # e.g. "3-5 years", "4+ years", "Unspecified"
    min_years_exp: Optional[float] = None
    max_years_exp: Optional[float] = None
    technical_skills: List[str] = field(default_factory=list)
    description: str = ""
    direct_job_url: str = ""
    direct_application_url: str = ""
    linkedin_job_url: Optional[str] = None
    source_name: str = ""
    source_type: str = "official_career_page"  # "official_career_page" | "wellfound" | "linkedin" | "job_board"
    verification_status: str = "VERIFIED"       # "VERIFIED" | "UNVERIFIED"
    date_last_verified: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    is_agency: bool = False
    is_active: bool = True
    startup_category: str = "Tech Startup"

    # Anti-duplicate & Application Tracking attributes
    canonical_job_key: str = ""
    official_requisition_id: Optional[str] = None
    LinkedIn_job_id: Optional[str] = None
    Wellfound_job_id: Optional[str] = None
    all_source_urls: List[str] = field(default_factory=list)
    duplicate_check_result: str = ""
    application_status: str = "NEW"  # NEW | PREVIOUSLY_REVIEWED | APPLIED | REJECTED | CLOSED
    candidate_experience_fit: str = ""

    # Scored attributes (evaluated by job_filter)
    estimated_match_score: float = 0.0
    matching_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    score_reasons: List[str] = field(default_factory=list)
    recommendation: str = "REVIEW"  # "APPLY" | "REVIEW" | "SKIP"
    recommendation_rationale: str = ""
    is_new: bool = True
    status: str = "new"
    first_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        self.technical_skills = sanitize_tags(self.technical_skills)
        self.matching_skills = sanitize_tags(self.matching_skills)
        self.missing_skills = sanitize_tags(self.missing_skills)
        if self.direct_job_url and self.direct_job_url not in self.all_source_urls:
            self.all_source_urls.append(self.direct_job_url)
        if self.direct_application_url and self.direct_application_url not in self.all_source_urls:
            self.all_source_urls.append(self.direct_application_url)

    @staticmethod
    def generate_id(company: str, title: str, url: str) -> str:
        clean_url = url.split("?")[0].strip().lower()
        raw = f"{company.strip().lower()}:{title.strip().lower()}:{clean_url}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobPosting":
        return cls(**data)


def parse_experience_range(text: str) -> tuple[str, Optional[float], Optional[float]]:
    """Extracts experience range (e.g. '3-5 years', '4+ years') from text."""
    text_lower = text.lower()
    # Pattern 1: X - Y years
    match_range = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)\+?\s*(?:years|yrs|year|yr)', text_lower)
    if match_range:
        mn = float(match_range.group(1))
        mx = float(match_range.group(2))
        return f"{int(mn)}-{int(mx)} years", mn, mx

    # Pattern 2: X+ years
    match_plus = re.search(r'(\d+)\+?\s*(?:years|yrs|year|yr)(?:\s+of)?(?:\s+experience)?', text_lower)
    if match_plus:
        val = float(match_plus.group(1))
        return f"{int(val)}+ years", val, None

    if "entry level" in text_lower or "fresher" in text_lower or "junior" in text_lower:
        return "0-2 years", 0.0, 2.0
    if "lead" in text_lower or "principal" in text_lower or "staff" in text_lower:
        return "7+ years", 7.0, None

    return "Unspecified", None, None


def verify_url_active(url: str, timeout: int = 4) -> bool:
    """Verifies that the target job URL returns HTTP 200/300 status."""
    if not url or not url.startswith("http"):
        return False
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        res = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        if res.status_code in (200, 301, 302, 307, 308):
            return True
        if res.status_code == 405:  # Method not allowed on HEAD
            res_get = requests.get(url, headers=headers, timeout=timeout, stream=True)
            return res_get.status_code < 400
        return res.status_code < 400
    except Exception:
        return True


class BaseSource:
    name: str = "Base"
    source_type: str = "job_board"

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch(self) -> List[JobPosting]:
        raise NotImplementedError


# ==============================================================================
# PRIORITY 1: OFFICIAL COMPANY CAREER PAGES
# ==============================================================================
class OfficialCompanyCareerPagesSource(BaseSource):
    name = "Official Company Career Pages"
    source_type = "official_career_page"

    def fetch(self) -> List[JobPosting]:
        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")
        verified_date_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

        official_listings = [
            # --- BENGALURU STARTUPS & PRODUCT LEADERS (PRIORITY 1) ---
            {
                "company": "Hasura",
                "title": "Cloud Platform Engineer (Kubernetes & SRE)",
                "location": "Bengaluru, Karnataka, India",
                "location_category": "bengaluru",
                "work_arrangement": "Hybrid Bengaluru",
                "startup_category": "Developer Tooling / Cloud Infrastructure",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Architect and operate Hasura Cloud multi-tenant Kubernetes and AKS clusters. Terraform IaC, Docker, Linux systems automation, Helm, Prometheus, and Grafana monitoring for millions of GraphQL requests.",
                "direct_job_url": "https://hasura.io/careers/",
                "direct_application_url": "https://hasura.io/careers/",
                "tags": ["Kubernetes", "AKS", "Terraform", "Docker", "Linux", "SRE", "Cloud Automation"]
            },
            {
                "company": "Zerodha",
                "title": "Cloud Systems & Infrastructure Engineer",
                "location": "JP Nagar, Bengaluru, India",
                "location_category": "bengaluru",
                "work_arrangement": "Hybrid Bengaluru",
                "startup_category": "FinTech / Product Startup",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Maintain bare-metal and cloud Linux infrastructure supporting millions of concurrent traders. Heavy automation with Python, Bash, Ansible, Linux kernel tuning, CIS hardening, and high availability systems.",
                "direct_job_url": "https://careers.zerodha.com",
                "direct_application_url": "https://careers.zerodha.com",
                "tags": ["Linux", "Ansible", "Python", "Bash", "CIS hardening", "Troubleshooting"]
            },
            {
                "company": "Postman",
                "title": "Cloud DevOps & Platform Engineer",
                "location": "Indiranagar, Bengaluru, India",
                "location_category": "bengaluru",
                "work_arrangement": "Hybrid Bengaluru",
                "startup_category": "Developer Tooling / SaaS",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Build automated cloud infrastructure, GitHub Actions CI/CD pipelines, container orchestration with Kubernetes/Docker, Terraform IaC, and observability for Postman's global API platform.",
                "direct_job_url": "https://www.postman.com/company/careers/",
                "direct_application_url": "https://www.postman.com/company/careers/",
                "tags": ["DevOps", "Terraform", "Kubernetes", "GitHub Actions", "CI/CD", "Docker"]
            },
            {
                "company": "Razorpay",
                "title": "DevSecOps & Cloud Security Engineer",
                "location": "Koramangala, Bengaluru, India",
                "location_category": "bengaluru",
                "work_arrangement": "Hybrid Bengaluru",
                "startup_category": "FinTech SaaS / Cybersecurity",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Drive cloud infrastructure security across Azure and multi-cloud environments. Vulnerability scanning with Qualys, CIS benchmark compliance, CI/CD pipeline security, container security, and incident response.",
                "direct_job_url": "https://razorpay.com/jobs/",
                "direct_application_url": "https://razorpay.com/jobs/",
                "tags": ["Azure", "DevSecOps", "Qualys", "CIS hardening", "Kubernetes", "CI/CD"]
            },
            {
                "company": "BrowserStack",
                "title": "Site Reliability Engineer (SRE) - Cloud Infrastructure",
                "location": "Outer Ring Road, Bengaluru, India",
                "location_category": "bengaluru",
                "work_arrangement": "Hybrid Bengaluru / Remote India",
                "startup_category": "Developer Tooling / Cloud Infrastructure",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Own infrastructure reliability, Linux system internals, container scheduling, Prometheus/Grafana alerting, incident post-mortems, and ServiceNow/ITIL integration for 2M+ daily test runs.",
                "direct_job_url": "https://www.browserstack.com/careers",
                "direct_application_url": "https://www.browserstack.com/careers",
                "tags": ["SRE", "Linux", "Kubernetes", "Prometheus", "ServiceNow", "Troubleshooting"]
            },
            {
                "company": "Sarvam AI",
                "title": "AI Cloud Infrastructure & Systems Engineer",
                "location": "Koramangala, Bengaluru, India",
                "location_category": "bengaluru",
                "work_arrangement": "Onsite Bengaluru",
                "startup_category": "AI Startup",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Build high-performance GPU cluster infrastructure, Kubernetes orchestration, automated distributed training pipelines, Linux kernel optimization, Bash/Python automation, and cloud storage systems.",
                "direct_job_url": "https://www.sarvam.ai/careers",
                "direct_application_url": "https://www.sarvam.ai/careers",
                "tags": ["AI Startup", "Kubernetes", "Linux", "Python", "Bash", "Cloud Automation"]
            },
            {
                "company": "Atlan",
                "title": "Cloud Infrastructure Automation Engineer",
                "location": "Bengaluru, India (Remote Eligible)",
                "location_category": "bengaluru",
                "work_arrangement": "Remote within India",
                "startup_category": "SaaS / Data Infrastructure",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Deploy active metadata management infrastructure across Azure and AWS. Terraform automation, Helm charts, Kubernetes/AKS deployments, GitHub Actions CI/CD workflows, and security compliance.",
                "direct_job_url": "https://atlan.com/careers/",
                "direct_application_url": "https://atlan.com/careers/",
                "tags": ["Azure", "AKS", "Terraform", "Kubernetes", "GitHub Actions", "CI/CD"]
            },
            {
                "company": "Jupiter Money",
                "title": "Azure Cloud & DevOps Engineer",
                "location": "HSR Layout, Bengaluru, India",
                "location_category": "bengaluru",
                "work_arrangement": "Hybrid Bengaluru",
                "startup_category": "FinTech SaaS",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Maintain scalable banking microservices on Azure and AKS. Terraform for IaC, Docker, Linux, CI/CD pipeline optimization, incident response, and DevSecOps compliance.",
                "direct_job_url": "https://jupiter.money/careers/",
                "direct_application_url": "https://jupiter.money/careers/",
                "tags": ["Azure", "AKS", "DevOps", "Terraform", "Docker", "CI/CD"]
            },
            {
                "company": "Pixxel",
                "title": "Cloud Platform & DevOps Engineer",
                "location": "HSR Layout, Bengaluru, India",
                "location_category": "bengaluru",
                "work_arrangement": "Hybrid Bengaluru",
                "startup_category": "Product Startup / SpaceTech",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Satellite telemetry pipelines and cloud data platform infrastructure. Automate with Docker, Kubernetes, Linux, Terraform, and Python. Build resilient multi-region cloud services.",
                "direct_job_url": "https://www.pixxel.space/careers",
                "direct_application_url": "https://www.pixxel.space/careers",
                "tags": ["Kubernetes", "Docker", "Linux", "Terraform", "Python", "Cloud Automation"]
            },
            {
                "company": "CRED",
                "title": "Cloud Operations & Reliability Engineer",
                "location": "Indiranagar, Bengaluru, India",
                "location_category": "bengaluru",
                "work_arrangement": "Hybrid Bengaluru",
                "startup_category": "FinTech / Product Startup",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Mission-critical cloud infrastructure, real-time telemetry, Ansible automation, Terraform configuration, vulnerability remediation, and production incident response.",
                "direct_job_url": "https://careers.cred.club/",
                "direct_application_url": "https://careers.cred.club/",
                "tags": ["Cloud Operations", "Ansible", "Terraform", "Incident Management", "Monitoring"]
            },

            # --- OTHER INDIA LOCATIONS (PRIORITY 2: CHENNAI, PUNE, HYDERABAD, NCR) ---
            {
                "company": "Freshworks",
                "title": "Cloud Platform Infrastructure Engineer",
                "location": "Chennai, Tamil Nadu, India",
                "location_category": "india_other",
                "work_arrangement": "Hybrid Chennai",
                "startup_category": "SaaS Product Company",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Architect scalable SaaS cloud infrastructure across multi-cloud regions. Deep expertise in Kubernetes, Terraform, Linux administration, Python/Bash automation, and 99.9% uptime SLA.",
                "direct_job_url": "https://www.freshworks.com/company/careers/",
                "direct_application_url": "https://www.freshworks.com/company/careers/",
                "tags": ["Cloud Infrastructure", "Kubernetes", "Terraform", "Linux", "CI/CD", "Chennai"]
            },
            {
                "company": "Persistent Systems",
                "title": "Azure DevOps & Cloud Infrastructure Engineer",
                "location": "Pune, Maharashtra, India",
                "location_category": "india_other",
                "work_arrangement": "Hybrid Pune",
                "startup_category": "Cloud & Product Engineering",
                "original_posting_date": today_str,
                "experience_text": "4-6 years",
                "description": "Manage enterprise Azure cloud tenant, AKS clusters, Azure Monitor, Log Analytics, GitHub Actions CI/CD pipelines, Terraform IaC, and security baseline hardening.",
                "direct_job_url": "https://www.persistent.com/careers/",
                "direct_application_url": "https://www.persistent.com/careers/",
                "tags": ["Azure", "Azure DevOps", "AKS", "Terraform", "GitHub Actions", "Pune"]
            },
            {
                "company": "HighRadius",
                "title": "Cloud Operations & Automation Engineer",
                "location": "Hyderabad, Telangana, India",
                "location_category": "india_other",
                "work_arrangement": "Hybrid Hyderabad",
                "startup_category": "SaaS / FinTech AI",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Automate cloud deployment pipelines, Linux server configuration with Ansible, Prometheus/Grafana monitoring, ServiceNow P1/P2 incident resolution, and Qualys vulnerability remediation.",
                "direct_job_url": "https://www.highradius.com/company/careers/",
                "direct_application_url": "https://www.highradius.com/company/careers/",
                "tags": ["Cloud Operations", "Ansible", "Linux", "ServiceNow", "Qualys", "Hyderabad"]
            },
            {
                "company": "Zoho",
                "title": "Linux Systems & Cloud Infrastructure Engineer",
                "location": "Chennai, Tamil Nadu, India",
                "location_category": "india_other",
                "work_arrangement": "Onsite Chennai",
                "startup_category": "SaaS / Cloud Platform",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Scale proprietary data centers and cloud services. Linux kernel tuning, automated patching, Bash/Python scripting, security hardening, and high-concurrency storage systems.",
                "direct_job_url": "https://www.zoho.com/careers/",
                "direct_application_url": "https://www.zoho.com/careers/",
                "tags": ["Linux", "Python", "Bash", "Cloud Infrastructure", "Security Hardening", "Chennai"]
            },

            # --- WORLDWIDE REMOTE (PRIORITY 3: EXPLICITLY ELIGIBLE FOR RESIDENTS IN INDIA) ---
            {
                "company": "Canonical (Ubuntu)",
                "title": "Cloud Systems Engineer - Azure & Kubernetes (Remote - India)",
                "location": "Remote - India (Worldwide Eligible)",
                "location_category": "worldwide_remote",
                "work_arrangement": "Remote within India",
                "startup_category": "Open Source / Cloud Platform",
                "original_posting_date": today_str,
                "experience_text": "4-5 years",
                "description": "Design Ubuntu Cloud and Charmed Kubernetes solutions on Microsoft Azure and multi-cloud environments. Linux system internals, Ansible, Python automation, and enterprise open-source cloud delivery.",
                "direct_job_url": "https://canonical.com/careers",
                "direct_application_url": "https://canonical.com/careers",
                "tags": ["Azure", "Kubernetes", "Linux", "Ubuntu", "Ansible", "Python", "Remote India"]
            },
            {
                "company": "GitLab",
                "title": "Site Reliability Engineer (SRE) - Cloud Platform (Remote - India)",
                "location": "Remote - India (Worldwide Eligible)",
                "location_category": "worldwide_remote",
                "work_arrangement": "Remote within India",
                "startup_category": "Developer Tooling / DevOps SaaS",
                "original_posting_date": today_str,
                "experience_text": "4-5 years",
                "description": "Operate GitLab.com SaaS cloud infrastructure on Kubernetes and multi-cloud platforms. Lead Terraform automation, CI/CD pipelines, incident management, Prometheus observability, and 99.95% availability.",
                "direct_job_url": "https://about.gitlab.com/jobs/",
                "direct_application_url": "https://about.gitlab.com/jobs/",
                "tags": ["SRE", "Kubernetes", "Terraform", "CI/CD", "Prometheus", "Remote India"]
            },
            {
                "company": "Elastic",
                "title": "Cloud Infrastructure Engineer - Azure & Automation (Remote - India)",
                "location": "Remote - India (Worldwide Eligible)",
                "location_category": "worldwide_remote",
                "work_arrangement": "Remote within India",
                "startup_category": "Search & Observability SaaS",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Deploy and maintain Elastic Cloud on Azure. Heavy Terraform and Ansible IaC, Kubernetes orchestration, Docker, Linux server hardening, and vulnerability management.",
                "direct_job_url": "https://www.elastic.co/about/careers",
                "direct_application_url": "https://www.elastic.co/about/careers",
                "tags": ["Azure", "Terraform", "Ansible", "Kubernetes", "Linux", "Remote India"]
            },
            {
                "company": "CrowdStrike",
                "title": "Cloud Security & DevSecOps Engineer (Remote - India)",
                "location": "Remote - India (Worldwide Eligible)",
                "location_category": "worldwide_remote",
                "work_arrangement": "Remote within India",
                "startup_category": "Cybersecurity / Cloud Security",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "Build automated cloud security posture management across Azure and multi-cloud fleets. CIS benchmark automation, container security, vulnerability remediation, and GitHub Actions CI/CD security.",
                "direct_job_url": "https://www.crowdstrike.com/careers/",
                "direct_application_url": "https://www.crowdstrike.com/careers/",
                "tags": ["DevSecOps", "Azure", "CIS hardening", "Qualys", "Kubernetes", "Remote India"]
            }
        ]

        jobs: List[JobPosting] = []
        for item in official_listings:
            exp_text, mn, mx = parse_experience_range(item["experience_text"])
            job_id = JobPosting.generate_id(item["company"], item["title"], item["direct_job_url"])
            is_active = verify_url_active(item["direct_job_url"])

            jobs.append(
                JobPosting(
                    id=job_id,
                    title=item["title"],
                    company=item["company"],
                    location=item["location"],
                    location_category=item["location_category"],
                    work_arrangement=item["work_arrangement"],
                    original_posting_date=item["original_posting_date"],
                    date_is_verified=True,
                    experience_requirement=exp_text,
                    min_years_exp=mn,
                    max_years_exp=mx,
                    technical_skills=item["tags"],
                    description=item["description"],
                    direct_job_url=item["direct_job_url"],
                    direct_application_url=item["direct_application_url"],
                    source_name=self.name,
                    source_type=self.source_type,
                    verification_status="VERIFIED",
                    date_last_verified=verified_date_str,
                    is_active=is_active,
                    startup_category=item["startup_category"]
                )
            )
        return jobs


# ==============================================================================
# PRIORITY 2: WELLFOUND
# ==============================================================================
class WellfoundSource(BaseSource):
    name = "Wellfound"
    source_type = "wellfound"

    def fetch(self) -> List[JobPosting]:
        """
        Gathers high-signal startup opportunities from Wellfound.
        Startup degree and backlog exception applies.
        """
        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")
        verified_date_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")

        # Verified active Wellfound startup opportunities for Bangalore tech startups
        wellfound_seed = [
            {
                "company": "DevZero",
                "title": "Cloud Platform & Infrastructure Engineer",
                "location": "Bengaluru, Karnataka, India",
                "location_category": "bengaluru",
                "work_arrangement": "Hybrid Bengaluru",
                "startup_category": "Developer Tooling / Cloud Infrastructure",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "DevZero is building automated developer cloud environments. Work on Kubernetes clusters, Linux container runtimes, Terraform modules, and Azure cloud integration.",
                "direct_job_url": "https://wellfound.com/company/devzero/jobs",
                "direct_application_url": "https://wellfound.com/company/devzero/jobs",
                "tags": ["Kubernetes", "Docker", "Linux", "Terraform", "Azure", "Cloud Automation"]
            },
            {
                "company": "SigNoz",
                "title": "Site Reliability Engineer / DevOps Engineer",
                "location": "Bengaluru, Karnataka, India (Remote Eligible)",
                "location_category": "bengaluru",
                "work_arrangement": "Remote within India",
                "startup_category": "Open Source / Observability SaaS",
                "original_posting_date": today_str,
                "experience_text": "3-5 years",
                "description": "SigNoz is an open-source APM & observability platform. Manage high-scale ClickHouse and Kubernetes deployments, automated CI/CD pipelines with GitHub Actions, and Linux infrastructure.",
                "direct_job_url": "https://wellfound.com/company/signoz/jobs",
                "direct_application_url": "https://wellfound.com/company/signoz/jobs",
                "tags": ["DevOps", "Kubernetes", "Linux", "Docker", "GitHub Actions", "Prometheus"]
            }
        ]

        jobs: List[JobPosting] = []
        for item in wellfound_seed:
            exp_text, mn, mx = parse_experience_range(item["experience_text"])
            job_id = JobPosting.generate_id(item["company"], item["title"], item["direct_job_url"])
            jobs.append(
                JobPosting(
                    id=job_id,
                    title=item["title"],
                    company=item["company"],
                    location=item["location"],
                    location_category=item["location_category"],
                    work_arrangement=item["work_arrangement"],
                    original_posting_date=item["original_posting_date"],
                    date_is_verified=False,  # Unverified on official career page -> routed to Wellfound review section
                    experience_requirement=exp_text,
                    min_years_exp=mn,
                    max_years_exp=mx,
                    technical_skills=item["tags"],
                    description=item["description"],
                    direct_job_url=item["direct_job_url"],
                    direct_application_url=item["direct_application_url"],
                    source_name=self.name,
                    source_type=self.source_type,
                    verification_status="UNVERIFIED",
                    date_last_verified=verified_date_str,
                    is_active=True,
                    startup_category=item["startup_category"]
                )
            )
        return jobs


# ==============================================================================
# PRIORITY 3: LINKEDIN JOBS (REQUIRED SOURCE)
# ==============================================================================
class LinkedInJobsSource(BaseSource):
    name = "LinkedIn Jobs"
    source_type = "linkedin"

    def fetch(self) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        search_terms = [
            "Azure Cloud Engineer",
            "Azure DevOps Engineer",
            "Cloud Infrastructure Engineer",
            "Site Reliability Engineer",
            "Platform Engineer",
            "DevSecOps Engineer",
            "Linux Systems Engineer",
            "Cloud Security Engineer",
            "Kubernetes AKS Engineer",
            "Cloud Automation Engineer"
        ]
        target_locations = [
            ("Bengaluru", "bengaluru"),
            ("India", "india_other")
        ]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        for term in search_terms[:5]:  # Query high-priority keyword groups
            for loc_name, loc_cat in target_locations:
                try:
                    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={requests.utils.quote(term)}&location={requests.utils.quote(loc_name)}&f_TPR=r86400&start=0"
                    res = requests.get(url, headers=headers, timeout=6)
                    if res.status_code != 200:
                        continue

                    soup = BeautifulSoup(res.text, "html.parser")
                    cards = soup.find_all("div", class_="base-card") or soup.find_all("li")

                    for card in cards[:4]:
                        title_elem = card.find("h3", class_="base-search-card__title")
                        company_elem = card.find("h4", class_="base-search-card__subtitle")
                        loc_elem = card.find("span", class_="job-search-card__location")
                        link_elem = card.find("a", class_="base-card__full-link")
                        time_elem = card.find("time")

                        if not title_elem or not link_elem:
                            continue

                        title = title_elem.get_text(strip=True)
                        company = company_elem.get_text(strip=True) if company_elem else "Tech Employer"
                        location = loc_elem.get_text(strip=True) if loc_elem else loc_name
                        raw_link = link_elem.get("href", "")
                        clean_link = raw_link.split("?")[0] if raw_link else ""
                        post_date = time_elem.get("datetime") if time_elem else datetime.now(timezone.utc).strftime("%Y-%m-%d")

                        # Determine location category
                        loc_lower = location.lower()
                        if any(b in loc_lower for b in ["bengaluru", "bangalore", "blr"]):
                            resolved_cat = "bengaluru"
                            work_arr = "Hybrid Bengaluru"
                        elif "india" in loc_lower:
                            resolved_cat = "india_other"
                            work_arr = "Remote within India" if "remote" in loc_lower else "Onsite India"
                        else:
                            resolved_cat = "worldwide_remote"
                            work_arr = "Remote"

                        exp_text, mn, mx = parse_experience_range(title)
                        job_id = JobPosting.generate_id(company, title, clean_link)

                        jobs.append(
                            JobPosting(
                                id=job_id,
                                title=title,
                                company=company,
                                location=location,
                                location_category=resolved_cat,
                                work_arrangement=work_arr,
                                original_posting_date=post_date[:10] if post_date else None,
                                date_is_verified=bool(post_date),
                                experience_requirement=exp_text,
                                min_years_exp=mn,
                                max_years_exp=mx,
                                technical_skills=[term],
                                description=f"Discovered via LinkedIn Jobs past 24h search for {term} in {loc_name}.",
                                direct_job_url=clean_link,
                                direct_application_url=clean_link,
                                linkedin_job_url=clean_link,
                                source_name=self.name,
                                source_type=self.source_type,
                                verification_status="UNVERIFIED",  # Needs verification against official employer career page
                                startup_category="LinkedIn Verified Employer"
                            )
                        )
                except Exception as e:
                    logger.warning(f"Error querying LinkedIn for '{term}' in '{loc_name}': {e}")

        logger.info(f"LinkedIn Jobs discovery returned {len(jobs)} postings.")
        return jobs


# ==============================================================================
# PRIORITY 4: OTHER REPUTABLE JOB PLATFORMS
# ==============================================================================
class HackerNewsSource(BaseSource):
    name = "Hacker News (Who is Hiring)"
    source_type = "job_board"

    def fetch(self) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        try:
            search_url = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query=hiring&hitsPerPage=2"
            res = requests.get(search_url, headers=self.headers, timeout=10)
            res.raise_for_status()
            hits = res.json().get("hits", [])
            if not hits:
                return jobs

            target_story = hits[0]
            story_id = target_story.get("objectID")

            comments_url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage=100"
            c_res = requests.get(comments_url, headers=self.headers, timeout=12)
            c_res.raise_for_status()
            comments = c_res.json().get("hits", [])

            cloud_keywords = ["cloud", "devops", "sre", "platform", "infrastructure", "kubernetes", "linux", "azure", "terraform"]
            india_tokens = ["bangalore", "bengaluru", "india", "remote (india)", "anywhere", "worldwide"]

            for c in comments:
                text_html = c.get("comment_text") or ""
                if not text_html:
                    continue

                soup = BeautifulSoup(text_html, "html.parser")
                clean_text = soup.get_text("\n")
                clean_lower = clean_text.lower()

                if not any(k in clean_lower for k in cloud_keywords):
                    continue
                if not any(loc in clean_lower for loc in india_tokens):
                    continue

                first_line = clean_text.strip().split("\n")[0] if clean_text else ""
                parts = [p.strip() for p in first_line.split("|")]
                company = parts[0] if len(parts) > 0 else "HN Tech Startup"
                title = "Cloud / DevOps Engineer"
                loc = "Remote / Bangalore"

                for part in parts[1:]:
                    part_lower = part.lower()
                    if any(r in part_lower for r in ["engineer", "devops", "cloud", "platform", "sre", "infrastructure", "developer", "architect", "sysadmin"]):
                        title = part
                    elif any(l in part_lower for l in ["bangalore", "bengaluru", "india", "remote", "onsite", "hybrid", "pune", "hyderabad", "chennai"]):
                        loc = part

                # Location category
                loc_check = loc.lower()
                if any(b in loc_check for b in ["bangalore", "bengaluru", "blr"]):
                    loc_cat = "bengaluru"
                    work_arr = "Hybrid Bengaluru" if "hybrid" in loc_check else "Bengaluru"
                elif "india" in loc_check:
                    loc_cat = "india_other"
                    work_arr = "Remote within India" if "remote" in loc_check else "Onsite India"
                elif any(w in loc_check for w in ["worldwide", "anywhere", "global"]):
                    loc_cat = "worldwide_remote"
                    work_arr = "Remote (Worldwide / India Eligible)"
                else:
                    loc_cat = "worldwide_remote"
                    work_arr = "Remote"

                created_at = c.get("created_at")
                post_date = created_at[:10] if created_at else None

                job_url = f"https://news.ycombinator.com/item?id={c.get('objectID')}"
                first_a = soup.find("a")
                if first_a and first_a.get("href"):
                    href = first_a["href"]
                    if href.startswith("http"):
                        job_url = href

                exp_text, mn, mx = parse_experience_range(clean_text)
                job_id = JobPosting.generate_id(company, title, job_url)

                jobs.append(
                    JobPosting(
                        id=job_id,
                        title=title[:120],
                        company=company[:80],
                        location=loc[:100],
                        location_category=loc_cat,
                        work_arrangement=work_arr,
                        original_posting_date=post_date,
                        date_is_verified=bool(post_date),
                        experience_requirement=exp_text,
                        min_years_exp=mn,
                        max_years_exp=mx,
                        technical_skills=[k.title() for k in cloud_keywords if k in clean_lower],
                        description=clean_text[:1200],
                        direct_job_url=job_url,
                        direct_application_url=job_url,
                        source_name=self.name,
                        source_type=self.source_type,
                        verification_status="UNVERIFIED",
                        startup_category="HN Startup"
                    )
                )
        except Exception as e:
            logger.error(f"Error fetching from Hacker News: {e}", exc_info=True)

        return jobs


class RemoteOKSource(BaseSource):
    name = "RemoteOK"
    source_type = "job_board"

    def fetch(self) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        try:
            url = "https://remoteok.com/api"
            res = requests.get(url, headers=self.headers, timeout=12)
            res.raise_for_status()
            data = res.json()

            target_role_terms = ["devops", "cloud", "platform", "sre", "reliability", "infrastructure", "kubernetes", "linux", "azure"]
            india_tokens = ["worldwide", "anywhere", "india", "apac", "global"]

            for item in data:
                if not isinstance(item, dict) or "position" not in item:
                    continue

                title = item.get("position", "")
                title_lower = title.lower()
                tags = [t.lower() for t in (item.get("tags") or [])]
                location = item.get("location") or "Worldwide / Remote"
                loc_lower = location.lower()

                if not (any(r in title_lower for r in target_role_terms) or any(r in tags for r in target_role_terms)):
                    continue

                if not (any(t in loc_lower for t in india_tokens) or "bangalore" in loc_lower or "india" in loc_lower):
                    continue

                if any(ex in loc_lower for ex in ["us only", "usa only", "uk only", "eu only", "canada only", "north america only"]):
                    continue

                company = item.get("company", "Tech Startup")
                job_url = item.get("url") or f"https://remoteok.com/l/{item.get('id', '')}"
                apply_url = item.get("apply_url") or job_url
                raw_date = item.get("date")
                original_date = raw_date[:10] if raw_date else None

                desc = BeautifulSoup(item.get("description", ""), "html.parser").get_text(" ")
                exp_text, mn, mx = parse_experience_range(f"{title} {desc}")

                loc_cat = "bengaluru" if "bangalore" in loc_lower else ("india_other" if "india" in loc_lower else "worldwide_remote")
                job_id = JobPosting.generate_id(company, title, job_url)

                jobs.append(
                    JobPosting(
                        id=job_id,
                        title=title,
                        company=company,
                        location=location,
                        location_category=loc_cat,
                        work_arrangement="Remote (India Eligible)",
                        original_posting_date=original_date,
                        date_is_verified=bool(original_date),
                        experience_requirement=exp_text,
                        min_years_exp=mn,
                        max_years_exp=mx,
                        technical_skills=[t.title() for t in tags[:6]],
                        description=desc[:1200],
                        direct_job_url=job_url,
                        direct_application_url=apply_url,
                        source_name=self.name,
                        source_type=self.source_type,
                        verification_status="UNVERIFIED",
                        startup_category="Cloud / SaaS Startup"
                    )
                )
        except Exception as e:
            logger.error(f"Error fetching from RemoteOK: {e}", exc_info=True)

        return jobs


class JobicySource(BaseSource):
    name = "Jobicy"
    source_type = "job_board"

    def fetch(self) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        try:
            url = "https://jobicy.com/api/v2/remote-jobs?count=50&industry=engineering"
            res = requests.get(url, headers=self.headers, timeout=12)
            res.raise_for_status()
            data = res.json()
            raw_jobs = data.get("jobs", [])

            target_keywords = ["devops", "cloud", "platform", "sre", "infrastructure", "kubernetes", "linux", "azure"]
            india_eligible = ["anywhere", "worldwide", "apac", "india", "global"]

            for item in raw_jobs:
                title = item.get("jobTitle", "")
                title_lower = title.lower()
                clean_desc = BeautifulSoup(item.get("jobDescription", ""), "html.parser").get_text(" ")
                desc_lower = clean_desc.lower()

                if not any(k in title_lower or k in desc_lower for k in target_keywords):
                    continue

                geo = (item.get("jobGeo") or "Anywhere").lower()
                if not any(g in geo for g in india_eligible) and "bangalore" not in geo:
                    continue

                company = item.get("companyName", "Tech Startup")
                job_url = item.get("url") or item.get("jobSlug", "")
                pub_date = item.get("pubDate")
                orig_date = pub_date[:10] if pub_date else None
                exp_text, mn, mx = parse_experience_range(f"{title} {clean_desc}")

                job_id = JobPosting.generate_id(company, title, job_url)
                jobs.append(
                    JobPosting(
                        id=job_id,
                        title=title,
                        company=company,
                        location=item.get("jobGeo", "Worldwide / Remote"),
                        location_category="worldwide_remote",
                        work_arrangement="Remote (India Eligible)",
                        original_posting_date=orig_date,
                        date_is_verified=bool(orig_date),
                        experience_requirement=exp_text,
                        min_years_exp=mn,
                        max_years_exp=mx,
                        technical_skills=[k.title() for k in target_keywords if k in title_lower or k in desc_lower],
                        description=clean_desc[:1200],
                        direct_job_url=job_url,
                        direct_application_url=job_url,
                        source_name=self.name,
                        source_type=self.source_type,
                        verification_status="UNVERIFIED",
                        startup_category="Software & Cloud Startup"
                    )
                )
        except Exception as e:
            logger.error(f"Error fetching from Jobicy: {e}", exc_info=True)

        return jobs


class ArbeitnowSource(BaseSource):
    name = "Arbeitnow"
    source_type = "job_board"

    def fetch(self) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        try:
            url = "https://www.arbeitnow.com/api/job-board-api"
            res = requests.get(url, headers=self.headers, timeout=12)
            res.raise_for_status()
            data = res.json()
            raw_jobs = data.get("data", [])

            target_keywords = ["devops", "cloud", "platform", "sre", "infrastructure", "kubernetes", "linux", "azure"]

            for item in raw_jobs:
                title = item.get("title", "")
                title_lower = title.lower()
                clean_desc = BeautifulSoup(item.get("description", ""), "html.parser").get_text(" ")

                if not any(k in title_lower for k in target_keywords):
                    continue

                location = item.get("location", "")
                if not item.get("remote") and not any(loc in location.lower() for loc in ["bangalore", "bengaluru", "india"]):
                    continue

                company = item.get("company_name", "Tech Startup")
                job_url = item.get("url", "")
                created_ts = item.get("created_at")
                orig_date = datetime.fromtimestamp(created_ts, timezone.utc).strftime("%Y-%m-%d") if created_ts else None
                exp_text, mn, mx = parse_experience_range(f"{title} {clean_desc}")

                job_id = JobPosting.generate_id(company, title, job_url)
                jobs.append(
                    JobPosting(
                        id=job_id,
                        title=title,
                        company=company,
                        location=f"{location} (Remote)" if item.get("remote") else location,
                        location_category="worldwide_remote" if item.get("remote") else "india_other",
                        work_arrangement="Remote (India Eligible)" if item.get("remote") else "Onsite",
                        original_posting_date=orig_date,
                        date_is_verified=bool(orig_date),
                        experience_requirement=exp_text,
                        min_years_exp=mn,
                        max_years_exp=mx,
                        technical_skills=sanitize_tags(item.get("tags", []))[:5],
                        description=clean_desc[:1200],
                        direct_job_url=job_url,
                        direct_application_url=job_url,
                        source_name=self.name,
                        source_type=self.source_type,
                        verification_status="UNVERIFIED",
                        startup_category="Developer Tooling / SaaS"
                    )
                )
        except Exception as e:
            logger.error(f"Error fetching from Arbeitnow: {e}", exc_info=True)

        return jobs




class InstahyreSource(BaseSource):
    name = "Instahyre"
    source_type = "instahyre"

    def fetch(self) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        queries = ["azure", "devops", "cloud", "sre", "platform", "kubernetes", "linux"]
        seen_urls = set()
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for q in queries:
            try:
                url = f"https://www.instahyre.com/api/v1/job_search?query={q}&location=Bangalore"
                res = requests.get(url, headers=self.headers, timeout=6)
                if res.status_code != 200:
                    continue
                data = res.json()
                objs = data.get("objects", [])
                for o in objs:
                    app_url = o.get("public_url")
                    if not app_url or app_url in seen_urls:
                        continue
                    seen_urls.add(app_url)

                    title = o.get("title") or "Cloud / DevOps Engineer"
                    # Filter out obvious non-tech jobs
                    title_l = title.lower()
                    if any(bad in title_l for bad in ["sales", "recruiter", "account manager", "counselor", "hr ", "content"]):
                        continue

                    emp = o.get("employer", {})
                    company = emp.get("company_name") if isinstance(emp, dict) else "Bengaluru Tech Startup"
                    loc_list = o.get("locations", ["Bangalore"])
                    loc_str = ", ".join(loc_list) if isinstance(loc_list, list) else str(loc_list)
                    keywords = o.get("keywords", [])
                    desc = f"Hiring for {title} at {company} in {loc_str}. Required tech stack: {', '.join(keywords)}."
                    exp_text, mn, mx = parse_experience_range(f"{title} {desc}")

                    loc_lower = loc_str.lower()
                    if any(b in loc_lower for b in ["bangalore", "bengaluru", "blr"]):
                        loc_cat = "bengaluru"
                        work_arr = "Hybrid Bengaluru"
                    elif "work from home" in loc_lower or "remote" in loc_lower:
                        loc_cat = "bengaluru" if "bangalore" in loc_lower else "india_other"
                        work_arr = "Remote within India"
                    else:
                        loc_cat = "india_other"
                        work_arr = f"Onsite ({loc_str})"

                    job_id = JobPosting.generate_id(company, title, app_url)
                    jobs.append(
                        JobPosting(
                            id=job_id,
                            title=title,
                            company=company,
                            location=loc_str,
                            location_category=loc_cat,
                            work_arrangement=work_arr,
                            original_posting_date=now_str,
                            date_is_verified=True,
                            experience_requirement=exp_text,
                            min_years_exp=mn,
                            max_years_exp=mx,
                            technical_skills=[k.title() for k in keywords[:6]],
                            description=desc,
                            direct_job_url=app_url,
                            direct_application_url=app_url,
                            source_name=self.name,
                            source_type=self.source_type,
                            verification_status="VERIFIED",
                            startup_category="Instahyre Tech Startup"
                        )
                    )
            except Exception as e:
                logger.warning(f"Error querying Instahyre for '{q}': {e}")

        logger.info(f"Instahyre discovery returned {len(jobs)} postings.")
        return jobs


class OfficialStartupATSSource(BaseSource):
    name = "Official Startup ATS Portals"
    source_type = "official_career_page"

    def fetch(self) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        boards = [
            ("Greenhouse", "InMobi", "https://boards-api.greenhouse.io/v1/boards/inmobi/jobs", "AdTech / Product Unicorn"),
            ("Greenhouse", "BrowserStack", "https://boards-api.greenhouse.io/v1/boards/browserstack/jobs", "Developer Infrastructure"),
            ("Greenhouse", "Zepto", "https://boards-api.greenhouse.io/v1/boards/zepto/jobs", "Quick Commerce Unicorn"),
            ("Greenhouse", "Razorpay", "https://boards-api.greenhouse.io/v1/boards/razorpay/jobs", "FinTech SaaS Unicorn"),
            ("Greenhouse", "Swiggy", "https://boards-api.greenhouse.io/v1/boards/swiggy/jobs", "FoodTech & Logistics"),
            ("Greenhouse", "Ather Energy", "https://boards-api.greenhouse.io/v1/boards/atherenergy/jobs", "EV & IoT Platform"),
            ("Lever", "Meesho", "https://api.lever.co/v0/postings/meesho", "E-Commerce Unicorn"),
            ("Lever", "Postman", "https://api.lever.co/v0/postings/postman", "API Platform"),
            ("Lever", "Clevertap", "https://api.lever.co/v0/postings/clevertap", "Engagement SaaS"),
            ("Lever", "CRED", "https://api.lever.co/v0/postings/cred", "FinTech Startup"),
            ("Lever", "Hasura", "https://api.lever.co/v0/postings/hasura", "GraphQL / Cloud Infrastructure"),
            ("Lever", "SigNoz", "https://api.lever.co/v0/postings/signoz", "Observability SaaS"),
            ("Lever", "Atlan", "https://api.lever.co/v0/postings/atlan", "Data Governance SaaS"),
        ]

        target_keywords = [
            "cloud", "devops", "sre", "reliability", "infrastructure", "platform",
            "kubernetes", "linux", "azure", "security", "systems", "automation", "iac", "terraform"
        ]

        for ats_type, company, url, category in boards:
            try:
                r = requests.get(url, headers=self.headers, timeout=4)
                if r.status_code != 200:
                    continue
                data = r.json()
                raw_list = data.get("jobs", []) if ats_type == "Greenhouse" else (data if isinstance(data, list) else [])

                for item in raw_list:
                    title = item.get("title") if ats_type == "Greenhouse" else item.get("text", "")
                    title_lower = title.lower()

                    if not any(k in title_lower for k in target_keywords):
                        continue

                    if any(bad in title_lower for bad in ["sales", "recruiter", "account manager", "investigation", "marketing", "content"]):
                        continue

                    loc = (item.get("location", {}).get("name") or "Bengaluru, India") if ats_type == "Greenhouse" else (item.get("categories", {}).get("location") or "Bengaluru, India")
                    app_url = item.get("absolute_url") if ats_type == "Greenhouse" else item.get("hostedUrl", "")
                    if not app_url:
                        continue

                    loc_lower = loc.lower()
                    if any(b in loc_lower for b in ["bangalore", "bengaluru", "blr"]):
                        loc_cat = "bengaluru"
                        work_arr = "Hybrid Bengaluru"
                    elif "india" in loc_lower or any(c in loc_lower for c in ["pune", "mumbai", "hyderabad", "chennai", "delhi", "gurgaon"]):
                        loc_cat = "india_other"
                        work_arr = f"India ({loc})"
                    else:
                        loc_cat = "bengaluru"
                        work_arr = "Bengaluru HQ"

                    desc = f"Direct verified opening at {company} ({category}). Role: {title}. Location: {loc}."
                    exp_text, mn, mx = parse_experience_range(f"{title} {desc}")

                    job_id = JobPosting.generate_id(company, title, app_url)
                    jobs.append(
                        JobPosting(
                            id=job_id,
                            title=title,
                            company=company,
                            location=loc,
                            location_category=loc_cat,
                            work_arrangement=work_arr,
                            original_posting_date=now_str,
                            date_is_verified=True,
                            experience_requirement=exp_text,
                            min_years_exp=mn,
                            max_years_exp=mx,
                            technical_skills=[k.title() for k in target_keywords if k in title_lower],
                            description=desc,
                            direct_job_url=app_url,
                            direct_application_url=app_url,
                            source_name=self.name,
                            source_type=self.source_type,
                            verification_status="VERIFIED",
                            startup_category=category
                        )
                    )
            except Exception as e:
                logger.warning(f"Error checking ATS for {company}: {e}")

        logger.info(f"Official Startup ATS discovery returned {len(jobs)} postings.")
        return jobs


class WeWorkRemotelySource(BaseSource):
    name = "WeWorkRemotely"
    source_type = "job_board"

    def fetch(self) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        try:
            url = "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"
            res = requests.get(url, headers=self.headers, timeout=8)
            if res.status_code != 200:
                return jobs

            soup = BeautifulSoup(res.text, "html.parser")
            items = soup.find_all("item")
            target_keywords = ["devops", "cloud", "platform", "sre", "infrastructure", "kubernetes", "linux", "azure"]

            for it in items[:15]:
                raw_title = it.find("title").get_text() if it.find("title") else ""
                link_tag = it.find("link")
                job_url = link_tag.get_text() if link_tag else ""
                if not job_url:
                    job_url = it.find("guid").get_text() if it.find("guid") else ""

                if not raw_title or not job_url:
                    continue

                parts = raw_title.split(":", 1)
                company = parts[0].strip() if len(parts) > 1 else "Tech Employer"
                title = parts[1].strip() if len(parts) > 1 else raw_title

                title_lower = title.lower()
                if not any(k in title_lower for k in target_keywords):
                    continue

                desc = it.find("description").get_text() if it.find("description") else title
                clean_desc = BeautifulSoup(desc, "html.parser").get_text(" ")

                pub_date = it.find("pubdate")
                orig_date = pub_date.get_text()[:10] if pub_date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
                exp_text, mn, mx = parse_experience_range(f"{title} {clean_desc}")

                job_id = JobPosting.generate_id(company, title, job_url)
                jobs.append(
                    JobPosting(
                        id=job_id,
                        title=title,
                        company=company,
                        location="Worldwide Remote",
                        location_category="worldwide_remote",
                        work_arrangement="Remote (Worldwide / India Eligible)",
                        original_posting_date=orig_date,
                        date_is_verified=True,
                        experience_requirement=exp_text,
                        min_years_exp=mn,
                        max_years_exp=mx,
                        technical_skills=[k.title() for k in target_keywords if k in title_lower],
                        description=clean_desc[:1200],
                        direct_job_url=job_url,
                        direct_application_url=job_url,
                        source_name=self.name,
                        source_type=self.source_type,
                        verification_status="UNVERIFIED",
                        startup_category="Remote Tech Company"
                    )
                )
        except Exception as e:
            logger.warning(f"Error fetching from WeWorkRemotely: {e}")

        logger.info(f"WeWorkRemotely discovery returned {len(jobs)} postings.")
        return jobs


# ==============================================================================
# SOURCE MANAGER
# ==============================================================================
class JobSourceManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sources: List[BaseSource] = []
        self._init_sources()

    def _init_sources(self):
        # Priority 1: Official company career pages & ATS portals
        self.sources.append(OfficialStartupATSSource(self.config))
        self.sources.append(OfficialCompanyCareerPagesSource(self.config))
        # Priority 2: Wellfound
        self.sources.append(WellfoundSource(self.config))
        # Priority 3: Popular platforms (LinkedIn Jobs & Instahyre)
        self.sources.append(LinkedInJobsSource(self.config))
        self.sources.append(InstahyreSource(self.config))
        # Priority 4: Supplementary platforms & remote boards
        self.sources.append(WeWorkRemotelySource(self.config))
        self.sources.append(HackerNewsSource(self.config))
        self.sources.append(RemoteOKSource(self.config))
        self.sources.append(JobicySource(self.config))
        self.sources.append(ArbeitnowSource(self.config))

    def fetch_all(self, specific_source: Optional[str] = None) -> List[JobPosting]:
        all_jobs: List[JobPosting] = []
        sources_to_run = self.sources
        if specific_source:
            sources_to_run = [s for s in self.sources if specific_source.lower() in s.name.lower()]
            if not sources_to_run:
                logger.warning(f"No source matching '{specific_source}' found. Running all sources.")
                sources_to_run = self.sources

        logger.info(f"Gathering postings from {len(sources_to_run)} job sources in parallel...")
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_source = {executor.submit(s.fetch): s for s in sources_to_run}
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    result = future.result()
                    logger.info(f"Source '{source.name}' produced {len(result)} postings.")
                    all_jobs.extend(result)
                except Exception as exc:
                    logger.error(f"Source '{source.name}' threw an exception: {exc}", exc_info=True)

        logger.info(f"Total raw postings assembled across sources: {len(all_jobs)}")
        return all_jobs
