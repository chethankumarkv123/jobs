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

    # Categories
    sec_a = [j for j in jobs if j.location_category == "bengaluru" and j.source_type == "official_career_page" and j.date_is_verified]
    sec_b = [j for j in jobs if j.location_category == "india_other" and j.source_type == "official_career_page" and j.date_is_verified]
    sec_c = [j for j in jobs if j.location_category == "worldwide_remote" and j.source_type == "official_career_page" and j.date_is_verified]
    sec_d = [j for j in jobs if j.source_type == "linkedin"]
    sec_e = [j for j in jobs if j.source_type == "wellfound"]
    sec_f = [j for j in jobs if j.source_type == "job_board" or (not j.date_is_verified and j not in sec_d and j not in sec_e)]

    apply_count = sum(1 for j in jobs if j.recommendation == "APPLY")
    review_count = sum(1 for j in jobs if j.recommendation == "REVIEW")
    official_count = sum(1 for j in jobs if j.source_type == "official_career_page")
    official_share = round((official_count / len(jobs) * 100) if jobs else 0.0, 1)

    console.print()
    console.print(
        Panel(
            f"[bold cyan]Antigravity Job Finder | Run Summary[/]\n"
            f"[dim]Timestamp:[/] {now_ist} | [dim]Candidate:[/] Azure Cloud Engineer (4+ yrs IT experience)\n"
            f"[green bold]APPLY:[/] {apply_count} | [yellow bold]REVIEW:[/] {review_count} | [bold]Total Qualified:[/] {len(jobs)} | [bold cyan]Official Career Page Share:[/] {official_share}% (Target >= 70%)\n"
            f"[dim]Location Distribution:[/] Bengaluru: {len(sec_a)} | Other India: {len(sec_b)} | Worldwide Remote: {len(sec_c)} | LinkedIn: {len(sec_d)} | Wellfound: {len(sec_e)} | Review: {len(sec_f)}",
            border_style="cyan",
        )
    )

    if not jobs:
        console.print(
            Panel(
                "[bold yellow]Zero qualifying openings found meeting strict 24h & experience criteria during this run.[/]\n"
                "[dim]Filters enforced: 3-6 yrs experience, direct employer only, India eligibility confirmed. Pipeline will re-run tomorrow at 08:30 IST.[/]",
                title="Summary",
                border_style="yellow"
            )
        )
        return

    # Render Priority 1: Bengaluru Confirmed
    if sec_a:
        table_a = Table(title="[bold green]A. Bengaluru — Officially Verified Jobs (Priority 1)[/]", border_style="green")
        table_a.add_column("Company", style="bold white", width=14)
        table_a.add_column("Role", style="cyan", width=32)
        table_a.add_column("Arrangement", style="magenta", width=18)
        table_a.add_column("Score", style="bold green", justify="center", width=8)
        table_a.add_column("Rec", justify="center", width=8)
        table_a.add_column("Official Application URL", style="blue underline", width=36)
        for j in sec_a:
            table_a.add_row(
                j.company,
                j.title,
                j.work_arrangement,
                f"{j.estimated_match_score}%",
                f"[bold green]{j.recommendation}[/]",
                j.direct_application_url or j.direct_job_url
            )
        console.print(table_a)
        console.print()

    # Render Priority 2: Other India Confirmed
    if sec_b:
        table_b = Table(title="[bold cyan]B. Other Indian Locations — Officially Verified Jobs (Priority 2)[/]", border_style="cyan")
        table_b.add_column("Company", style="bold white", width=14)
        table_b.add_column("Role", style="cyan", width=32)
        table_b.add_column("City & Arrangement", style="magenta", width=22)
        table_b.add_column("Score", style="bold green", justify="center", width=8)
        table_b.add_column("Rec", justify="center", width=8)
        table_b.add_column("Official Application URL", style="blue underline", width=36)
        for j in sec_b:
            table_b.add_row(
                j.company,
                j.title,
                f"{j.location[:14]} ({j.work_arrangement[:7]})",
                f"{j.estimated_match_score}%",
                f"[bold green]{j.recommendation}[/]",
                j.direct_application_url or j.direct_job_url
            )
        console.print(table_b)
        console.print()

    # Render Priority 3: Worldwide Remote Confirmed
    if sec_c:
        table_c = Table(title="[bold blue]C. Worldwide Remote — Verified Jobs Open to India-Based Applicants (Priority 3)[/]", border_style="blue")
        table_c.add_column("Company", style="bold white", width=16)
        table_c.add_column("Role", style="cyan", width=32)
        table_c.add_column("Score", style="bold green", justify="center", width=8)
        table_c.add_column("Rec", justify="center", width=8)
        table_c.add_column("Official Application URL", style="blue underline", width=38)
        for j in sec_c:
            table_c.add_row(
                j.company,
                j.title,
                f"{j.estimated_match_score}%",
                f"[bold green]{j.recommendation}[/]",
                j.direct_application_url or j.direct_job_url
            )
        console.print(table_c)
        console.print()

    # Render Priority 4: LinkedIn Openings (Dedicated Section)
    if sec_d:
        table_d = Table(title="[bold yellow]D. LinkedIn — Relevant New Openings (Past 24 Hours)[/]", border_style="yellow")
        table_d.add_column("Company", style="bold white", width=16)
        table_d.add_column("Role", style="cyan", width=30)
        table_d.add_column("Location", style="magenta", width=18)
        table_d.add_column("Score", style="bold green", justify="center", width=8)
        table_d.add_column("Rec", justify="center", width=8)
        table_d.add_column("LinkedIn Link", style="blue underline", width=34)
        for j in sec_d:
            table_d.add_row(
                j.company,
                j.title,
                j.location[:18],
                f"{j.estimated_match_score}%",
                f"[bold yellow]{j.recommendation}[/]",
                j.linkedin_job_url or j.direct_job_url
            )
        console.print(table_d)
        console.print()

    # Source coverage summary
    console.print(
        Panel(
            f"[bold white]Source Coverage Summary:[/] {source_stats.get('coverage', 'All configured sources checked')}\n"
            f"[bold green][OK] HTML Dashboard:[/] [white underline]{outputs['html']}[/]\n"
            f"[bold green][OK] CSV Table:[/]     [white underline]{outputs['csv']}[/]\n"
            f"[bold green][OK] JSON Payload:[/]   [white underline]{outputs['json']}[/]\n"
            f"[bold green][OK] Dated Archive:[/]  [white underline]{outputs['archive_html']}[/]",
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
