import io
from openpyxl import Workbook
from openpyxl.styles import Font


def build_bookings_report(bookings):
    wb = Workbook()
    ws = wb.active
    ws.title = "Bookings"

    headers = [
        "Reference", "Attendee Name", "Email", "Phone", "Seats",
        "Amount (EUR)", "Payment Method", "Payment Status", "Booked At",
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for b in bookings:
        ws.append([
            b.reference,
            b.attendee_name,
            b.email,
            b.phone or "",
            b.seat_labels(),
            b.amount_total_eur,
            b.payment_method,
            b.payment_status,
            b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "",
        ])

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
