import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    # Database (SQLite by default for local/dev; set DATABASE_URL in prod, e.g. Postgres)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "bookings.db")
    )
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        # SQLAlchemy 1.4+/2.0 requires the postgresql:// scheme
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Event details (from the official poster)
    EVENT_NAME = "Light Up the Sky - Fireworks Display"
    EVENT_SUBTITLE = "Fireworks Display Synchronised with Music"
    EVENT_ANNIVERSARY = "15th Anniversary"
    EVENT_LOCATION = "Andrijiet Street, Munxar, Gozo"
    EVENT_DATE_TEXT = "Saturday, 12th September 2026"
    EVENT_TIME_TEXT = "21:30"
    EVENT_DATETIME_ISO = "2026-09-12T21:30:00"
    EVENT_ORGANISERS = "Government of Malta - Ministry for Gozo | Munxar Local Council"

    # Wider festa program (this site only sells seats for "Light Up the Sky",
    # but the home page cross-promotes the full week so visitors see this is
    # one event within it - matches the official festa poster).
    FESTIVAL_NAME = "Festa San Pawl Nawfragu"
    FESTIVAL_EYEBROW = "Sezzjoni Zghazagh Pawlini Munxarin"
    FESTIVAL_PLACE = "Munxar, Ghawdex"
    FESTIVAL_DATES_TEXT = "5 - 13 ta' Settembru 2026"
    SOCIAL_FACEBOOK_HANDLE = "szpmgozo"
    SOCIAL_INSTAGRAM_HANDLE = "szpm.mt"

    PROGRAMME = [
        {
            "key": "nar",
            "name": "Nar tal-Art",
            "tagline": "Ground fireworks display",
            "date": "Friday, 11th September",
            "time": "00:00",
            "location": "Pjazza tal-Munxar",
            "current": False,
        },
        {
            "key": "sky",
            "name": "Light Up the Sky",
            "tagline": "Fireworks display synchronised with music",
            "date": "Saturday, 12th September",
            "time": "21:30",
            "location": "Andrijiet Street, Munxar",
            "current": True,
        },
        {
            "key": "stars",
            "name": "Sky Full of Stars",
            "tagline": "Fireworks display synchronised with music - HoloConcert + Live Orchestra",
            "date": "Saturday, 12th September",
            "time": "22:30",
            "location": "Madonna tal-Karmnu Street, Munxar",
            "current": False,
        },
        {
            "key": "festa",
            "name": "Jum il-Festa",
            "tagline": "Procession of St Paul Shipwrecked",
            "date": "Sunday, 13th September",
            "time": "19:00",
            "location": "Munxar",
            "current": False,
        },
    ]

    # Seats
    TOTAL_SEATS = int(os.environ.get("TOTAL_SEATS", 300))
    SEAT_PRICE_EUR = float(os.environ.get("SEAT_PRICE_EUR", 5.00))
    SEAT_HOLD_MINUTES = int(os.environ.get("SEAT_HOLD_MINUTES", 7))
    SEAT_HOLD_DURATION = timedelta(minutes=SEAT_HOLD_MINUTES)

    # Admin
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")

    # Stripe
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    CURRENCY = "eur"

    # Email (Microsoft 365 / Outlook SMTP)
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.office365.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "Festa Munxar - Fireworks Booking")
    TEAM_NOTIFY_EMAILS = [
        e.strip() for e in os.environ.get("TEAM_NOTIFY_EMAILS", "").split(",") if e.strip()
    ]

    # Base URL used in emails / Stripe redirect (set to the real public URL once deployed)
    BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
