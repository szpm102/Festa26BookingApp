import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


def _env(key, default=""):
    """Like os.environ.get, but a blank value (e.g. an empty 'KEY=' line in
    a .env file) falls back to the default too, not just a missing key."""
    return os.environ.get(key) or default


class Config:
    SECRET_KEY = _env("SECRET_KEY", "change-me-in-production")

    # Database (SQLite by default for local/dev; set DATABASE_URL in prod, e.g. Postgres)
    SQLALCHEMY_DATABASE_URI = _env(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "bookings.db")
    )
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        # SQLAlchemy 1.4+/2.0 requires the postgresql:// scheme
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Browser tab / bookmark title (kept separate from EVENT_NAME, which is
    # the event's own name shown throughout the page content and emails).
    SITE_TITLE = "SZPM | Munxar Feast 2026"

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
    FESTIVAL_NAME = "Feast of Saint Paul Shipwreck"
    FESTIVAL_EYEBROW = "Sezzjoni Zghazagh Pawlini Munxarin"
    FESTIVAL_PLACE = "Munxar, Gozo"
    FESTIVAL_DATES_TEXT = "5 - 13 September 2026"
    SOCIAL_FACEBOOK_HANDLE = "szpmgozo"
    SOCIAL_INSTAGRAM_HANDLE = "szpm.mt"

    PROGRAMME = [
        {
            "key": "nar",
            "name": "Ground Fireworks",
            "tagline": "Ground fireworks display",
            "date": "Friday, 11th September",
            "time": "00:00",
            "location": "Munxar Square",
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
            "tagline": "38-piece live orchestra with immersive holographic displays and light show",
            "date": "Saturday, 12th September",
            "time": "22:30",
            "location": "Our Lady of Mount Carmel Street, Munxar",
            "current": False,
        },
        {
            "key": "festa",
            "name": "Feast Day",
            "tagline": "Procession of St Paul Shipwrecked",
            "date": "Sunday, 13th September",
            "time": "19:00",
            "location": "Munxar",
            "current": False,
        },
    ]

    # Seats
    TOTAL_SEATS = int(_env("TOTAL_SEATS", "300"))
    SEAT_PRICE_EUR = float(_env("SEAT_PRICE_EUR", "4.00"))
    SEAT_HOLD_MINUTES = int(_env("SEAT_HOLD_MINUTES", "7"))
    SEAT_HOLD_DURATION = timedelta(minutes=SEAT_HOLD_MINUTES)

    # Policy text shown on the booking page, in confirmation emails, and on
    # the PDF ticket. Edit here to change the wording everywhere at once.
    ADMIN_CONTACT_EMAIL = _env("ADMIN_CONTACT_EMAIL", "admin@szpm.mt")
    REFUND_POLICY_TEXT = "All bookings are final. Tickets are non-refundable."
    PRIVACY_NOTICE_TEXT = (
        f"Your name, email and phone number are used to process this booking and for future "
        f"SZPM promotional updates. Email {ADMIN_CONTACT_EMAIL} anytime to cancel your booking or opt out."
    )

    # Admin
    ADMIN_EMAIL = _env("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD = _env("ADMIN_PASSWORD", "changeme123")

    # WalletWallet.dev - generates Apple Wallet (.pkpass) + Google Wallet passes
    # without needing our own Apple Developer / Google Wallet issuer account.
    # Optional: leave WALLETWALLET_API_KEY empty to skip wallet passes entirely
    # (the QR code + PDF ticket always work regardless).
    WALLETWALLET_API_KEY = _env("WALLETWALLET_API_KEY")
    WALLETWALLET_API_URL = "https://api.walletwallet.dev/api/passes"

    # Stripe
    STRIPE_SECRET_KEY = _env("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY = _env("STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET = _env("STRIPE_WEBHOOK_SECRET")
    CURRENCY = "eur"

    # Email (Microsoft 365 / Outlook SMTP)
    SMTP_HOST = _env("SMTP_HOST", "smtp.office365.com")
    SMTP_PORT = int(_env("SMTP_PORT", "587"))
    SMTP_USER = _env("SMTP_USER")
    SMTP_PASSWORD = _env("SMTP_PASSWORD")
    MAIL_FROM_NAME = _env("MAIL_FROM_NAME", "Festa Munxar - Fireworks Booking")
    TEAM_NOTIFY_EMAILS = [
        e.strip() for e in _env("TEAM_NOTIFY_EMAILS").split(",") if e.strip()
    ]

    # Base URL used in emails / Stripe redirect (set to the real public URL once deployed)
    BASE_URL = _env("BASE_URL", "http://127.0.0.1:5000")

    # Session cookie hardening. SECURE is tied to BASE_URL rather than a
    # separate flag: once deployed over HTTPS (as PythonAnywhere/any real
    # host will be), cookies are only ever sent encrypted; on local
    # http://127.0.0.1 dev it stays off automatically so login still works.
    SESSION_COOKIE_SECURE = BASE_URL.startswith("https://")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
