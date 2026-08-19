"""Apple Wallet / Google Wallet passes via the third-party WalletWallet.dev
API. This is entirely optional: if WALLETWALLET_API_KEY isn't set, or the
service errors out, callers just get None back and the booking/email flow
carries on unaffected - the QR code and PDF ticket never depend on this.
"""

import base64
from datetime import datetime

import requests
from flask import current_app


def create_wallet_pass(seat, booking, cfg, checkin_url):
    """Build one wallet pass for a single seat (not the whole booking) -
    each seat has its own barcode so a group can be checked in separately."""
    api_key = cfg.get("WALLETWALLET_API_KEY")
    if not api_key:
        return None

    expiration_days = None
    try:
        event_dt = datetime.fromisoformat(cfg["EVENT_DATETIME_ISO"])
        expiration_days = max((event_dt - datetime.utcnow()).days + 1, 1)
    except Exception:
        pass

    payload = {
        "barcodeValue": checkin_url,
        "barcodeFormat": "QR",
        "logoText": "Light Up the Sky",
        "organizationName": cfg["FESTIVAL_NAME"][:64],
        "description": f"{cfg['EVENT_NAME']} ticket ({booking.reference} - seat {seat.label})",
        "colorPreset": "red",
        "headerFields": [{"label": "REF", "value": booking.reference}],
        "primaryFields": [{"label": "SEAT", "value": seat.label}],
        "secondaryFields": [
            {"label": "DATE", "value": cfg["EVENT_DATE_TEXT"]},
            {"label": "TIME", "value": cfg["EVENT_TIME_TEXT"]},
        ],
        "backFields": [
            {"label": "Location", "value": cfg["EVENT_LOCATION"]},
            {"label": "Attendee", "value": booking.attendee_name},
            {"label": "Amount paid (whole booking)", "value": f"EUR {booking.amount_total_eur:.2f}"},
        ],
    }
    if expiration_days:
        payload["expirationDays"] = expiration_days

    try:
        resp = requests.post(
            cfg["WALLETWALLET_API_URL"],
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        current_app.logger.exception(
            "WalletWallet pass creation failed for booking %s seat %s", booking.reference, seat.label
        )
        return None


def revoke_wallet_pass(serial, cfg):
    api_key = cfg.get("WALLETWALLET_API_KEY")
    if not api_key or not serial:
        return
    try:
        requests.delete(
            f"{cfg['WALLETWALLET_API_URL']}/{serial}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
    except Exception:
        current_app.logger.exception("WalletWallet pass revocation failed for serial %s", serial)


def decode_apple_pass(wallet_apple_pass_b64):
    return base64.b64decode(wallet_apple_pass_b64)
