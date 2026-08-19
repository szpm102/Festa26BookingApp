import stripe
from flask import current_app


def _configure():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]


def create_checkout_session(seat_ids, seat_labels, unit_amount_cents, attendee_name, email, phone, session_id):
    _configure()
    cfg = current_app.config
    checkout = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        customer_email=email,
        line_items=[
            {
                "price_data": {
                    "currency": cfg["CURRENCY"],
                    "unit_amount": unit_amount_cents,
                    "product_data": {
                        "name": f"Fireworks Display Seat {label}",
                    },
                },
                "quantity": 1,
            }
            for label in seat_labels
        ],
        metadata={
            "seat_ids": ",".join(str(i) for i in seat_ids),
            "attendee_name": attendee_name,
            "email": email,
            "phone": phone or "",
            "session_id": session_id,
        },
        success_url=cfg["BASE_URL"] + "/booking/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cfg["BASE_URL"] + "/booking/cancelled",
    )
    return checkout


def retrieve_checkout_session(stripe_session_id):
    _configure()
    return stripe.checkout.Session.retrieve(stripe_session_id)


def construct_webhook_event(payload, sig_header):
    _configure()
    cfg = current_app.config
    return stripe.Webhook.construct_event(payload, sig_header, cfg["STRIPE_WEBHOOK_SECRET"])
