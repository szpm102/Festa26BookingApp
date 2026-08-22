from datetime import datetime

from flask import Blueprint, jsonify, request, session, current_app

from models import Seat, SeatStatus
from seats import sweep_expired_holds, hold_seats, release_seats
from analytics import Event, log_event, has_event, CLIENT_LOGGABLE_EVENTS
from extensions import csrf, limiter

api_bp = Blueprint("api", __name__, url_prefix="/api")
csrf.exempt(api_bp)

MAX_SEATS_PER_SESSION = 10


def _adjacency_ok(seat, sid):
    """When REQUIRE_ADJACENT_SEATS is on, this session's held seats within the
    same section/row (including the candidate seat) must form one unbroken
    run of seat numbers, so nobody ends up splitting a row with a stray
    empty seat between two different parties."""
    held = Seat.query.filter(
        Seat.status == SeatStatus.HELD,
        Seat.held_by_session == sid,
        Seat.section == seat.section,
        Seat.row_label == seat.row_label,
    ).all()
    numbers = sorted({s.seat_number for s in held} | {seat.seat_number})
    return numbers[-1] - numbers[0] + 1 == len(numbers)


def _serialize_seats(sid):
    # Disabled seats (not yet released - see seat_config.FIRST_BATCH_LABELS)
    # are omitted entirely from the public seat list, not just shown as
    # unavailable, so visitors never see hints of sections/rows that
    # haven't opened yet. The admin's own seat list (routes_admin.py) is a
    # separate query and still includes them, since staff need to see and
    # enable them later.
    seats = (
        Seat.query.filter(Seat.status != SeatStatus.DISABLED)
        .order_by(Seat.section, Seat.row_label, Seat.seat_number)
        .all()
    )
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

    if current_app.config["REQUIRE_ADJACENT_SEATS"]:
        seat = Seat.query.get(seat_id)
        if seat is None:
            return jsonify({"ok": False, "error": "Seat not found."}), 404
        if not _adjacency_ok(seat, sid):
            return jsonify({
                "ok": False,
                "error": "For now, please pick seats next to your other selected seat(s) in the same row.",
                "seats": _serialize_seats(sid),
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
