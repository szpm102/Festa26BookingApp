from datetime import datetime

from flask import Blueprint, jsonify, request, session, current_app

from models import Seat, SeatStatus
from seats import sweep_expired_holds, hold_seats, release_seats
from analytics import Event, log_event, has_event, CLIENT_LOGGABLE_EVENTS
from extensions import csrf, limiter

api_bp = Blueprint("api", __name__, url_prefix="/api")
csrf.exempt(api_bp)

MAX_SEATS_PER_SESSION = 10


def _serialize_seats(sid):
    seats = Seat.query.order_by(Seat.row_label, Seat.seat_number).all()
    out = []
    for s in seats:
        status = s.status
        mine = False
        if status == SeatStatus.HELD and s.held_by_session == sid:
            status = "held_mine"
            mine = True
        out.append({
            "id": s.id,
            "label": s.label,
            "section": s.section,
            "row": s.row_label,
            "number": s.seat_number,
            "status": status,
            "mine": mine,
            "price": s.price_eur,
        })
    return out


@api_bp.route("/seats")
def list_seats():
    sweep_expired_holds()
    sid = session.get("sid")
    return jsonify({"seats": _serialize_seats(sid)})


@api_bp.route("/hold", methods=["POST"])
@limiter.limit("20 per minute")
def hold():
    sweep_expired_holds()
    sid = session["sid"]
    data = request.get_json(force=True) or {}
    seat_id = data.get("seat_id")
    if seat_id is None:
        return jsonify({"ok": False, "error": "seat_id required"}), 400

    already_held = Seat.query.filter(
        Seat.status == SeatStatus.HELD, Seat.held_by_session == sid
    ).count()
    if already_held >= MAX_SEATS_PER_SESSION:
        return jsonify({
            "ok": False,
            "error": f"You can select at most {MAX_SEATS_PER_SESSION} seats per booking.",
        }), 400

    hold_until = datetime.utcnow() + current_app.config["SEAT_HOLD_DURATION"]
    ok_ids, failed_ids = hold_seats([seat_id], sid, hold_until)

    if ok_ids:
        if not has_event(Event.SEAT_SELECTED, sid):
            log_event(Event.SEAT_SELECTED, sid)
        return jsonify({"ok": True, "seats": _serialize_seats(sid)})
    return jsonify({"ok": False, "error": "That seat was just taken. Please pick another.", "seats": _serialize_seats(sid)}), 409


@api_bp.route("/track", methods=["POST"])
@limiter.limit("30 per minute")
def track():
    """Fire-and-forget client-side interaction logging for the marketing
    funnel report - restricted to a fixed allow-list so this can't be used
    to write arbitrary event types."""
    data = request.get_json(force=True) or {}
    event_type = data.get("event_type")
    if event_type not in CLIENT_LOGGABLE_EVENTS:
        return jsonify({"ok": False}), 400
    log_event(event_type, session.get("sid"))
    return jsonify({"ok": True})


@api_bp.route("/release", methods=["POST"])
def release():
    sid = session["sid"]
    data = request.get_json(force=True) or {}
    seat_id = data.get("seat_id")
    if seat_id is None:
        return jsonify({"ok": False, "error": "seat_id required"}), 400
    release_seats([seat_id], sid)
    return jsonify({"ok": True, "seats": _serialize_seats(sid)})
