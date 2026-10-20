"""
application_tracker.py
Mandatory Anti-Duplicate and Application History Tracking System.
Maintains data/application_history.json to ensure one canonical record per opening,
detect duplicates across multiple job boards, and strictly prevent repeated applications.
"""

import os
import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def clean_tracking_params(url: str) -> str:
    """Removes marketing, analytics, and session query parameters from job URLs."""
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        # Strip tracking keys
        strip_prefixes = ("utm_", "ref", "trk", "tracking", "source", "pos", "mid", "campaign")
        strip_exact = {"currentjobid", "refid", "trackingid", "job_source", "fbclid", "gclid"}

        clean_params = {
            k: v for k, v in params.items()
            if not any(k.lower().startswith(p) for p in strip_prefixes)
            and k.lower() not in strip_exact
        }
        clean_query = urlencode(clean_params, doseq=True)
        cleaned = urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), parsed.params, clean_query, ""))
        return cleaned or url.split("?")[0].rstrip("/")
    except Exception:
        return url.split("?")[0].rstrip("/")


def normalize_tokens(text: str) -> List[str]:
    """Extracts alphanumeric tokens, filtering common filler words."""
    cleaned = re.sub(r'[\(\)\[\]\{\}\-\–\—\_\/\,\:\.]', ' ', text.lower())
    stop_words = {"inc", "ltd", "corp", "corporation", "technologies", "technology", "solutions", "services", "the", "a", "an", "and", "or", "for", "at", "in"}
    return [w for w in cleaned.split() if w and w not in stop_words]


def generate_canonical_key(company: str, title: str, location: str = "", req_id: Optional[str] = None) -> str:
    """
    Generates a deterministic canonical job key.
    - If official requisition ID exists: company::req_id
    - Otherwise: company::sorted_significant_title_tokens::location_bucket
    Example:
    'Company X' + 'Azure Cloud Engineer' + 'Bengaluru'
    and
    'Company X' + 'Cloud Engineer, Azure' + 'Bengaluru'
    both resolve to: 'companyx::azure,cloud,engineer::blr'
    """
    comp_tokens = normalize_tokens(company)
    comp_str = "".join(comp_tokens)

    if req_id and req_id.strip():
        req_clean = re.sub(r'[^a-zA-Z0-9]', '', req_id.lower())
        if len(req_clean) >= 3:
            return f"{comp_str}::req_{req_clean}"

    title_tokens = sorted(set(normalize_tokens(title)))
    # Exclude seniority words when forming the core discipline signature
    discipline_tokens = [t for t in title_tokens if t not in ("senior", "sr", "lead", "staff", "principal", "junior", "mid", "associate")]
    title_str = ",".join(discipline_tokens or title_tokens)

    loc_str = "blr" if any(b in location.lower() for b in ["bangalore", "bengaluru", "blr"]) else "india_other"
    return f"{comp_str}::{title_str}::{loc_str}"


