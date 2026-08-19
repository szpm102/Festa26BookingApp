from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, jsonify,
    send_file, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from extensions import db, csrf
from models import Seat, Booking, Admin, SeatStatus, PaymentMethod, PaymentStatus
from seats import disable_seats, enable_seats, confirm_seats_for_booking, cancel_booking, sweep_expired_holds
from utils import generate_reference
from reports import build_bookings_report
import emailer

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(email=email).first()
        if admin and check_password_hash(admin.password_hash, password):
            login_user(admin)
            return redirect(url_for("admin.dashboard"))
        flash("Invalid email or password.", "error")

    return render_template("admin/login.html", cfg=current_app.config)


@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@login_required
def dashboard():
    sweep_expired_holds()
    counts = {
        "total": Seat.query.count(),
        "available": Seat.query.filter_by(status=SeatStatus.AVAILABLE).count(),
        "held": Seat.query.filter_by(status=SeatStatus.HELD).count(),
        "booked": Seat.query.filter_by(status=SeatStatus.BOOKED).count(),
        "disabled": Seat.query.filter_by(status=SeatStatus.DISABLED).count(),
    }
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    revenue = sum(b.amount_total_eur for b in bookings if b.payment_status == PaymentStatus.PAID)
    return render_template(
        "admin/dashboard.html",
        cfg=current_app.config,
        counts=counts,
        bookings=bookings,
        revenue=revenue,
    )


@admin_bp.route("/api/seats")
@login_required
def admin_seats():
    sweep_expired_holds()
    seats = Seat.query.order_by(Seat.row_label, Seat.seat_number).all()
    out = []
    for s in seats:
        entry = {
            "id": s.id, "label": s.label, "section": s.section,
            "row": s.row_label, "number": s.seat_number, "status": s.status,
        }
        if s.status == SeatStatus.BOOKED and s.booking:
            entry["booking_id"] = s.booking.id
            entry["attendee_name"] = s.booking.attendee_name
            entry["email"] = s.booking.email
            entry["reference"] = s.booking.reference
            entry["payment_method"] = s.booking.payment_method
        out.append(entry)
    return jsonify({"seats": out})


@admin_bp.route("/api/seats/disable", methods=["POST"])
@login_required
def api_disable():
    seat_ids = request.get_json(force=True).get("seat_ids", [])
    n = disable_seats(seat_ids)
    return jsonify({"ok": True, "count": n})


@admin_bp.route("/api/seats/enable", methods=["POST"])
@login_required
def api_enable():
    seat_ids = request.get_json(force=True).get("seat_ids", [])
    n = enable_seats(seat_ids)
    return jsonify({"ok": True, "count": n})


@admin_bp.route("/api/bookings/cash", methods=["POST"])
@login_required
def api_book_cash():
    data = request.get_json(force=True)
    seat_ids = data.get("seat_ids", [])
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not seat_ids:
        return jsonify({"ok": False, "error": "No seats selected."}), 400
    if not name or not email:
        return jsonify({"ok": False, "error": "Name and email are required."}), 400

    seats = Seat.query.filter(Seat.id.in_(seat_ids)).all()
    valid_statuses = {SeatStatus.AVAILABLE, SeatStatus.HELD}
    if any(s.status not in valid_statuses for s in seats) or len(seats) != len(seat_ids):
        return jsonify({"ok": False, "error": "One or more selected seats are no longer available."}), 409

    amount = round(sum(s.price_eur for s in seats), 2)
    booking = Booking(
        reference=generate_reference(),
        attendee_name=name,
        email=email,
        phone=phone,
        amount_total_eur=amount,
        payment_method=PaymentMethod.CASH,
        payment_status=PaymentStatus.PAID,
        created_by_admin=True,
        notes=data.get("notes") or None,
    )
    db.session.add(booking)
    db.session.commit()

    confirm_seats_for_booking(seat_ids, booking.id, from_statuses=[SeatStatus.AVAILABLE, SeatStatus.HELD])
    db.session.refresh(booking)
    emailer.send_booking_confirmation(booking)

    return jsonify({"ok": True, "reference": booking.reference})


@admin_bp.route("/api/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def api_cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    cancel_booking(booking)
    booking.payment_status = PaymentStatus.CANCELLED
    db.session.commit()
    return jsonify({"ok": True})


@admin_bp.route("/report.xlsx")
@login_required
def report():
    bookings = Booking.query.order_by(Booking.created_at.asc()).all()
    buf = build_bookings_report(bookings)
    return send_file(
        buf,
        as_attachment=True,
        download_name="fireworks-bookings-report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
