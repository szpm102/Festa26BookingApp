"""Minimal self-hosted marketing funnel tracking - visits, key interaction
clicks, and how many of them turn into a booking. No third-party analytics
service and no personal data: just the same per-browser session id already
used for seat holds, an event type, and a timestamp.
"""

from datetime import datetime
from flask import current_app

from extensions import db
from models import AnalyticsEvent


class Event:
    PAGE_VIEW = "page_view"
    BOOK_CTA_CLICK = "book_cta_click"
    SEAT_SELECTED = "seat_selected"
    CHECKOUT_STARTED = "checkout_started"
    BOOKING_COMPLETED_ONLINE = "booking_completed_online"
    BOOKING_COMPLETED_CASH = "booking_completed_cash"


# Only these are ever accepted from the public /api/track endpoint - keeps
# it from being usable to log arbitrary junk into the table. Seat selection
# itself is logged server-side in routes_api.hold() instead, since that
# already has an authoritative signal (a successful hold).
CLIENT_LOGGABLE_EVENTS = {Event.BOOK_CTA_CLICK}


def has_event(event_type, session_id):
    if not session_id:
        return False
    return AnalyticsEvent.query.filter_by(event_type=event_type, session_id=session_id).first() is not None


def log_event(event_type, session_id=None, meta=None):
    """Fire-and-forget: a logging failure must never break the request it's
    attached to, so any error is caught and logged rather than raised."""
    try:
        db.session.add(AnalyticsEvent(
            session_id=session_id, event_type=event_type, meta=meta,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to log analytics event %s", event_type)


def funnel_summary(start=None, end=None):
    """Counts of each event type in [start, end), plus derived conversion
    rates, for the admin analytics report."""
    q = AnalyticsEvent.query
    if start:
        q = q.filter(AnalyticsEvent.created_at >= start)
    if end:
        q = q.filter(AnalyticsEvent.created_at < end)
    rows = q.all()

    counts = {}
    unique_sessions = set()
    for row in rows:
        counts[row.event_type] = counts.get(row.event_type, 0) + 1
        if row.session_id:
            unique_sessions.add(row.session_id)

    page_views = counts.get(Event.PAGE_VIEW, 0)
    visits = len(unique_sessions)
    book_clicks = counts.get(Event.BOOK_CTA_CLICK, 0)
    seat_selected = counts.get(Event.SEAT_SELECTED, 0)
    checkout_started = counts.get(Event.CHECKOUT_STARTED, 0)
    booked_online = counts.get(Event.BOOKING_COMPLETED_ONLINE, 0)
    booked_cash = counts.get(Event.BOOKING_COMPLETED_CASH, 0)

    def rate(n, d):
        return round(100.0 * n / d, 1) if d else None

    return {
        "page_views": page_views,
        "visits": visits,
        "book_clicks": book_clicks,
        "seat_selected": seat_selected,
        "checkout_started": checkout_started,
        "booked_online": booked_online,
        "booked_cash": booked_cash,
        "booked_total": booked_online + booked_cash,
        "rate_visit_to_click": rate(book_clicks, visits),
        "rate_click_to_seat": rate(seat_selected, book_clicks),
        "rate_seat_to_checkout": rate(checkout_started, seat_selected),
        "rate_checkout_to_booked": rate(booked_online, checkout_started),
        "rate_visit_to_booked": rate(booked_online, visits),
    }


def daily_breakdown(start=None, end=None):
    """One row per calendar day: visits (unique sessions with a page_view
    that day) and completed online bookings that day - the two numbers
    most useful for a day-by-day marketing trend."""
    q = AnalyticsEvent.query
    if start:
        q = q.filter(AnalyticsEvent.created_at >= start)
    if end:
        q = q.filter(AnalyticsEvent.created_at < end)
    rows = q.order_by(AnalyticsEvent.created_at.asc()).all()

    by_day = {}
    for row in rows:
        day = row.created_at.date()
        bucket = by_day.setdefault(day, {"sessions": set(), "booked_online": 0, "booked_cash": 0})
        if row.event_type == Event.PAGE_VIEW and row.session_id:
            bucket["sessions"].add(row.session_id)
        elif row.event_type == Event.BOOKING_COMPLETED_ONLINE:
            bucket["booked_online"] += 1
        elif row.event_type == Event.BOOKING_COMPLETED_CASH:
            bucket["booked_cash"] += 1

    return [
        {
            "date": day,
            "visits": len(b["sessions"]),
            "booked_online": b["booked_online"],
            "booked_cash": b["booked_cash"],
        }
        for day, b in sorted(by_day.items())
    ]
