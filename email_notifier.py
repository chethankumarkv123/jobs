"""
email_notifier.py
Sends the daily job report (HTML file + summary) to chethankumarkv123@gmail.com via SMTP.
Supports Gmail App Passwords and standard SMTP configurations.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def send_daily_job_report(
    recipient: str = "chethankumarkv123@gmail.com",
    html_report_path: str = "reports/latest.html",
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
) -> bool:
    """
    Sends the generated HTML report to the specified email address.
    Credentials can be passed explicitly or read from environment variables:
    - GMAIL_APP_PASSWORD or SMTP_PASSWORD or EMAIL_PASSWORD
    - GMAIL_USER or SMTP_USER or EMAIL_USER
    """
    # 1. Resolve credentials
    user = (
        smtp_user
        or os.environ.get("GMAIL_USER")
        or os.environ.get("SMTP_USER")
        or os.environ.get("EMAIL_USER")
        or "chethankumarkv123@gmail.com"
    )
    password = (
        smtp_password
        or os.environ.get("GMAIL_APP_PASSWORD")
        or os.environ.get("SMTP_PASSWORD")
        or os.environ.get("EMAIL_PASSWORD")
    )

    now_ist = datetime.now(IST_OFFSET).strftime("%d %b %Y, %I:%M %p IST")
    date_str = datetime.now(IST_OFFSET).strftime("%Y-%m-%d")
    subject = f"[Bangalore Startup Jobs] Daily Report & Verified Openings - {date_str}"

    if not password:
        logger.warning(
            "Email notification skipped: No SMTP password / GMAIL_APP_PASSWORD found in environment.\n"
            "To enable email dispatch:\n"
            "1. Generate a Gmail App Password at: https://myaccount.google.com/apppasswords\n"
            "2. Set the environment variable GMAIL_APP_PASSWORD on your PC or in GitHub Repository Secrets."
        )
        return False

    if not os.path.exists(html_report_path):
        logger.error(f"Cannot send email: HTML report not found at '{html_report_path}'")
        return False

    try:
        # 2. Read HTML content
        with open(html_report_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # 3. Construct Email
        msg = MIMEMultipart("mixed")
        msg["From"] = f"Bangalore Startup Job Finder <{user}>"
        msg["To"] = recipient
        msg["Subject"] = subject

        # Quick email body preview
        body_text = f"""Hello Chethan,

Your daily Bangalore Startup Job Intelligence run completed at {now_ist}.
The interactive report is attached to this email and can be opened directly on your phone.

Target Profile: Azure Cloud Engineer (4+ yrs IT experience, Azure/Kubernetes/Linux/Terraform)
Report Attached: latest.html

Best regards,
Bangalore Startup Job Finder
"""
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        # HTML alternative body for modern email clients
        part_html = MIMEText(
            f"""
            <div style="font-family: Arial, sans-serif; padding: 16px; color: #1e293b;">
                <h2 style="color: #0284c7;">Bangalore Startup Job Finder &bull; Daily Report</h2>
                <p>Hello Chethan,</p>
                <p>Your daily job intelligence search for <strong>Azure Cloud Engineer</strong> completed at <strong>{now_ist}</strong>.</p>
                <div style="background: #f8fafc; border-left: 4px solid #0284c7; padding: 12px; margin: 16px 0;">
                    <p style="margin: 0;"><strong>Attached file:</strong> <code>latest.html</code></p>
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: #64748b;">Open the attached HTML file in your phone browser to filter and tap-to-apply for verified roles.</p>
                </div>
            </div>
            """,
            "html",
            "utf-8"
        )
        msg.attach(part_html)

        # 4. Attach the HTML report file
        attachment = MIMEBase("application", "octet-stream")
        attachment.set_payload(html_content.encode("utf-8"))
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            f'attachment; filename="Bangalore_Startup_Jobs_{date_str}.html"'
        )
        msg.attach(attachment)

        # 5. Connect and send via SMTP
        logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        server.sendmail(user, [recipient], msg.as_string())
        server.quit()

        logger.info(f"SUCCESS: Daily job report sent successfully to {recipient}!")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {recipient}: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    send_daily_job_report()
