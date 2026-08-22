# Technical Documentation - Fireworks Seat Booking

This is the developer-facing reference for the "Light Up the Sky" seat
booking app: architecture, data model, request flows, configuration, and a
troubleshooting playbook built from real issues hit during development and
deployment. For a non-technical guide to running the system day-to-day, see
[USER_GUIDE.md](USER_GUIDE.md).

## 1. Stack

- **Backend**: Python 3.12, Flask, SQLAlchemy (Flask-SQLAlchemy), Flask-Login
  (admin sessions), Flask-WTF (CSRF), Flask-Limiter (rate limiting)
- **Database**: PostgreSQL in production (PythonAnywhere managed Postgres),
  SQLite for local development - same code, driven by `DATABASE_URL`
- **Payments**: Stripe Checkout (hosted payment page) + webhooks
- **Email**: SMTP via Microsoft 365 / Outlook (`smtplib`, no third-party
  email API)
- **Tickets**: `qrcode` + Pillow (QR codes), `fpdf2` (PDF generation)
- **Wallet passes**: [WalletWallet.dev](https://www.walletwallet.dev) (third
  party - see README "Apple Wallet / Google Wallet" section)
- **In-browser QR scanning**: [jsQR](https://github.com/cozmo/jsQR), vendored
  locally at `static/js/jsqr.min.js` (no CDN dependency)
- **Hosting**: PythonAnywhere (WSGI), custom domain `festa26.szpm.mt`
  proxied through Cloudflare
- **Repo**: <https://github.com/szpm102/Festa26BookingApp>

## 2. Project structure

```
app.py              Flask app factory / entry point, loads config.env/.env
config.py            All configuration (env-var driven, see section 6)
extensions.py        Shared Flask extension instances (db, login, csrf, limiter)
models.py            Seat / Booking / Admin tables + status enums
seats.py             Atomic seat state transitions (hold/release/book/disable)
seat_config.py        The real 300-seat layout (5 sections x 60 seats) - see section 3
payments.py          Stripe Checkout session creation/retrieval
webhooks.py          Stripe webhook handler - the only place bookings become "paid"
emailer.py           Confirmation emails (client + team), builds QR/PDF/wallet attachments
ticketing.py         QR code (PNG) and PDF ticket generation
wallet.py            WalletWallet.dev API client (create/revoke passes)
reports.py           Excel (.xlsx) booking export
utils.py             Small helpers (booking reference generator)
routes_public.py     Public booking page + checkout/success/cancel/ticket download
routes_api.py        JSON API the booking page polls (seat list, hold, release)
routes_admin.py      Admin login, dashboard, seat management, cash bookings,
                     check-in, admin-account management, report, QR scanner page
seed.py              CLI: create seats + first admin account
templates/           Jinja templates (public site + admin + emails)
static/               CSS, JS (seat map, admin dashboard, QR scanner), images,
                     favicon, web app manifest
docs/                 This file + USER_GUIDE.md
```

## 3. Data model

### Seating plan (`seat_config.py`)

The real, finalised layout (source: `SeatingPlanStructure.xlsx`) - 5 sections
placed side by side across the closed-off street (`A`-`E`), each 10 seats
wide and 6 rows deep (60 seats/section = 300 total), with an 80cm gap
between adjacent sections. `SEAT_LAYOUT` generates one entry per seat with:

- `label` - e.g. `A23` (section + a running 1-60 number within it, matching
  the spreadsheet's own numbering exactly)
- `section` - `A`-`E`
- `row` - `1`-`6`, depth within that section (derived from the running
  number: `row = ((n-1) // 10) + 1`)
- `number` - `1`-`10`, position within that row (`((n-1) % 10) + 1`)

Only part of the plan opens for booking at first: `FIRST_BATCH_LABELS`
(sections A and B, minus their back row - 100 seats) seed as `available`;
everything else (200 seats) seeds as `disabled` and gets opened later from
the admin dashboard (select seats on the map -> "Enable selected") as the
committee confirms more of the road, no code change needed.

`seed.py` is safe to re-run at any point to apply a corrected layout: it
matches existing rows by `label` and always corrects `section`/`row`/
`number` (harmless - never touches a booking), but only sets a seat's
open/closed status if that seat is still untouched (`available`) - it never
overrides a seat that's already booked, held, or one an admin has
deliberately disabled/enabled by hand.

Two places order seats by `(section, row_label, seat_number)` rather than
just `(row_label, seat_number)` - `routes_admin.py`'s `/api/seats` and
`routes_api.py`'s `_serialize_seats` - since row numbers alone (`1`-`6`)
repeat across every section and would otherwise interleave sections when
sorted. The seat map rendering (both the public SVG in `booking.js` and the
admin's plain grid in `admin.js`) groups by section first, then by row
within it, drawing the 5 blocks side by side with a gap between them.

### `Seat` (table `seats`)
One row per physical seat (300 total). Key fields:

| Field | Notes |
|---|---|
| `label` | Unique, e.g. `A12` - shown to the public, must match the physical venue |
| `status` | `available` / `held` / `booked` / `disabled` (see state machine below) |
| `held_by_session` / `held_until` | Set while a visitor is mid-checkout |
| `booking_id` | FK to `Booking`, set once permanently booked |
| `checkin_token` | Per-**seat** unguessable token (32-byte, `secrets.token_urlsafe`) - the QR code encodes a URL containing this |
| `checked_in_at` | Null until scanned at the door |
| `wallet_serial` / `wallet_google_url` / `wallet_apple_pass_b64` | Cached WalletWallet.dev pass data for this seat, so re-downloads don't depend on that service staying up |

### `Booking` (table `bookings`)
One row per checkout (can cover multiple seats). Key fields:

| Field | Notes |
|---|---|
| `reference` | Short human-shareable code, e.g. `FW-AB12CD` |
| `payment_method` | `stripe` / `cash` |
| `payment_status` | `pending` / `paid` / `cancelled` |
| `stripe_session_id` | Used as the idempotency key in the webhook (see section 4.2) |
| `access_token` | Lets a guest re-download their combined PDF later at `/ticket/<token>`, without logging in |
| `seats` | One-to-many relationship to `Seat` |

### `Admin` (table `admins`)
`is_superadmin` gates: resetting a seat's check-in status, and managing other
admin accounts. Regular admins can do everything else (seat map, cash
bookings, check-in, reports, resending confirmation emails).

### Why per-seat, not per-booking, tickets/check-in?

A group that books 4 seats together often arrives in separate waves. If
check-in were tracked once per *booking*, the second wave scanning the same
QR would incorrectly show "already scanned". Every seat has its own QR code,
its own wallet pass, and its own independent `checked_in_at` - the PDF is
still one combined document (one page per seat) so the guest only has one
file to keep.

## 4. Key flows

### 4.1 Seat holding (concurrency)

Every seat mutation in `seats.py` is a single atomic
`UPDATE ... WHERE status = X` (checked via `rowcount`), never a
read-then-write. Two visitors clicking the same seat at the same instant can
never both succeed - the database resolves the race regardless of how many
app workers are running. `sweep_expired_holds()` runs on most read/write
endpoints to release holds whose `held_until` has passed, before serving the
seat map.

### 4.2 Online payment (Stripe)

1. Visitor selects seats -> `POST /api/hold` marks them `held` for their
   session (`SEAT_HOLD_MINUTES`, default 7).
2. `POST /booking/checkout` creates a Stripe Checkout Session
   (`payments.create_checkout_session`) with `success_url`/`cancel_url`
   built from `BASE_URL` (**must** be a full `https://...` URL - see section
   9 troubleshooting) and seat IDs stashed in `metadata`.
3. Stripe's hosted page handles the actual card payment.
4. **Only** on `checkout.session.completed` does Stripe POST to
   `/stripe/webhook` (`webhooks.py`). The handler:
   - Verifies the signature with `STRIPE_WEBHOOK_SECRET`.
   - Checks `Booking.stripe_session_id` for idempotency - **if a booking
     already exists for this session, it returns immediately without
     resending email**. This means once a booking is created, a Stripe
     retry can never re-trigger the email step - see section 9 for why this
     matters.
   - Creates the `Booking` row, calls `confirm_seats_for_booking()` (moves
     seats `held`/`available` -> `booked`), then calls
     `emailer.send_booking_confirmation()`.
5. If the visitor cancels/declines on Stripe's page, they land on
   `/booking/cancelled`, which immediately releases that session's held
   seats. If they just abandon the tab, the hold expires naturally via
   `sweep_expired_holds()`. **No webhook event is needed for the failure
   path** - it's handled entirely by the redirect + the hold's natural
   expiry.

### 4.3 Cash payment (admin)

`POST /admin/api/bookings/cash` (routes_admin.py) does the same
booking-creation + `confirm_seats_for_booking()` + email steps synchronously,
in the request itself - no Stripe/webhook involved, `payment_status` is set
to `paid` directly.

### 4.4 Email sending

`emailer.send_booking_confirmation(booking)`:
1. For each seat (sorted by label): generates its QR PNG
   (`ticketing.build_qr_png`, encoding `{BASE_URL}/admin/checkin/{seat's
   token}`), requests a WalletWallet.dev pass (`wallet.create_wallet_pass` -
   returns `None` on any failure, non-fatal), and adds it as an inline image
   / `.pkpass` attachment.
2. Builds one combined PDF (`ticketing.build_ticket_pdf`, one page per seat).
3. Sends the client email (HTML + plain-text alternative, PDF + `.pkpass`
   attachments), then the team notification (if `TEAM_NOTIFY_EMAILS` is set)
   - no attachments on the team email.
4. `_send()` only returns `False` and logs a warning if SMTP itself fails
   (missing credentials or a connection/auth error) - it does not raise.

**Reliability note (fixed 2026-08-20):** the wallet-pass step used to call
`wallet.decode_apple_pass(seat.wallet_apple_pass_b64)` unconditionally once
`wallet_result` was truthy. If WalletWallet.dev returned a 200 response
without an `applePass` field for any seat (more likely across the multiple
rapid calls a multi-seat booking makes than a single-seat one),
`base64.b64decode(None)` raised, aborting the **entire** function before
either email was sent - and since the booking was already committed as
paid, a Stripe retry just hit the idempotency guard and never tried again.
Fixed by: skipping (and logging) a malformed wallet pass instead of raising,
and wrapping the `emailer.send_booking_confirmation()` call sites in
`webhooks.py` and `routes_admin.py` so an unexpected email failure can never
again crash the booking/webhook flow itself. An admin-facing **"Resend
confirmation email"** button (`POST
/admin/booking/<reference>/resend-email`) is the manual recovery path for
any booking that still doesn't get its email for some other reason.

### 4.5 Check-in

Each seat's QR encodes `/admin/checkin/<seat's checkin_token>`. Opening it
(`@login_required` - staff must be logged in) shows that seat's status with
a "Mark Checked In" button; scanning an already-checked-in seat shows a red
warning instead, and the button disappears once used. Two ways to open that
page:
- **Phone's native camera app** (no special software - it's just a URL).
- **In-app scanner** at `/admin/scan` (`templates/admin/scan.html` +
  `static/js/scan.js`), using `getUserMedia` + the vendored `jsQR` library to
  decode frames client-side and navigate to the decoded URL once it matches
  `/admin/checkin/` in its path (`looksLikeCheckinLink()`).

`/admin/booking/<reference>` (manual lookup by reference, or scanning
resolves a booking-reference-shaped code the same way) shows every seat in
that booking with its own status/action - useful for checking a whole group
in from one screen.

Only a superadmin can `POST /admin/checkin/<token>/reset` (also enforced
server-side, not just hidden in the UI).

### 4.6 Marketing funnel analytics

A self-hosted, no-third-party-service funnel log (`analytics.py`, table
`analytics_events`) for the one marketing question this project actually
needs answered: how many site visits turn into a booking. No personal data
- just the same per-browser session id already used for seat holds, an
event type, and a timestamp.

Events logged, in funnel order:
1. `page_view` - every `GET /` (`routes_public.index`).
2. `book_cta_click` - clicking the homepage's "Book Your Seat" button.
   Client-side only (it's just an anchor scroll, no server request), so
   `static/js/hero.js` fires a fire-and-forget `POST /api/track` for it.
   That endpoint only accepts event types in `CLIENT_LOGGABLE_EVENTS` -
   it can't be used to log arbitrary event types.
3. `seat_selected` - the first successful seat hold in a session
   (`routes_api.hold`), deduped via `analytics.has_event()` so selecting
   multiple seats doesn't inflate the count.
4. `checkout_started` - a Stripe Checkout Session was successfully created
   (`routes_public.checkout`).
5. `booking_completed_online` - the Stripe webhook actually confirmed the
   booking (`webhooks._fulfil_checkout`), tagged with the *browsing*
   session id carried through in the Checkout Session's `metadata.session_id`
   (not the webhook request's own session, which doesn't exist - Stripe
   calls this endpoint server-to-server).
6. `booking_completed_cash` - an admin-entered cash booking
   (`routes_admin.api_book_cash`) - logged without a session id, since it
   didn't originate from a browsing session to correlate against.

`analytics.funnel_summary()` turns these into counts plus step-to-step
conversion rates; `analytics.daily_breakdown()` buckets visits/bookings by
calendar day. Both back the admin page at `/admin/analytics` (optional
`?days=7`/`?days=30` to window the query) and its Excel export at
`/admin/analytics.xlsx` (`reports.build_analytics_report`).

## 5. Front-end notes

- **Seat map**: polls `GET /api/seats` every 4s; clicking a seat calls
  `POST /api/hold` immediately so it can't be grabbed elsewhere while the
  visitor decides.
- **Admin dashboard**: `static/js/admin.js` drives the same seat map plus
  disable/enable/cash-booking actions via `/admin/api/seats/*`.
- **PWA**: `static/manifest.webmanifest` + icons in `static/img/` let staff
  "Add to Home Screen" on their phone for an app-like experience (no browser
  chrome) - handy for the scan page on the event day. Declared in
  `templates/base.html`'s `<head>`.

## 6. Configuration reference

All of `config.py` is env-var driven via a `_env(key, default)` helper that
also treats a *blank* value (`KEY=` with nothing after it) as "use the
default", not just a missing key. Loaded from `config.env` (or `.env`) via
`python-dotenv` in `app.py`. See `.env.example` for a template.

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | placeholder | **Must** be a long random value in production (Flask session signing) |
| `DATABASE_URL` | local SQLite | Postgres in production; `postgres://` is auto-rewritten to `postgresql://` |
| `TOTAL_SEATS` | 300 | |
| `SEAT_PRICE_EUR` | 4.00 | |
| `SEAT_HOLD_MINUTES` | 7 | |
| `ADMIN_CONTACT_EMAIL` | admin@szpm.mt | Shown in the privacy notice text |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | placeholders | Used only by `seed.py` to create the first superadmin - change before running for real |
| `WALLETWALLET_API_KEY` | blank (disables wallet passes) | |
| `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET` | blank | Must match the **same** Stripe mode (test/live) and the **same specific webhook endpoint's** signing secret - see section 9 |
| `SMTP_HOST` | smtp.office365.com | |
| `SMTP_PORT` | 587 | |
| `SMTP_USER` / `SMTP_PASSWORD` | blank | An M365 mailbox + **App Password** (not the normal login password) - see README "Email sending" |
| `MAIL_FROM_NAME` | Festa Munxar - Fireworks Booking | |
| `TEAM_NOTIFY_EMAILS` | blank (disables team notification) | Comma-separated |
| `BASE_URL` | `http://127.0.0.1:5000` | **Must** be the full public URL including `https://` once deployed - used to build Stripe redirect URLs, QR/check-in links, and to decide `SESSION_COOKIE_SECURE` |

Non-env-var settings edited directly in `config.py`: `EVENT_*` / `FESTIVAL_*`
/ `PROGRAMME` (event details and the wider festa week's cross-promotion),
`SITE_TITLE` (browser tab title, separate from `EVENT_NAME` which is the
on-page/email event name), `REFUND_POLICY_TEXT`, `PRIVACY_NOTICE_TEXT`.

## 7. Security measures

See README "Security" section for the full list (rate limiting, security
headers, secure/httponly/samesite cookies, CSRF, debug-off-by-default,
hashed passwords, unguessable tokens). Two additions since that was last
written:
- `SQLALCHEMY_ENGINE_OPTIONS` sets `pool_pre_ping=True` and
  `pool_recycle=280` - see section 9's "SSL SYSCALL error" entry.
- Flask-Limiter's storage is in-memory: fine for PythonAnywhere's single
  always-on process, but would need Redis if ever scaled to multiple worker
  processes (state wouldn't be shared between them otherwise).

## 8. Deployment (PythonAnywhere)

The live app runs on PythonAnywhere, manually configured (not one of their
one-click frameworks), with a custom domain `festa26.szpm.mt` proxied
through Cloudflare.

- **Code**: `git pull` inside `~/Festa26BookingApp` after every push to
  `main`, then **Web tab -> Reload** (config/code changes only take effect
  after a reload - this is a common thing to forget).
- **Config**: `config.env` lives directly in the project folder on the
  server (not PythonAnywhere's separate "Environment variables" UI feature)
  - edit it with `nano ~/Festa26BookingApp/config.env` in a Bash console.
  It is **not** committed to git (`.gitignore`) and must be populated
  independently on the server; it is a *different file* from your local
  `config.env`.
- **Database**: PythonAnywhere's managed Postgres, on their private network
  with a non-standard port - the connection string needs host, the custom
  port, and the exact database name (create it with `CREATE DATABASE
  <name>;` in their Postgres console first if it doesn't exist yet).
- **First deploy / schema changes**: `db.create_all()` runs automatically in
  `create_app()`, so new tables appear on the next request after a reload -
  there's no migration tool set up (fine pre-launch; worth adding, e.g.
  Alembic, before this holds long-lived production data across schema
  changes).
- **Custom domain via Cloudflare**: PythonAnywhere's own domain-verification
  check can show a false-positive "There is a problem with your domain name
  configuration" warning because Cloudflare's proxy hides the true CNAME
  target from their verifier. Confirm independently with `curl`/`dig` that
  the domain resolves and serves traffic correctly before treating that
  warning as blocking.
- **Stripe webhook**: must be registered **for the exact production URL**
  (`https://festa26.szpm.mt/stripe/webhook`) in the Stripe Dashboard ->
  Developers -> Webhooks (this is separate from and easy to confuse with a
  local `stripe listen` test endpoint, which only ever points at
  `127.0.0.1` and can't receive anything from a real server) - see section
  9.

## 9. Troubleshooting playbook

Real issues hit during this project's development/deployment, and their
root cause + fix, in case they recur:

**Stripe error "Not a valid URL" on checkout.**
`BASE_URL` in `config.env` is missing the `https://` scheme (e.g. set to
just `festa26.szpm.mt`). Stripe's `success_url`/`cancel_url` require a full
absolute URL. Fix: `BASE_URL=https://festa26.szpm.mt`, save, reload the web
app.

**Payment succeeds in Stripe but the seat never becomes booked / no email
ever arrives.**
The webhook never reached or was rejected by the app. Check Stripe
Dashboard -> Developers -> Webhooks:
- No endpoint for the production URL at all -> it was never registered;
  create one for `https://festa26.szpm.mt/stripe/webhook`, subscribed to
  `checkout.session.completed`.
- Endpoint exists but shows `400`/signature errors on delivery attempts ->
  `STRIPE_WEBHOOK_SECRET` in `config.env` doesn't match *this specific
  endpoint's* signing secret (very easy to leave a local `stripe listen`
  secret in place by mistake - each endpoint, including each `stripe
  listen` session, has its own secret).
- Fix in both cases: paste the correct signing secret into `config.env`,
  reload. Use Stripe's "Send test webhook" button to confirm a `200` without
  needing a full purchase.

**Intermittent `sqlalchemy.exc.OperationalError: ... SSL SYSCALL error: EOF
detected` on random requests (e.g. `/api/seats`).**
The managed Postgres connection was closed after a period of inactivity
(idle timeout, either from Postgres itself or a network path in between),
but SQLAlchemy's pool tried to reuse it anyway. Fixed via
`SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}`
in `config.py` (validates/refreshes connections transparently). If this
recurs with a different symptom, lowering `pool_recycle` further is the
next lever.

**A booking confirms (seat goes "Booked") but no email arrives, and it only
happens for multi-seat bookings.**
See section 4.4 - this was the exact WalletWallet.dev `applePass`-missing
bug, now fixed. If a similar silent-email-failure pattern appears again in
the error log (search for the booking's timestamp/reference), the fix
pattern is: never let anything in the per-seat attachment-building loop
raise past a `try/except` that just logs and skips that one seat's extra,
and always wrap the *outer* `emailer.send_booking_confirmation()` call so a
failure there can't crash the request that already committed the
booking/seats as paid. Use the admin "Resend confirmation email" button to
recover any specific stuck booking without needing a code fix first.

**SMTP auth failures (`535 5.7.3 Authentication unsuccessful`) from
Microsoft 365.**
See README "Email sending" section - almost always SMTP AUTH disabled for
that mailbox, or using the normal password instead of an App Password, or a
tenant-wide Conditional Access policy blocking basic auth entirely.

**Local dev server picks up stale/wrong config (e.g. wrong Stripe key).**
Almost always a leftover Flask dev server process from an earlier run still
bound to the port, or a shell that silently didn't activate the venv (used
system Python instead). Kill stray `python.exe` processes for this project
path and always invoke the venv's python by its full path
(`./venv/Scripts/python.exe`) rather than relying on `activate` succeeding
silently.

## 10. Known open items

- No database migration tool is set up (fine pre-launch; add one, e.g.
  Alembic, before this holds long-lived production data across schema
  changes).
- Flask-Limiter's in-memory storage would need to move to Redis if ever
  scaled beyond a single always-on process.
