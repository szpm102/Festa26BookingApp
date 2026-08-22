from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, jsonify,
    send_file, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, csrf, limiter
from models import Seat, Booking, Admin, SeatStatus, PaymentMethod, PaymentStatus
from seats import disable_seats, enable_seats, confirm_seats_for_booking, cancel_booking, sweep_expired_holds
from utils import generate_reference, is_valid_email
from reports import build_bookings_report, build_analytics_report
from analytics import Event, log_event, funnel_summary, daily_breakdown
import emailer
import ticketing
import wallet

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def superadmin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_superadmin:
            flash("Only a superadmin can do that.", "error")
            return redirect(url_for("admin.dashboard"))
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
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


@admin_bp.route("/scan")
@login_required
def scan():
    return render_template("admin/scan.html", cfg=current_app.config)


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
    seats = Seat.query.order_by(Seat.section, Seat.row_label, Seat.seat_number).all()
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
    if not is_valid_email(email):
        return jsonify({"ok": False, "error": "That email address doesn't look valid - the ticket can't be delivered without a correct one."}), 400

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
        access_token=ticketing.generate_checkin_token(),
    )
    db.session.add(booking)
    db.session.commit()

    confirmed = confirm_seats_for_booking(seat_ids, booking.id, from_statuses=[SeatStatus.AVAILABLE, SeatStatus.HELD])
    if confirmed < len(seat_ids):
        current_app.logger.error(
            "Cash booking %s: only %s/%s requested seats could be confirmed (seat_ids=%s) - "
            "needs manual resolution", booking.reference, confirmed, len(seat_ids), seat_ids,
        )
    log_event(Event.BOOKING_COMPLETED_CASH, None, meta=booking.reference)
    db.session.refresh(booking)
    try:
        emailer.send_booking_confirmation(booking)
    except Exception:
        current_app.logger.exception(
            "send_booking_confirmation failed for cash booking %s - use admin resend", booking.reference
        )

    return jsonify({"ok": True, "reference": booking.reference})


