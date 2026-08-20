import io
import uuid
from datetime import datetime

from flask import Blueprint, render_template, session, jsonify, request, current_app, send_file, abort, redirect

from extensions import db, csrf, limiter
from models import Seat, Booking, SeatStatus, PaymentMethod, PaymentStatus
from seats import sweep_expired_holds, release_seats
from analytics import Event, log_event
import payments
import ticketing
import wallet

public_bp = Blueprint("public", __name__)
csrf.exempt(public_bp)


@public_bp.before_app_request
def ensure_session_id():
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    session.permanent = True


@public_bp.route("/")
def index():
    sweep_expired_holds()
    log_event(Event.PAGE_VIEW, session.get("sid"))
    cfg = current_app.config
    return render_template(
        "index.html",
        cfg=cfg,
        stripe_publishable_key=cfg["STRIPE_PUBLISHABLE_KEY"],
        seat_price=cfg["SEAT_PRICE_EUR"],
        hold_minutes=cfg["SEAT_HOLD_MINUTES"],
    )


@public_bp.route("/booking/checkout", methods=["POST"])
@limiter.limit("10 per minute")
def checkout():
    """Create a Stripe Checkout session for the seats currently held by this
    browser session."""
    sweep_expired_holds()
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not name or not email:
        return jsonify({"ok": False, "error": "Name and email are required."}), 400

    sid = session["sid"]
    held = Seat.query.filter(
        Seat.status == SeatStatus.HELD, Seat.held_by_session == sid
    ).all()
    if not held:
        return jsonify({"ok": False, "error": "No seats selected, or your hold expired. Please reselect your seats."}), 400

    seat_ids = [s.id for s in held]
    seat_labels = [s.label for s in held]
    unit_amount_cents = int(round(current_app.config["SEAT_PRICE_EUR"] * 100))

    try:
        checkout_session = payments.create_checkout_session(
            seat_ids, seat_labels, unit_amount_cents, name, email, phone, sid
        )
    except Exception as exc:
        current_app.logger.exception("Stripe checkout session creation failed")
        return jsonify({"ok": False, "error": f"Payment setup failed: {exc}"}), 500

    log_event(Event.CHECKOUT_STARTED, sid, meta=str(len(seat_ids)))
    return jsonify({"ok": True, "checkout_url": checkout_session.url})


@public_bp.route("/booking/success")
def booking_success():
    session_id = request.args.get("session_id")
    seat_labels = []
    email = None
    amount = None
    if session_id:
        try:
            checkout_session = payments.retrieve_checkout_session(session_id)
            email = checkout_session.get("customer_email") or checkout_session.metadata.get("email")
            amount = (checkout_session.get("amount_total") or 0) / 100.0
            seat_ids_meta = checkout_session.metadata.get("seat_ids", "")
            if seat_ids_meta:
                ids = [int(i) for i in seat_ids_meta.split(",") if i]
                seat_labels = [s.label for s in Seat.query.filter(Seat.id.in_(ids)).all()]
        except Exception:
            current_app.logger.exception("Could not retrieve Stripe session on success page")

    return render_template(
        "success.html",
        cfg=current_app.config,
        seat_labels=seat_labels,
        email=email,
        amount=amount,
    )


@public_bp.route("/ticket/<token>")
def download_ticket(token):
    """Let a guest re-download their combined PDF ticket (all seats) using
    the private access token from their confirmation email - no login
    needed, the token is the key."""
    booking = Booking.query.filter_by(access_token=token).first()
    if not booking or booking.payment_status != PaymentStatus.PAID:
        abort(404)

    seat_qr_pairs = []
    for seat in sorted(booking.seats, key=lambda s: s.label):
        if not seat.checkin_token:
            seat.checkin_token = ticketing.generate_checkin_token()
            db.session.commit()
        checkin_url = f"{current_app.config['BASE_URL']}/admin/checkin/{seat.checkin_token}"
        seat_qr_pairs.append((seat, ticketing.build_qr_png(checkin_url)))

    pdf_bytes = ticketing.build_ticket_pdf(booking, current_app.config, seat_qr_pairs)

    return send_file(
        io.BytesIO(pdf_bytes),
        as_attachment=True,
        download_name=f"ticket-{booking.reference}.pdf",
        mimetype="application/pdf",
    )


@public_bp.route("/ticket/<token>/wallet/apple/<int:seat_id>")
def download_apple_wallet(token, seat_id):
    booking = Booking.query.filter_by(access_token=token).first()
    if not booking or booking.payment_status != PaymentStatus.PAID:
        abort(404)
    seat = next((s for s in booking.seats if s.id == seat_id), None)
    if not seat or not seat.wallet_apple_pass_b64:
        abort(404)
    return send_file(
        io.BytesIO(wallet.decode_apple_pass(seat.wallet_apple_pass_b64)),
        as_attachment=True,
        download_name=f"ticket-{booking.reference}-{seat.label}.pkpass",
        mimetype="application/vnd.apple.pkpass",
    )


@public_bp.route("/ticket/<token>/wallet/google/<int:seat_id>")
def redirect_google_wallet(token, seat_id):
    booking = Booking.query.filter_by(access_token=token).first()
    if not booking or booking.payment_status != PaymentStatus.PAID:
        abort(404)
    seat = next((s for s in booking.seats if s.id == seat_id), None)
    if not seat or not seat.wallet_google_url:
        abort(404)
    return redirect(seat.wallet_google_url)


@public_bp.route("/booking/cancelled")
def booking_cancelled():
    sid = session.get("sid")
    if sid:
        held = Seat.query.filter(Seat.status == SeatStatus.HELD, Seat.held_by_session == sid).all()
        release_seats([s.id for s in held], sid)
    return render_template("cancel.html", cfg=current_app.config)
