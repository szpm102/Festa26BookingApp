from flask import Blueprint, request, jsonify, current_app

from extensions import db, csrf
from models import Seat, Booking, SeatStatus, PaymentMethod, PaymentStatus
from seats import confirm_seats_for_booking
from utils import generate_reference
from analytics import Event, log_event
import payments
import emailer
import ticketing

webhooks_bp = Blueprint("webhooks", __name__)
csrf.exempt(webhooks_bp)


@webhooks_bp.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    # Fail closed, not open: verifying a signature against a blank secret is
    # not meaningfully different from not verifying at all - refuse outright
    # rather than let a misconfigured deployment silently accept forged
    # "payment completed" requests.
    if not current_app.config.get("STRIPE_WEBHOOK_SECRET"):
        current_app.logger.error("STRIPE_WEBHOOK_SECRET is not configured - rejecting webhook request")
        return jsonify({"error": "webhook not configured"}), 503

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = payments.construct_webhook_event(payload, sig_header)
    except Exception:
        current_app.logger.exception("Invalid Stripe webhook signature")
        return jsonify({"error": "invalid signature"}), 400

    if event["type"] == "checkout.session.completed":
        checkout_session = event["data"]["object"]
        _fulfil_checkout(checkout_session)

    return jsonify({"received": True})


def _fulfil_checkout(checkout_session):
    metadata = checkout_session.get("metadata", {})
    seat_ids_meta = metadata.get("seat_ids", "")
    if not seat_ids_meta:
        return
    seat_ids = [int(i) for i in seat_ids_meta.split(",") if i]

    existing = Booking.query.filter_by(stripe_session_id=checkout_session["id"]).first()
    if existing:
        return  # already processed (webhook can be retried by Stripe)

    amount_total = (checkout_session.get("amount_total") or 0) / 100.0

    booking = Booking(
        reference=generate_reference(),
        attendee_name=metadata.get("attendee_name", "Guest"),
        email=metadata.get("email") or checkout_session.get("customer_email") or "",
        phone=metadata.get("phone", ""),
        amount_total_eur=amount_total,
        payment_method=PaymentMethod.STRIPE,
        payment_status=PaymentStatus.PAID,
        stripe_session_id=checkout_session["id"],
        created_by_admin=False,
        access_token=ticketing.generate_checkin_token(),
    )
    db.session.add(booking)
    db.session.commit()

    confirmed = confirm_seats_for_booking(
        seat_ids, booking.id, from_statuses=[SeatStatus.HELD, SeatStatus.AVAILABLE]
    )
    if confirmed < len(seat_ids):
        # The customer already paid, but one or more of the seats they picked
        # were re-sold to someone else (or otherwise left AVAILABLE/HELD)
        # before this webhook ran - most likely their hold expired while they
        # were still on Stripe's page. send_booking_confirmation() below
        # detects a booking with no/fewer seats and sends a distinct "we need
        # to sort this out" email instead of a broken blank ticket, but this
        # still needs a human to actually resolve it.
        current_app.logger.error(
            "Booking %s: only %s/%s requested seats could be confirmed "
            "(seat_ids=%s) - needs manual resolution",
            booking.reference, confirmed, len(seat_ids), seat_ids,
        )
    else:
        current_app.logger.info("Confirmed %s seats for booking %s", confirmed, booking.reference)

    log_event(Event.BOOKING_COMPLETED_ONLINE, metadata.get("session_id"), meta=booking.reference)

    db.session.refresh(booking)
    try:
        emailer.send_booking_confirmation(booking)
    except Exception:
        # The seat is already booked and paid at this point - Stripe must not
        # retry (it would just hit the "already processed" guard above and
        # skip the email forever). Log it; an admin can resend manually from
        # the booking overview page.
        current_app.logger.exception(
            "send_booking_confirmation failed for booking %s - use admin resend", booking.reference
        )
