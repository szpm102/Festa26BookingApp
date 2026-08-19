"""Run once (and again any time you add new seats) to initialise the database:

    python seed.py

Creates the 300 seats from seat_config.py (skipping any labels that already
exist) and ensures the admin account from config/env vars exists.
"""

from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import Seat, Admin
from seat_config import SEAT_LAYOUT


def run():
    app = create_app()
    with app.app_context():
        existing_labels = {label for (label,) in db.session.query(Seat.label).all()}

        added = 0
        for entry in SEAT_LAYOUT:
            if entry["label"] in existing_labels:
                continue
            seat = Seat(
                section=entry["section"],
                row_label=entry["row"],
                seat_number=entry["number"],
                label=entry["label"],
                price_eur=app.config["SEAT_PRICE_EUR"],
            )
            db.session.add(seat)
            added += 1
        db.session.commit()
        print(f"Seats: {added} added, {Seat.query.count()} total in database.")

        admin_email = app.config["ADMIN_EMAIL"].lower()
        admin = Admin.query.filter_by(email=admin_email).first()
        if not admin:
            admin = Admin(
                email=admin_email,
                password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]),
            )
            db.session.add(admin)
            db.session.commit()
            print(f"Admin account created: {admin_email}")
        else:
            print(f"Admin account already exists: {admin_email}")


if __name__ == "__main__":
    run()
