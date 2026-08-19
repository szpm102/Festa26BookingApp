from datetime import datetime, timedelta
from flask_login import UserMixin
from extensions import db


class SeatStatus:
    AVAILABLE = "available"
    HELD = "held"
    BOOKED = "booked"
    DISABLED = "disabled"


class PaymentMethod:
    STRIPE = "stripe"
    CASH = "cash"


class PaymentStatus:
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class Seat(db.Model):
    __tablename__ = "seats"

    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(20), nullable=False)
    row_label = db.Column(db.String(5), nullable=False)
    seat_number = db.Column(db.Integer, nullable=False)
    label = db.Column(db.String(20), unique=True, nullable=False)  # e.g. "A-12"

    status = db.Column(db.String(20), nullable=False, default=SeatStatus.AVAILABLE)
    price_eur = db.Column(db.Float, nullable=False, default=5.0)

    held_by_session = db.Column(db.String(64), nullable=True)
    held_until = db.Column(db.DateTime, nullable=True)

    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "label": self.label,
            "section": self.section,
            "row": self.row_label,
            "number": self.seat_number,
            "status": self.status,
            "price": self.price_eur,
        }


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False)

    attendee_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(40), nullable=True)

    amount_total_eur = db.Column(db.Float, nullable=False, default=0.0)
    payment_method = db.Column(db.String(20), nullable=False, default=PaymentMethod.STRIPE)
    payment_status = db.Column(db.String(20), nullable=False, default=PaymentStatus.PENDING)

    stripe_session_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_admin = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String(255), nullable=True)

    seats = db.relationship("Seat", backref="booking", lazy=True)

    def seat_labels(self):
        return ", ".join(sorted(s.label for s in self.seats))


class Admin(UserMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
