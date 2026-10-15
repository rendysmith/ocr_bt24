"""Email notification utilities.

Supports both SMTP (cross-platform) and win32com/Outlook (Windows-only).
"""

import os
import smtplib
import configparser
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import pandas as pd
from pretty_html_table import build_table


def _get_email_password() -> str:
    """Read email password from config.ini or env var."""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")
    if os.path.exists(config_path):
        config.read(config_path)
        try:
            return config.get("email", "password")
        except (configparser.NoSectionError, configparser.NoOptionError):
            pass
    return os.environ.get("email_password", "")


def send_smtp(to_list: list[str], subject: str, text: str) -> None:
    """Send a plain-text email via SMTP (Office365 / mail.ubpo.ru).

    Args:
        to_list: List of recipient email addresses.
        subject: Email subject line.
        text: Plain-text email body.
    """
    server_addr = "mail.ubpo.ru"
    port = 587
    from_addr = "HRrobot@BDOBPO.RU"
    password = _get_email_password()

    message = (
        f"From: {from_addr}\r\n"
        f"To: {', '.join(to_list)}\r\n"
        f"Subject: {subject}\r\n\r\n{text}"
    )

    server = smtplib.SMTP(server_addr, port)
    server.ehlo()
    server.command_encoding = "utf-8"
    server.starttls()
    server.login(from_addr, password)
    server.sendmail(from_addr, to_list, message.encode("utf8"))
    server.quit()
    print("Send!")


def send_smtp_df(to: str, subject: str, df: pd.DataFrame) -> None:
    """Send an email with a DataFrame rendered as an HTML table.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        df: Pandas DataFrame to render in the email body.
    """
    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = "HRrobot@BDOBPO.RU"
    message["To"] = to
    password = _get_email_password()

    body_content = build_table(df, "blue_light", font_size="14px", text_align="center")
    message.attach(MIMEText(body_content, "html"))

    server = smtplib.SMTP("smtp.office365.com", 587)
    server.starttls()
    server.login(message["From"], password)
    server.sendmail(message["From"], [message["To"]], message.as_string())
    server.quit()


def send_smtp_html(to: str, subject: str, html_content: str) -> None:
    """Send an HTML email via SMTP.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_content: HTML string for the email body.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "HRrobot@BDOBPO.RU"
    msg["To"] = to
    password = _get_email_password()

    msg.add_header("Content-Type", "text/html")
    msg.set_payload(html_content)

    server = smtplib.SMTP("smtp.office365.com", 587)
    server.ehlo()
    server.command_encoding = "utf-8"
    server.starttls()
    server.login(msg["From"], password)
    server.sendmail(msg["From"], [msg["To"]], msg.as_string().encode("utf8"))
    server.quit()


def send_mail_win32(mail_to: str, subject: str, text: str) -> None:
    """Send an email via Outlook (Windows-only, requires pywin32).

    Args:
        mail_to: Recipient email address.
        subject: Email subject line.
        text: HTML content for the email body.
    """
    import win32com.client  # noqa: PLC0415 — Windows-only

    outlook = win32com.Dispatch("outlook.application")
    mail = outlook.CreateItem(0)
    mail.To = mail_to
    mail.Subject = subject
    mail.HTMLBody = text
    mail.Send()