@admin_bp.route("/api/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def api_cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    seats = list(booking.seats)
    cancel_booking(booking)
    booking.payment_status = PaymentStatus.CANCELLED
    db.session.commit()
    for seat in seats:
        wallet.revoke_wallet_pass(seat.wallet_serial, current_app.config)
    return jsonify({"ok": True})


@admin_bp.route("/booking/<reference>")
@login_required
def booking_overview(reference):
    """Manual lookup by booking reference - shows every seat in the booking
    with its own check-in status, for group bookings where scanning each
    seat's QR individually isn't convenient."""
    booking = Booking.query.filter_by(reference=reference.strip().upper()).first()
    if not booking:
        flash(f"No booking found for '{reference}'.", "error")
        return redirect(url_for("admin.dashboard"))
    return render_template(
        "admin/booking.html", cfg=current_app.config, booking=booking,
        can_reset=current_user.is_superadmin,
    )


@admin_bp.route("/booking/<reference>/resend-email", methods=["POST"])
@login_required
def resend_email(reference):
    booking = Booking.query.filter_by(reference=reference.strip().upper()).first()
    if not booking:
        flash(f"No booking found for '{reference}'.", "error")
        return redirect(url_for("admin.dashboard"))

    if booking.payment_status != PaymentStatus.PAID:
        flash("This booking isn't marked as paid - not resending a confirmation email.", "error")
        return redirect(url_for("admin.booking_overview", reference=booking.reference))

    try:
        emailer.send_booking_confirmation(booking)
        flash(f"Confirmation email re-sent to {booking.email}.", "success")
    except Exception:
        current_app.logger.exception("Manual resend failed for booking %s", booking.reference)
        flash("Failed to send the email - check the error log for details.", "error")

    return redirect(url_for("admin.booking_overview", reference=booking.reference))


@admin_bp.route("/checkin/<token>", methods=["GET"])
@login_required
def checkin(token):
    seat = Seat.query.filter_by(checkin_token=token).first()
    if not seat:
        flash(f"No ticket found for '{token}'.", "error")
        return redirect(url_for("admin.dashboard"))
    if not seat.booking or seat.booking.payment_status == PaymentStatus.CANCELLED:
        flash(f"Seat {seat.label}'s booking has been cancelled - this ticket is no longer valid.", "error")
        return redirect(url_for("admin.dashboard"))
    just_checked_in = request.args.get("just_now") == "1"
    return render_template(
        "admin/checkin.html", cfg=current_app.config, seat=seat, booking=seat.booking,
        just_checked_in=just_checked_in, can_reset=current_user.is_superadmin,
    )


@admin_bp.route("/checkin/<token>", methods=["POST"])
@login_required
def checkin_confirm(token):
    seat = Seat.query.filter_by(checkin_token=token).first()
    if not seat:
        flash(f"No ticket found for '{token}'.", "error")
        return redirect(url_for("admin.dashboard"))
    if not seat.booking or seat.booking.payment_status == PaymentStatus.CANCELLED:
        flash(f"Seat {seat.label}'s booking has been cancelled - this ticket is no longer valid.", "error")
        return redirect(url_for("admin.dashboard"))

    just_now = False
    if seat.booking and seat.booking.payment_status == PaymentStatus.PAID and not seat.checked_in_at:
        seat.checked_in_at = datetime.utcnow()
        db.session.commit()
        just_now = True

    return redirect(url_for("admin.checkin", token=token, just_now="1" if just_now else None))


@admin_bp.route("/checkin/<token>/reset", methods=["POST"])
@login_required
def checkin_reset(token):
    if not current_user.is_superadmin:
        flash("Only a superadmin can reset a ticket's check-in status.", "error")
        return redirect(url_for("admin.checkin", token=token))

    seat = Seat.query.filter_by(checkin_token=token).first()
    if not seat:
        flash(f"No ticket found for '{token}'.", "error")
        return redirect(url_for("admin.dashboard"))

    seat.checked_in_at = None
    db.session.commit()
    flash(f"Check-in reset for seat {seat.label} - it can be scanned in again.", "success")
    return redirect(url_for("admin.checkin", token=token))


@admin_bp.route("/checkin-lookup", methods=["POST"])
@login_required
def checkin_lookup():
    code = (request.form.get("code") or "").strip()
    if not code:
        flash("Enter a booking reference or scan a ticket QR code.", "error")
        return redirect(url_for("admin.dashboard"))
    if Seat.query.filter_by(checkin_token=code).first():
        return redirect(url_for("admin.checkin", token=code))
    return redirect(url_for("admin.booking_overview", reference=code))


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


def _analytics_window():
    """?days=N restricts the funnel report to the last N days; omitted or
    invalid means all-time."""
    days = request.args.get("days", type=int)
    if not days or days <= 0:
        return None, None
    return datetime.utcnow() - timedelta(days=days), None


@admin_bp.route("/analytics")
@login_required
def analytics():
    start, end = _analytics_window()
    summary = funnel_summary(start, end)
    daily_rows = daily_breakdown(start, end)
    return render_template(
        "admin/analytics.html", cfg=current_app.config, summary=summary,
        daily_rows=daily_rows, days=request.args.get("days", type=int),
    )


@admin_bp.route("/analytics.xlsx")
@login_required
def analytics_report():
    start, end = _analytics_window()
    summary = funnel_summary(start, end)
    daily_rows = daily_breakdown(start, end)
    buf = build_analytics_report(summary, daily_rows)
    return send_file(
        buf,
        as_attachment=True,
        download_name="fireworks-marketing-funnel.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/admins")
@superadmin_required
def manage_admins():
    admins = Admin.query.order_by(Admin.email).all()
    return render_template("admin/admins.html", cfg=current_app.config, admins=admins)


@admin_bp.route("/admins", methods=["POST"])
@superadmin_required
def create_admin():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    is_superadmin = request.form.get("is_superadmin") == "on"

    if not email or not password:
        flash("Email and password are required.", "error")
    elif len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
    elif Admin.query.filter_by(email=email).first():
        flash(f"An admin with email {email} already exists.", "error")
    else:
        admin = Admin(email=email, password_hash=generate_password_hash(password), is_superadmin=is_superadmin)
        db.session.add(admin)
        db.session.commit()
        flash(f"Admin account created: {email}", "success")

    return redirect(url_for("admin.manage_admins"))


@admin_bp.route("/admins/<int:admin_id>/delete", methods=["POST"])
@superadmin_required
def delete_admin(admin_id):
    target = Admin.query.get_or_404(admin_id)
    if target.id == current_user.id:
        flash("You can't delete your own account.", "error")
    elif target.is_superadmin and Admin.query.filter_by(is_superadmin=True).count() <= 1:
        flash("Can't delete the last superadmin account.", "error")
    else:
        db.session.delete(target)
        db.session.commit()
        flash(f"Admin account removed: {target.email}", "success")
    return redirect(url_for("admin.manage_admins"))