class ApplicationTracker:
    ALLOWED_STATUSES = {
        "NEW",
        "PREVIOUSLY_REVIEWED",
        "APPLIED",
        "REJECTED",
        "CLOSED",
        "WITHDRAWN"
    }

    def __init__(self, filepath: str = "data/application_history.json"):
        self.filepath = filepath
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading {self.filepath}: {e}")
        return {
            "version": "1.0.0",
            "last_updated": None,
            "total_records": 0,
            "applied_count": 0,
            "records": {}
        }

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            records = self.data.setdefault("records", {})
            self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
            self.data["total_records"] = len(records)
            self.data["applied_count"] = sum(1 for r in records.values() if r.get("status") == "APPLIED")
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved application history ({self.data['total_records']} tracked records, {self.data['applied_count']} applied).")
        except Exception as e:
            logger.error(f"Failed to save application history: {e}")

    def find_existing_record(
        self,
        canonical_key: str,
        clean_url: str,
        req_id: Optional[str] = None,
        linkedin_id: Optional[str] = None,
        wellfound_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Searches for duplicate records across canonical key, clean URLs, and requisition/platform IDs."""
        records = self.data.setdefault("records", {})

        # Direct canonical key match
        if canonical_key in records:
            return records[canonical_key]

        # Scan for matching requisition ID or URLs
        for rec in records.values():
            if req_id and rec.get("official_requisition_id") and rec.get("official_requisition_id").lower() == req_id.lower():
                return rec
            if linkedin_id and rec.get("LinkedIn_job_id") == linkedin_id:
                return rec
            if wellfound_id and rec.get("Wellfound_job_id") == wellfound_id:
                return rec
            if clean_url and clean_url == rec.get("canonical_application_url"):
                return rec
            if clean_url and clean_url in rec.get("all_source_urls", []):
                return rec

        return None

    def get_record(self, canonical_key: str) -> Optional[Dict[str, Any]]:
        """Returns tracked record by canonical key if present."""
        return self.data.get("records", {}).get(canonical_key)

    def get_days_since_first_discovered(self, canonical_key: str) -> float:
        """Returns elapsed days since the opening was first recorded."""
        rec = self.get_record(canonical_key)
        if not rec:
            return 0.0
        date_str = rec.get("first_discovered_at") or rec.get("first_discovered_date")
        if not date_str:
            return 0.0
        try:
            first_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            return max(0.0, (now_dt - first_dt).total_seconds() / 86400.0)
        except Exception:
            return 0.0

    def evaluate_and_track(
        self,
        job_data: Dict[str, Any]
    ) -> Tuple[str, str, str, bool]:
        """
        Reconciles incoming vacancy with persistent application history.
        Returns: (canonical_key, status, duplicate_check_result, is_new_opening)
        Status values: 'NEW', 'PREVIOUSLY_REVIEWED', 'APPLIED', 'CLOSED', etc.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        company = job_data.get("company", "Company")
        title = job_data.get("title", "Role")
        location = job_data.get("location", "Location")
        req_id = job_data.get("official_requisition_id")
        app_url = clean_tracking_params(job_data.get("direct_application_url") or job_data.get("direct_job_url") or "")
        source_url = clean_tracking_params(job_data.get("source_url") or app_url)
        linkedin_id = job_data.get("LinkedIn_job_id")
        wellfound_id = job_data.get("Wellfound_job_id")
        source_type = job_data.get("source_type", "job_board")

        canonical_key = generate_canonical_key(company, title, location, req_id)
        existing = self.find_existing_record(canonical_key, app_url, req_id, linkedin_id, wellfound_id)

        records = self.data.setdefault("records", {})

        if existing:
            # Duplicate / Previously Discovered Vacancy
            prev_status = existing.get("status", "PREVIOUSLY_REVIEWED")
            existing["last_verified_at"] = now_iso

            # Merge discovered URLs
            all_urls = set(existing.get("all_source_urls", []))
            if app_url:
                all_urls.add(app_url)
            if source_url:
                all_urls.add(source_url)
            existing["all_source_urls"] = sorted(list(all_urls))

            # If official career page URL is now available, upgrade canonical URL
            if source_type == "official_career_page" and app_url:
                existing["canonical_application_url"] = app_url

            # Status logic
            if prev_status == "APPLIED":
                dup_result = f"Already applied on {existing.get('application_date', 'earlier run')}. DO NOT REAPPLY."
                return canonical_key, "APPLIED", dup_result, False
            else:
                dup_result = f"Previously discovered on {existing.get('first_discovered_at', '')[:10]} (Duplicate cross-source merged)."
                existing["status"] = "PREVIOUSLY_REVIEWED"
                return canonical_key, "PREVIOUSLY_REVIEWED", dup_result, False

        else:
            # Genuinely NEW Opening
            new_record = {
                "canonical_job_key": canonical_key,
                "company": company,
                "job_title": title,
                "location": location,
                "work_arrangement": job_data.get("work_arrangement", "Onsite/Remote"),
                "official_requisition_id": req_id,
                "LinkedIn_job_id": linkedin_id,
                "Wellfound_job_id": wellfound_id,
                "other_source_job_ids": [],
                "canonical_application_url": app_url,
                "all_source_urls": [u for u in [app_url, source_url] if u],
                "first_discovered_at": now_iso,
                "original_posting_date": job_data.get("original_posting_date"),
                "last_verified_at": now_iso,
                "status": "NEW",
                "application_date": None,
                "notes": f"Discovered via {job_data.get('source_name', 'System')} on {now_iso[:10]}"
            }
            records[canonical_key] = new_record
            dup_result = "Unique opening (Never seen before)"
            return canonical_key, "NEW", dup_result, True

    def mark_applied(self, canonical_key: str, notes: str = "") -> bool:
        """Mark a job as APPLIED upon explicit user confirmation."""
        records = self.data.setdefault("records", {})
        if canonical_key in records:
            now_str = datetime.now(IST_OFFSET).strftime("%Y-%m-%d %H:%M IST")
            records[canonical_key]["status"] = "APPLIED"
            records[canonical_key]["application_date"] = now_str
            records[canonical_key]["notes"] = (records[canonical_key].get("notes", "") + f" | Marked applied on {now_str}. {notes}").strip()
            self.save()
            logger.info(f"Marked {canonical_key} as APPLIED.")
            return True
        return False
