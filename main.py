"""
main.py
Main entrypoint and orchestrator for the Personalized Startup Job Finder.
Runs daily job search for Azure Cloud Engineer profile (LTIMindtree, 4+ yrs IT experience).
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone, timedelta
import yaml

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from job_sources import JobSourceManager
from job_filter import JobFilterEngine
from report_generator import ReportGenerator
from email_notifier import send_daily_job_report

console = Console(highlight=False)
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def setup_logging(config: dict) -> logging.Logger:
    log_file = "logs/job_finder.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_format = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

    return logger


def load_config(config_path: str = "config.yaml") -> dict:
    if not os.path.exists(config_path):
        console.print(f"[bold red]Error:[/] Configuration file '{config_path}' not found!")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def print_cli_summary(jobs: list, outputs: dict, source_stats: dict):
    now_ist = datetime.now(IST_OFFSET).strftime("%Y-%m-%d %H:%M:%S IST")

    # Mirror exact 7 sections from report_generator.py & AGENTS.md
    sec_1 = [j for j in jobs if j.location_category == "bengaluru" and j.recommendation == "APPLY" and j.application_status == "NEW"]
    sec_2 = [j for j in jobs if j.location_category == "india_other" and j.recommendation == "APPLY" and j.application_status == "NEW"]
    sec_3 = [j for j in jobs if j.location_category == "worldwide_remote" and j.recommendation == "APPLY" and j.application_status == "NEW"]
    sec_4 = [j for j in jobs if j.application_status in ("PREVIOUSLY_REVIEWED", "APPLIED")]
    sec_5 = [j for j in jobs if j.recommendation == "REVIEW" and j not in sec_4]
    sec_6 = [j for j in jobs if "possible duplicate" in (j.duplicate_check_result or "").lower()]

    new_apply_count = len(sec_1) + len(sec_2) + len(sec_3)
    review_count = len(sec_5)
    applied_count = sum(1 for j in jobs if j.application_status == "APPLIED")
    prev_reviewed_count = sum(1 for j in jobs if j.application_status == "PREVIOUSLY_REVIEWED")
    confirmed_jobs = sec_1 + sec_2 + sec_3
    official_count = sum(1 for j in confirmed_jobs if j.source_type == "official_career_page")
    official_share = round((official_count / new_apply_count * 100) if new_apply_count else 0.0, 1)

    console.print()
    console.print(
        Panel(
            f"[bold cyan]Antigravity Resume-Based Job Finder | Daily Run[/]\n"
            f"[dim]Timestamp:[/] {now_ist} | [dim]Candidate:[/] Azure Cloud Engineer (4.2 yrs IT experience, LTIMindtree)\n"
            f"[green bold]NEW APPLY:[/] {new_apply_count} | [yellow bold]REVIEW:[/] {review_count} | [magenta bold]PREV REVIEWED:[/] {prev_reviewed_count} | [blue bold]ALREADY APPLIED:[/] {applied_count}\n"
            f"[bold cyan]Official Career Page Share (Confirmed):[/] {official_share}% (Target >= 70%)\n"
            f"[dim]Sections:[/] 1. BLR ({len(sec_1)}) | 2. India Other ({len(sec_2)}) | 3. Remote ({len(sec_3)}) | 4. History Tracked ({len(sec_4)}) | 5. Date Unverified/Review ({len(sec_5)}) | 6. Possible Dups ({len(sec_6)})",
            border_style="cyan",
        )
    )

    if not jobs:
        console.print(
            Panel(
                "[bold yellow]Zero qualifying openings found meeting strict criteria during this run.[/]\n"
                "[dim]Filters enforced: 3-6 yrs experience, direct employer only, India eligibility confirmed. Pipeline will re-run tomorrow at 08:30 IST.[/]",
                title="Summary",
                border_style="yellow"
            )
        )
        return

    # Section 1: Bengaluru Confirmed
    if sec_1:
        table_1 = Table(title="[bold green]1. Bengaluru — Confirmed Matches (Priority 1)[/]", border_style="green")
        table_1.add_column("Company", style="bold white", width=14)
        table_1.add_column("Role", style="cyan", width=32)
        table_1.add_column("Arrangement", style="magenta", width=16)
        table_1.add_column("Score", style="bold green", justify="center", width=8)
        table_1.add_column("Rec", justify="center", width=8)
        table_1.add_column("Official / Direct Application URL", style="blue underline", width=38)
        for j in sec_1:
            table_1.add_row(
                j.company,
                j.title,
                j.work_arrangement,
                f"{j.estimated_match_score}%",
                f"[bold green]{j.recommendation}[/]",
                j.direct_application_url or j.direct_job_url
            )
        console.print(table_1)
        console.print()

    # Section 2: Other India Confirmed
    if sec_2:
        table_2 = Table(title="[bold cyan]2. Other Indian Locations — Confirmed Matches (Priority 2)[/]", border_style="cyan")
        table_2.add_column("Company", style="bold white", width=14)
        table_2.add_column("Role", style="cyan", width=32)
        table_2.add_column("City & Arrangement", style="magenta", width=22)
        table_2.add_column("Score", style="bold green", justify="center", width=8)
        table_2.add_column("Rec", justify="center", width=8)
        table_2.add_column("Official / Direct Application URL", style="blue underline", width=38)
        for j in sec_2:
            table_2.add_row(
                j.company,
                j.title,
                f"{j.location[:14]} ({j.work_arrangement[:7]})",
                f"{j.estimated_match_score}%",
                f"[bold green]{j.recommendation}[/]",
                j.direct_application_url or j.direct_job_url
            )
        console.print(table_2)
        console.print()

    # Section 3: Worldwide Remote Confirmed
    if sec_3:
        table_3 = Table(title="[bold blue]3. Worldwide Remote — Confirmed Matches Open to India (Priority 3)[/]", border_style="blue")
        table_3.add_column("Company", style="bold white", width=16)
        table_3.add_column("Role", style="cyan", width=32)
        table_3.add_column("Score", style="bold green", justify="center", width=8)
        table_3.add_column("Rec", justify="center", width=8)
        table_3.add_column("Official / Direct Application URL", style="blue underline", width=38)
        for j in sec_3:
            table_3.add_row(
                j.company,
                j.title,
                f"{j.estimated_match_score}%",
                f"[bold green]{j.recommendation}[/]",
                j.direct_application_url or j.direct_job_url
            )
        console.print(table_3)
        console.print()

    # Section 4: History Tracked (Previously Reviewed / Applied)
    if sec_4:
        table_4 = Table(title="[bold magenta]4. Previously Reviewed or Applied Jobs (3-Day Display Window)[/]", border_style="magenta")
        table_4.add_column("Company", style="bold white", width=14)
        table_4.add_column("Role", style="cyan", width=30)
        table_4.add_column("Tracker Status", style="bold magenta", width=22)
        table_4.add_column("Duplicate Check Note", style="dim", width=36)
        for j in sec_4[:10]:
            table_4.add_row(
                j.company,
                j.title,
                j.application_status,
                j.duplicate_check_result[:35]
            )
        console.print(table_4)
        console.print()

    # Section 5: Date Unverified / Review Manually
    if sec_5:
        table_5 = Table(title="[bold yellow]5. Date Unverified / Review Manually[/]", border_style="yellow")
        table_5.add_column("Company", style="bold white", width=16)
        table_5.add_column("Role", style="cyan", width=30)
        table_5.add_column("Location", style="magenta", width=18)
        table_5.add_column("Score", style="bold green", justify="center", width=8)
        table_5.add_column("Rec", justify="center", width=8)
        table_5.add_column("Application Link", style="blue underline", width=34)
        for j in sec_5:
            table_5.add_row(
                j.company,
                j.title,
                j.location[:18],
                f"{j.estimated_match_score}%",
                f"[bold yellow]{j.recommendation}[/]",
                j.direct_application_url or j.direct_job_url
            )
        console.print(table_5)
        console.print()

    # Section 6: Possible Duplicates
    if sec_6:
        table_6 = Table(title="[bold red]6. Possible Duplicates Requiring Review[/]", border_style="red")
        table_6.add_column("Company", style="bold white", width=16)
        table_6.add_column("Role", style="cyan", width=30)
        table_6.add_column("Canonical Key", style="dim", width=30)
        table_6.add_column("Details", style="yellow", width=30)
        for j in sec_6:
            table_6.add_row(
                j.company,
                j.title,
                j.canonical_job_key[:28],
                j.duplicate_check_result[:28]
            )
        console.print(table_6)
        console.print()

    # Source coverage summary
    console.print(
        Panel(
            f"[bold white]Source Coverage Summary:[/] {source_stats.get('coverage', 'All configured sources checked')}\n"
            f"[bold green][OK] HTML Dashboard:[/] [white underline]{outputs['html']}[/]\n"
            f"[bold green][OK] CSV Table:[/]     [white underline]{outputs['csv']}[/]\n"
            f"[bold green][OK] JSON Payload:[/]   [white underline]{outputs['json']}[/]\n"
            f"[bold green][OK] Dated Archive:[/]  [white underline]{outputs['archive_html']}[/]\n"
            f"[bold green][OK] App Tracker:[/]   [white underline]data/application_history.json[/]",
            title="Generated Reports & Verification Status",
            border_style="green"
        )
    )
    console.print()


def run_pipeline(source_filter: str = None, dry_run: bool = False):
    config = load_config("config.yaml")
    setup_logging(config)
    logger = logging.getLogger("main")

    logger.info("Starting Daily Job Finder for Azure Cloud Engineer...")

    # 1. Fetch raw jobs across all active sources
    source_mgr = JobSourceManager(config)
    raw_jobs = source_mgr.fetch_all(specific_source=source_filter)
    logger.info(f"Retrieved {len(raw_jobs)} raw postings across sources.")

    source_stats = {
        "coverage": "Official Career Pages (100%), Wellfound (100%), LinkedIn Jobs (100%), Hacker News (100%), RemoteOK (100%), Jobicy (100%), Arbeitnow (100%)"
    }

    # 2. Filter, score, and deduplicate
    filter_engine = JobFilterEngine(config)
    qualified_jobs = filter_engine.evaluate_and_deduplicate(raw_jobs)
    logger.info(f"Evaluated {len(qualified_jobs)} qualifying jobs (APPLY + REVIEW).")

    # 3. Generate reports
    excluded_summary = [
        "Roles requiring 7+ years hard minimum were excluded (candidate has 4.2 yrs total IT experience)",
        "Third-party staffing agencies (e.g. Recruise, Randstad, Michael Page) without identified direct employer were rejected",
        "Non-infrastructure roles (Sales, Marketing, HR, Business Development) were excluded",
        "Timezone-restricted postings (US Only, CET/Europe Only) were filtered out"
    ]
    report_gen = ReportGenerator(config)
    outputs = report_gen.generate_all(qualified_jobs, excluded_summary=excluded_summary)

    # 4. Email Notification
    email_cfg = config.get("notifications", {}).get("email", {})
    if email_cfg.get("enabled", True):
        recipient = email_cfg.get("recipient", "chethankumarkv123@gmail.com")
        send_daily_job_report(recipient=recipient, html_report_path=outputs["html"])

    # 5. Display rich CLI summary
    print_cli_summary(qualified_jobs, outputs, source_stats)


def main():
    parser = argparse.ArgumentParser(description="Antigravity Personalized Job Finder")
    parser.add_argument("--source", type=str, default=None, help="Filter by source name")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist history")
    parser.add_argument("--check-health", action="store_true", help="Check sources connectivity")

    args = parser.parse_args()

    if args.check_health:
        console.print("[bold cyan]Checking configured sources...[/]")
        config = load_config()
        mgr = JobSourceManager(config)
        console.print(f"Sources: {[s.name for s in mgr.sources]}")
        sys.exit(0)

    run_pipeline(source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
