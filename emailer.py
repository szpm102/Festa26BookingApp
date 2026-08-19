import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.utils import formatdate, make_msgid
from flask import current_app, render_template

from extensions import db
import ticketing
import wallet


def _send(to_addrs, subject, html_body, text_body, inline_images=None, attachments=None):
    cfg = current_app.config
    if not cfg.get("SMTP_USER") or not cfg.get("SMTP_PASSWORD"):
        current_app.logger.warning(
            "SMTP not configured (SMTP_USER/SMTP_PASSWORD missing) - email not sent: %s",
            subject,
        )
        return False

    root = MIMEMultipart("mixed")
    root["Subject"] = subject
    root["From"] = f"{cfg['MAIL_FROM_NAME']} <{cfg['SMTP_USER']}>"
    root["To"] = ", ".join(to_addrs)
    # Missing Date/Message-ID headers, and HTML with no plain-text
    # alternative, are both well-known spam signals - avoid both.
    root["Date"] = formatdate(localtime=True)
    root["Message-ID"] = make_msgid(domain=cfg["SMTP_USER"].rsplit("@", 1)[-1])

    related = MIMEMultipart("related")
    alt = MIMEMultipart("alternative")
    # Least-preferred first: plain text, then HTML.
    alt.attach(MIMEText(text_body, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    related.attach(alt)

    for cid, img_bytes in (inline_images or {}).items():
        img = MIMEImage(img_bytes, _subtype="png")
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=f"{cid}.png")
        related.attach(img)

    root.attach(related)

    for filename, file_bytes, mimetype in (attachments or []):
        part = MIMEApplication(file_bytes, _subtype=mimetype)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        root.attach(part)

    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"]) as server:
            server.starttls()
            server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            server.sendmail(cfg["SMTP_USER"], to_addrs, root.as_string())
        return True
    except Exception:
        current_app.logger.exception("Failed to send email: %s", subject)
        return False


def send_booking_confirmation(booking):
    """Each seat in the booking gets its own QR code, PDF page, and wallet
    pass, so a group can be checked in seat-by-seat rather than all at once."""
    cfg = current_app.config
    subject = f"Booking Confirmed - {cfg['EVENT_NAME']} ({booking.reference})"

    if not booking.access_token:
        booking.access_token = ticketing.generate_checkin_token()
        db.session.commit()

    seat_qr_pairs = []
    inline_images = {}
    tickets = []
    attachments = []

    for seat in sorted(booking.seats, key=lambda s: s.label):
        if not seat.checkin_token:
            seat.checkin_token = ticketing.generate_checkin_token()
            db.session.commit()

        checkin_url = f"{cfg['BASE_URL']}/admin/checkin/{seat.checkin_token}"
        qr_png = ticketing.build_qr_png(checkin_url)
        seat_qr_pairs.append((seat, qr_png))

        cid = f"qr_{seat.id}"
        inline_images[cid] = qr_png

        wallet_result = wallet.create_wallet_pass(seat, booking, cfg, checkin_url)
        if wallet_result:
            seat.wallet_serial = wallet_result.get("serialNumber")
            seat.wallet_google_url = wallet_result.get("googleSaveUrl")
            seat.wallet_apple_pass_b64 = wallet_result.get("applePass")
            db.session.commit()
            attachments.append((
                f"ticket-{booking.reference}-{seat.label}.pkpass",
                wallet.decode_apple_pass(seat.wallet_apple_pass_b64),
                "vnd.apple.pkpass",
            ))

        tickets.append({"seat": seat, "qr_cid": cid})

    ticket_pdf = ticketing.build_ticket_pdf(booking, cfg, seat_qr_pairs)
    attachments.insert(0, (f"ticket-{booking.reference}.pdf", ticket_pdf, "pdf"))

    html = render_template("emails/client_confirmation.html", booking=booking, cfg=cfg, tickets=tickets)
    text = render_template("emails/client_confirmation.txt", booking=booking, cfg=cfg, tickets=tickets)
    _send(
        [booking.email],
        subject,
        html,
        text,
        inline_images=inline_images,
        attachments=attachments,
    )

    if cfg.get("TEAM_NOTIFY_EMAILS"):
        team_html = render_template("emails/team_notification.html", booking=booking, cfg=cfg)
        team_text = render_template("emails/team_notification.txt", booking=booking, cfg=cfg)
        _send(
            cfg["TEAM_NOTIFY_EMAILS"],
            f"New seat booking - {booking.reference} ({booking.seat_labels()})",
            team_html,
            team_text,
        )
