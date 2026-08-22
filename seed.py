"""Run once (and again any time you add new seats) to initialise the database:

    python seed.py

Creates the 300 seats from seat_config.py (skipping any labels that already
exist) and ensures the admin account from config/env vars exists as a
superadmin (the only kind of account allowed to reset a ticket's check-in
status).

To add an extra staff/door account (regular, cannot reset check-ins):

    python seed.py add-admin door@szpm.mt somepassword

Add --superadmin to give that new account reset rights too:

    python seed.py add-admin organiser@szpm.mt somepassword --superadmin
"""

import sys

from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import Seat, Admin, SeatStatus
from seat_config import SEAT_LAYOUT, FIRST_BATCH_LABELS


def seed_seats_and_primary_admin(app):
    existing = {s.label: s for s in Seat.query.all()}

    added = 0
    updated = 0
    for entry in SEAT_LAYOUT:
        initial_status = SeatStatus.AVAILABLE if entry["label"] in FIRST_BATCH_LABELS else SeatStatus.DISABLED
        seat = existing.get(entry["label"])
        if seat is None:
            db.session.add(Seat(
                section=entry["section"],
                row_label=entry["row"],
                seat_number=entry["number"],
                label=entry["label"],
                status=initial_status,
                price_eur=app.config["SEAT_PRICE_EUR"],
            ))
            added += 1
            continue

        # Seat already exists (e.g. from an earlier placeholder layout) -
        # always safe to correct its section/row/number, since that never
        # touches a booking. Only set its initial open/closed status if
        # it's still untouched (available) - never override a seat that's
        # already booked, held, or one an admin has deliberately disabled
        # or enabled by hand.
        seat.section = entry["section"]
        seat.row_label = entry["row"]
        seat.seat_number = entry["number"]
        if seat.status == SeatStatus.AVAILABLE:
            seat.status = initial_status
            updated += 1
    db.session.commit()
    print(f"Seats: {added} added, {updated} synced to the new layout, {Seat.query.count()} total in database.")

    admin_email = app.config["ADMIN_EMAIL"].lower()
    admin = Admin.query.filter_by(email=admin_email).first()
    if not admin:
        admin = Admin(
            email=admin_email,
            password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]),
            is_superadmin=True,
        )
        db.session.add(admin)
        db.session.commit()
        print(f"Superadmin account created: {admin_email}")
    else:
        print(f"Admin account already exists: {admin_email}")


def add_admin(email, password, is_superadmin):
    email = email.strip().lower()
    if Admin.query.filter_by(email=email).first():
        print(f"An admin with email {email} already exists.")
        return
    admin = Admin(
        email=email,
        password_hash=generate_password_hash(password),
        is_superadmin=is_superadmin,
    )
    db.session.add(admin)
    db.session.commit()
    kind = "superadmin" if is_superadmin else "admin"
    print(f"{kind.capitalize()} account created: {email}")


def run():
    app = create_app()
    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == "add-admin":
            if len(sys.argv) < 4:
                print("Usage: python seed.py add-admin <email> <password> [--superadmin]")
                sys.exit(1)
            email, password = sys.argv[2], sys.argv[3]
            is_superadmin = "--superadmin" in sys.argv[4:]
            add_admin(email, password, is_superadmin)
        else:
            seed_seats_and_primary_admin(app)


if __name__ == "__main__":
    run()
