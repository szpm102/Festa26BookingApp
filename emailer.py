import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app, render_template


def _send(to_addrs, subject, html_body):
    cfg = current_app.config
    if not cfg.get("SMTP_USER") or not cfg.get("SMTP_PASSWORD"):
        current_app.logger.warning(
            "SMTP not configured (SMTP_USER/SMTP_PASSWORD missing) - email not sent: %s",
            subject,
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{cfg['MAIL_FROM_NAME']} <{cfg['SMTP_USER']}>"
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"]) as server:
            server.starttls()
            server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            server.sendmail(cfg["SMTP_USER"], to_addrs, msg.as_string())
        return True
    except Exception:
        current_app.logger.exception("Failed to send email: %s", subject)
        return False


def send_booking_confirmation(booking):
    cfg = current_app.config
    subject = f"Booking Confirmed - {cfg['EVENT_NAME']} ({booking.reference})"

    html = render_template(
        "emails/client_confirmation.html",
        booking=booking,
        cfg=cfg,
    )
    _send([booking.email], subject, html)

    if cfg.get("TEAM_NOTIFY_EMAILS"):
        team_html = render_template(
            "emails/team_notification.html",
            booking=booking,
            cfg=cfg,
        )
        _send(
            cfg["TEAM_NOTIFY_EMAILS"],
            f"New seat booking - {booking.reference} ({booking.seat_labels()})",
            team_html,
        )
