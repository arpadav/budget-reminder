import os
import smtplib
from typing import List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailClient:
    def __init__(self, from_email: str, app_password: Optional[str] = None):
        self.from_email = from_email
        self.app_password = app_password or os.environ.get("GMAIL_APP_PASSWORD")
        if not self.app_password:
            raise ValueError(
                "App password must be provided or set in GMAIL_APP_PASSWORD"
            )

    def send_email(
        self,
        subject: str,
        body_html: str,
        to: List[str],
        cc: List[str] = [],
        bcc: List[str] = [],
    ):
        cc = cc or []
        bcc = bcc or []

        msg = MIMEMultipart()
        msg["From"] = self.from_email
        msg["To"] = ", ".join(to)
        msg["Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        recipients = to + cc + bcc

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(self.from_email, self.app_password)  # type: ignore
            server.sendmail(self.from_email, recipients, msg.as_string())
