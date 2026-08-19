"""Core seat state-machine helpers. All mutations use atomic UPDATE ... WHERE
status = X statements (checked via rowcount) so concurrent requests from
different users can never both succeed in grabbing the same seat, regardless
of the underlying database backend.
"""

from datetime import datetime
from extensions import db
from models import Seat, SeatStatus


def sweep_expired_holds():
    """Release any HELD seats whose hold has expired back to AVAILABLE."""
    now = datetime.utcnow()
    expired = Seat.query.filter(
        Seat.status == SeatStatus.HELD, Seat.held_until < now
    )
    expired.update(
        {
            Seat.status: SeatStatus.AVAILABLE,
            Seat.held_by_session: None,
            Seat.held_until: None,
        },
        synchronize_session=False,
    )
    db.session.commit()


def hold_seats(seat_ids, session_id, hold_until):
    """Try to hold the given seat ids for session_id. Returns (ok_ids, failed_ids)."""
    ok_ids = []
    failed_ids = []
    for seat_id in seat_ids:
        result = (
            Seat.query.filter(
                Seat.id == seat_id, Seat.status == SeatStatus.AVAILABLE
            ).update(
                {
                    Seat.status: SeatStatus.HELD,
                    Seat.held_by_session: session_id,
                    Seat.held_until: hold_until,
                },
                synchronize_session=False,
            )
        )
        if result == 1:
            ok_ids.append(seat_id)
        else:
            failed_ids.append(seat_id)
    db.session.commit()
    return ok_ids, failed_ids


def release_seats(seat_ids, session_id=None):
    """Release held seats back to available. If session_id given, only release
    seats held by that session (prevents releasing someone else's hold)."""
    query = Seat.query.filter(Seat.id.in_(seat_ids), Seat.status == SeatStatus.HELD)
    if session_id:
        query = query.filter(Seat.held_by_session == session_id)
    query.update(
        {
            Seat.status: SeatStatus.AVAILABLE,
            Seat.held_by_session: None,
            Seat.held_until: None,
        },
        synchronize_session=False,
    )
    db.session.commit()


def confirm_seats_for_booking(seat_ids, booking_id, from_statuses):
    """Move seats into BOOKED state and attach them to a booking. Only seats
    currently in one of from_statuses are touched. Returns number confirmed."""
    result = (
        Seat.query.filter(Seat.id.in_(seat_ids), Seat.status.in_(from_statuses)).update(
            {
                Seat.status: SeatStatus.BOOKED,
                Seat.held_by_session: None,
                Seat.held_until: None,
                Seat.booking_id: booking_id,
            },
            synchronize_session=False,
        )
    )
    db.session.commit()
    return result


def disable_seats(seat_ids):
    """Admin override: block a seat from sale even if it's currently held by
    someone mid-checkout (their hold is discarded)."""
    result = (
        Seat.query.filter(
            Seat.id.in_(seat_ids),
            Seat.status.in_([SeatStatus.AVAILABLE, SeatStatus.HELD]),
        ).update(
            {
                Seat.status: SeatStatus.DISABLED,
                Seat.held_by_session: None,
                Seat.held_until: None,
            },
            synchronize_session=False,
        )
    )
    db.session.commit()
    return result


def enable_seats(seat_ids):
    result = (
        Seat.query.filter(
            Seat.id.in_(seat_ids), Seat.status == SeatStatus.DISABLED
        ).update({Seat.status: SeatStatus.AVAILABLE}, synchronize_session=False)
    )
    db.session.commit()
    return result


def cancel_booking(booking):
    """Admin action: free up a booking's seats back to available (e.g. refund)."""
    seat_ids = [s.id for s in booking.seats]
    Seat.query.filter(Seat.id.in_(seat_ids)).update(
        {
            Seat.status: SeatStatus.AVAILABLE,
            Seat.held_by_session: None,
            Seat.held_until: None,
            Seat.booking_id: None,
        },
        synchronize_session=False,
    )
    db.session.commit()
