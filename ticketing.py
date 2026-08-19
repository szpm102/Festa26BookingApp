"""QR check-in codes and downloadable PDF tickets - one of each per seat, not
per booking, so a group can be checked in seat-by-seat. No Apple/Google
developer accounts are needed for any of this - it's a plain QR code
(containing a link to the admin check-in page for that seat) plus a PDF
ticket. Real wallet passes are handled separately in wallet.py.
"""

import io
import secrets

import qrcode
from PIL import Image
from fpdf import FPDF


def generate_checkin_token():
    return secrets.token_urlsafe(24)


def build_qr_png(data):
    img = qrcode.make(data, border=2)
    # qrcode produces a 1-bit image; fpdf2 mis-decodes that bit depth (renders
    # as garbled diagonal noise), so convert to a plain 8-bit RGB PNG first.
    raw = io.BytesIO()
    img.save(raw, format="PNG")
    raw.seek(0)
    rgb = Image.open(raw).convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def build_ticket_pdf(booking, cfg, seat_qr_pairs):
    """One page per seat, each with its own QR code, so a group booking
    multiple seats gets one PDF where every seat can be checked in
    independently. seat_qr_pairs is a list of (seat, qr_png_bytes)."""
    pdf = FPDF(unit="mm", format=(120, 180))
    pdf.set_auto_page_break(False)

    for seat, qr_png_bytes in seat_qr_pairs:
        pdf.add_page()

        pdf.set_fill_color(11, 6, 5)
        pdf.rect(0, 0, 120, 180, style="F")

        pdf.set_text_color(216, 31, 38)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_xy(6, 8)
        pdf.cell(108, 8, "LIGHT UP THE SKY", align="C")

        pdf.set_text_color(230, 230, 230)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(6, 17)
        pdf.multi_cell(108, 5, cfg["EVENT_SUBTITLE"], align="C")

        pdf.set_font("Helvetica", "", 8)
        pdf.set_xy(6, 30)
        pdf.multi_cell(
            108, 4.5,
            f"{cfg['EVENT_LOCATION']}\n{cfg['EVENT_DATE_TEXT']} - {cfg['EVENT_TIME_TEXT']}",
            align="C",
        )

        qr_path = io.BytesIO(qr_png_bytes)
        pdf.image(qr_path, x=30, y=44, w=60, h=60)

        pdf.set_text_color(230, 230, 230)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_xy(6, 108)
        pdf.cell(108, 6, f"Ref: {booking.reference}", align="C")

        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(6, 116)
        pdf.cell(108, 5, booking.attendee_name, align="C")

        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(255, 59, 59)
        pdf.set_xy(6, 126)
        pdf.cell(108, 12, f"Seat {seat.label}", align="C")

        if len(seat_qr_pairs) > 1:
            other_labels = ", ".join(s.label for s, _ in seat_qr_pairs if s.id != seat.id)
            pdf.set_font("Helvetica", "", 7.5)
            pdf.set_text_color(150, 150, 150)
            pdf.set_xy(6, 140)
            pdf.multi_cell(108, 4, f"Part of a {len(seat_qr_pairs)}-seat booking, also with: {other_labels}", align="C")

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.set_xy(6, 152)
        pdf.multi_cell(
            108, 4.5,
            f"Paid: EUR {booking.amount_total_eur:.2f} total ({booking.payment_method})\n"
            "Present this QR code at the entrance to be checked in.\n"
            f"{cfg['REFUND_POLICY_TEXT']}",
            align="C",
        )

    out = pdf.output()
    return bytes(out)
