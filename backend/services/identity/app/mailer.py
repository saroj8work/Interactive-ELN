import os
import smtplib
from email.message import EmailMessage

from eln_common.errors import ServiceUnavailableError


class InvitationMailer:
    def send(self, recipient: str, organization_name: str, invite_url: str) -> None:
        message = EmailMessage()
        message["Subject"] = f"Invitation to {organization_name} on Interactive ELN"
        message["To"] = recipient
        message.set_content(
            f"You have been invited to {organization_name} on Interactive ELN.\n\n"
            f"Accept your invitation using this single-use link:\n{invite_url}\n\n"
            "This invitation expires in 7 days. If you were not expecting it, "
            "you can ignore this message."
        )
        self._send(message)

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Reset your Interactive ELN password"
        message["To"] = recipient
        message.set_content(
            "A password reset was requested for your Interactive ELN account.\n\n"
            f"Use this single-use link within one hour:\n{reset_url}\n\n"
            "If you did not request this, you can ignore this message."
        )
        self._send(message)

    @staticmethod
    def _send(message: EmailMessage) -> None:
        host = os.getenv("SMTP_HOST")
        sender = os.getenv("SMTP_FROM")
        if not host or not sender:
            raise ServiceUnavailableError(
                "Email delivery is not configured; the email was not sent."
            )
        message["From"] = sender
        try:
            port = int(os.getenv("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
                    smtp.starttls()
                username = os.getenv("SMTP_USERNAME")
                password = os.getenv("SMTP_PASSWORD")
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException, ValueError) as error:
            raise ServiceUnavailableError(
                "The email could not be delivered."
            ) from error
