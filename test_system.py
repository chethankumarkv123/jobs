"""
test_system.py
Verification test suite for Anti-Duplicate Application Tracker, Resume-Based Scoring,
and Filtering Rules.
"""

import os
import sys
import unittest
import tempfile
import yaml
from datetime import datetime, timezone

from job_sources import JobPosting
from application_tracker import ApplicationTracker, generate_canonical_key
from job_filter import JobFilterEngine


class TestApplicationTrackerAndFilter(unittest.TestCase):
    def setUp(self):
        # Temporary tracker file
        self.tmp_dir = tempfile.mkdtemp()
        self.tracker_file = os.path.join(self.tmp_dir, "test_app_history.json")
        self.tracker = ApplicationTracker(filepath=self.tracker_file)

        # Config with candidate profile
        with open("config.yaml", "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.filter_engine = JobFilterEngine(self.config)
        self.filter_engine.tracker = self.tracker

    def test_canonical_key_generation(self):
        """Test canonical key generation for title variations and URL parameter stripping."""
        j1 = JobPosting(
            id="1",
            title="Senior Azure Cloud Engineer",
            company="Infosys Cloud Labs",
            location="Bengaluru, Karnataka, India",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="3-5 years",
            source_name="Official Careers",
            direct_job_url="https://careers.infosys.com/job/123?utm_source=linkedin&gh_jid=456",
            description="Azure, Terraform, Linux",
        )
        j2 = JobPosting(
            id="2",
            title="Azure Cloud Engineer",
            company="Infosys Cloud Labs",
            location="Bangalore",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="3-5 years",
            source_name="LinkedIn",
            direct_job_url="https://careers.infosys.com/job/123?ref=feed",
            description="Azure, Terraform, Linux",
        )

        key1 = generate_canonical_key(j1.company, j1.title, j1.location)
        key2 = generate_canonical_key(j2.company, j2.title, j2.location)
        # Same company, same core discipline (cloud azure), same city bucket (blr)
        self.assertEqual(key1, key2)

    def test_distinct_roles_at_same_company_kept_separate(self):
        """Test that different roles at the same company have distinct canonical keys."""
        j1 = JobPosting(
            id="1",
            title="Azure Cloud Engineer",
            company="Acme Corp",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="4 years",
            source_name="Official",
            direct_job_url="https://acme.com/jobs/azure-cloud",
            description="Azure, Terraform",
        )
        j2 = JobPosting(
            id="2",
            title="DevSecOps Engineer",
            company="Acme Corp",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="4 years",
            source_name="Official",
            direct_job_url="https://acme.com/jobs/devsecops",
            description="DevSecOps, Qualys, CIS benchmarks",
        )

        key1 = generate_canonical_key(j1.company, j1.title, j1.location)
        key2 = generate_canonical_key(j2.company, j2.title, j2.location)
        self.assertNotEqual(key1, key2)

    def test_requisition_id_deduplication(self):
        """Test that same requisition ID across different portals matches immediately."""
        j1 = JobPosting(
            id="101",
            title="Azure DevOps Engineer",
            company="TechCorp India",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="3-5 years",
            source_name="Official",
            direct_job_url="https://techcorp.com/careers/req9999",
            description="Terraform, Azure DevOps, AKS",
            official_requisition_id="REQ-9999",
        )
        j2 = JobPosting(
            id="102",
            title="Cloud Platform Engineer (Req 9999)",
            company="TechCorp India",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="3-5 years",
            source_name="LinkedIn",
            direct_job_url="https://linkedin.com/jobs/view/88888",
            description="Terraform, Azure DevOps, AKS",
            official_requisition_id="REQ-9999",
        )

        key1 = generate_canonical_key(j1.company, j1.title, j1.location, req_id=j1.official_requisition_id)
        key2 = generate_canonical_key(j2.company, j2.title, j2.location, req_id=j2.official_requisition_id)
        self.assertEqual(key1, key2)

    def test_already_applied_job_never_recommended_again(self):
        """Test that a job marked APPLIED is suppressed from recommendation."""
        j = JobPosting(
            id="applied_job_1",
            title="Azure Infrastructure Engineer",
            company="Fintech Startup India",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="4 years",
            source_name="Official Careers",
            direct_job_url="https://fintech.io/careers/infra",
            description="Azure, Terraform, Kubernetes, Linux, 4 years experience required",
        )

        key = generate_canonical_key(j.company, j.title, j.location)
        # Pre-seed tracker with APPLIED status
        self.tracker.data["records"][key] = {
            "canonical_job_key": key,
            "company": j.company,
            "job_title": j.title,
            "location": j.location,
            "canonical_application_url": j.direct_job_url,
            "all_source_urls": [j.direct_job_url],
            "first_discovered_date": datetime.now(timezone.utc).isoformat(),
            "last_verified_date": datetime.now(timezone.utc).isoformat(),
            "status": "APPLIED",
            "score": 90.0,
            "recommendation": "SKIP",
            "notes": "Applied on company portal via Workday",
        }
        self.tracker.save()

        # Run filter
        self.filter_engine.evaluate_and_deduplicate([j])

        self.assertEqual(j.application_status, "APPLIED")
        self.assertEqual(j.recommendation, "SKIP")
        self.assertIn("ALREADY APPLIED", j.recommendation_rationale)

    def test_previously_reviewed_job_is_labeled_correctly(self):
        """Test that a previously seen job is marked PREVIOUSLY_REVIEWED."""
        j = JobPosting(
            id="rev_job_1",
            title="Cloud Operations Engineer",
            company="Global SaaS Ltd",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="3-5 years",
            source_name="Official Careers",
            direct_job_url="https://globalsaas.com/jobs/cloud-ops",
            description="Azure, Linux, Monitoring, ServiceNow, 3-5 years experience",
        )

        key = generate_canonical_key(j.company, j.title, j.location)
        # First discovery
        self.tracker.data["records"][key] = {
            "canonical_job_key": key,
            "company": j.company,
            "job_title": j.title,
            "location": j.location,
            "canonical_application_url": j.direct_job_url,
            "all_source_urls": [j.direct_job_url],
            "first_discovered_date": datetime.now(timezone.utc).isoformat(),
            "last_verified_date": datetime.now(timezone.utc).isoformat(),
            "status": "NEW",
            "score": 82.0,
            "recommendation": "APPLY",
            "notes": "First discovered",
        }
        self.tracker.save()

        # Re-evaluate same job on next daily run
        self.filter_engine.evaluate_and_deduplicate([j])
        self.assertEqual(j.application_status, "PREVIOUSLY_REVIEWED")

    def test_previously_reviewed_3_day_cutoff(self):
        """Test that previously reviewed jobs older than 3 days are excluded from the daily report."""
        from datetime import timedelta
        # Job A: Discovered 1 day ago (within 3-day cutoff)
        j_recent = JobPosting(
            id="recent_job",
            title="Cloud Platform Engineer",
            company="Startup A",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="3-5 years",
            source_name="Official Careers",
            direct_job_url="https://startupa.io/jobs/1",
            description="Azure, Terraform, Kubernetes",
        )
        key_a = generate_canonical_key(j_recent.company, j_recent.title, j_recent.location)
        self.tracker.data["records"][key_a] = {
            "canonical_job_key": key_a,
            "company": j_recent.company,
            "job_title": j_recent.title,
            "location": j_recent.location,
            "canonical_application_url": j_recent.direct_job_url,
            "all_source_urls": [j_recent.direct_job_url],
            "first_discovered_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "status": "PREVIOUSLY_REVIEWED",
            "score": 80.0,
        }

        # Job B: Discovered 5 days ago (older than 3-day cutoff)
        j_old = JobPosting(
            id="old_job",
            title="Site Reliability Engineer",
            company="Startup B",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="3-5 years",
            source_name="Official Careers",
            direct_job_url="https://startupb.io/jobs/2",
            description="Azure, Linux, Monitoring",
        )
        key_b = generate_canonical_key(j_old.company, j_old.title, j_old.location)
        self.tracker.data["records"][key_b] = {
            "canonical_job_key": key_b,
            "company": j_old.company,
            "job_title": j_old.title,
            "location": j_old.location,
            "canonical_application_url": j_old.direct_job_url,
            "all_source_urls": [j_old.direct_job_url],
            "first_discovered_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "status": "PREVIOUSLY_REVIEWED",
            "score": 80.0,
        }
        self.tracker.save()

        # Run filter on both
        results = self.filter_engine.evaluate_and_deduplicate([j_recent, j_old])

        # j_recent (1 day old) must be included in the report
        self.assertIn(j_recent, results)
        self.assertEqual(j_recent.recommendation, "REVIEW")

        # j_old (5 days old) must be excluded from today's report
        self.assertNotIn(j_old, results)

    def test_hard_7_plus_years_excluded(self):
        """Test that jobs requiring 7+ years hard minimum are excluded."""
        j = JobPosting(
            id="exp_fail",
            title="Lead Azure Architect",
            company="Enterprise Corp",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="8+ years",
            min_years_exp=8.0,
            source_name="Official",
            direct_job_url="https://enterprise.com/job/lead",
            description="Must have minimum 8+ years of experience in Azure cloud.",
        )
        self.filter_engine.evaluate_and_deduplicate([j])
        self.assertEqual(j.recommendation, "SKIP")
        self.assertIn("Exceeds experience cap", j.recommendation_rationale)

    def test_startup_education_backlog_exemption(self):
        """Test that startup role with degree requirement is never rejected."""
        j = JobPosting(
            id="startup_1",
            title="DevOps Engineer",
            company="Bengaluru AI Labs",
            location="Bengaluru",
            location_category="bengaluru",
            work_arrangement="hybrid",
            original_posting_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            date_is_verified=True,
            experience_requirement="3-5 years",
            min_years_exp=3.0,
            source_name="Wellfound",
            source_type="wellfound",
            direct_job_url="https://wellfound.com/jobs/ai-devops",
            description="Requires B.Tech/B.E degree with no active backlogs. 3-5 years experience with Azure, Terraform, Docker, Kubernetes.",
        )
        self.filter_engine.evaluate_and_deduplicate([j])
        self.assertIn(j.recommendation, ["APPLY", "REVIEW"])
        self.assertNotEqual(j.recommendation, "SKIP")
        self.assertTrue(j.estimated_match_score >= 50)


if __name__ == "__main__":
    unittest.main()
