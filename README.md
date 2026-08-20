# Fireworks Seat Booking - "Light Up the Sky", Munxar 2026

Web app for booking the 300 viewing seats for the Festa Munxar fireworks display
(Andrijiet Street, Munxar, Sat 12 Sept 2026, 21:30). Seats are held live while a
visitor is checking out, paid via Stripe, and permanently marked booked once
payment succeeds. Admins can also book a seat manually for a cash payment, or
disable a seat entirely (e.g. reserved seating).

## Documentation

- **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** - for the SZPM committee and
  door staff: logging in, cash bookings, checking guests in, reports,
  managing admin accounts. No coding knowledge needed.
- **[docs/TECHNICAL.md](docs/TECHNICAL.md)** - architecture, data model,
  request flows, configuration reference, and a troubleshooting playbook
  built from real deployment issues.

The rest of this README is a quicker technical reference; the two docs
above go into more depth on each side.

## How it works

- **Seat states**: `available` -> `held` (temporary, ~7 min, while someone is
  paying) -> `booked` (permanent) or back to `available` if they abandon
  checkout. Admins can also mark a seat `disabled` (blocked from public
  booking, e.g. given away for cash or reserved).
- **Live greying-out**: the booking page polls the server every 4 seconds and
  seats update for everyone; clicking a seat holds it immediately for that
  visitor so nobody else can grab it while they pay.
- **Payments**: Stripe Checkout handles card payments; a webhook confirms the
  booking and marks the seats permanently booked only once Stripe confirms
  payment. Admins can also register a booking directly (cash payment) from the
  dashboard, which books seats immediately without going through Stripe.
- **Emails**: on every confirmed booking (online or cash), a confirmation email
  goes to the customer and a notification goes to the team address(es) in
  `TEAM_NOTIFY_EMAILS`.
- **Reports**: `Admin > Download report (.xlsx)` exports every booking (name,
  email, seats, amount, payment method/status, check-in time).
- **Tickets & check-in are per seat, not per booking**: a booking for several
  seats gets one combined PDF, but each seat inside it has its own QR code,
  its own wallet pass, and its own independent check-in status. That means a
  group that bought seats together but arrives in separate waves can each be
  checked in on arrival, without the second wave triggering a false
  "duplicate ticket" warning. The PDF (all seats) is attached to the
  confirmation email and re-downloadable anytime at `/ticket/<booking's
  access token>`. Each seat's QR encodes a link to `/admin/checkin/<that
  seat's token>` - an admin scans it with their **phone's normal camera app**
  (no special app needed), which opens that link, asks them to log in if
  needed, and shows just that seat with a "Mark Checked In" button (plus a
  read-only summary of the other seats in the same booking, for context).
  Admins can also type a booking reference on the dashboard instead of
  scanning, which opens an overview of every seat in that booking with its
  own status and check-in button - handy for checking a whole group in
  manually from one screen.
- **Check-in status is visible at a glance**: scanning a fresh seat's ticket
  shows a green "CHECKED IN" banner; scanning that same seat again shows a
  red "ALREADY SCANNED" warning instead (possible duplicate/shared ticket) -
  the "Mark Checked In" button disappears once used, so it can't be re-run by
  accident. Other seats in the same booking are unaffected either way.
- **Only a superadmin can reset a check-in** (e.g. to undo test scans before
  the event). Regular admin accounts see the same check-in page but no reset
  button, and a direct attempt to reset is rejected server-side too. See
  "Admin accounts" below for how to create superadmin vs regular accounts.

## Admin accounts

`python seed.py` creates one **superadmin** account from `ADMIN_EMAIL` /
`ADMIN_PASSWORD` - superadmins can do everything, including resetting a
ticket's check-in status and managing other admin accounts. **Change
`ADMIN_PASSWORD` to a real password before running `seed.py` for real** - it
ships as an obvious placeholder.

To add extra accounts for door staff day-to-day, no server access needed:
log in as a superadmin, click **"Manage admins"** on the dashboard, and
create new admin accounts (with or without superadmin rights) directly from
the browser. Removing an account works the same way - you can't remove your
own account or the last remaining superadmin.

The command-line route still works too, useful for the very first account or
scripted setups:

```bash
python seed.py add-admin door-staff@szpm.mt somepassword
```

Add `--superadmin` at the end to give that account full rights too.

## IMPORTANT - seat layout is a placeholder

No real venue seating chart was available yet, so `seat_config.py` currently
generates a generic 5-row x 60-seat grid (rows A-E), single "Main" section =
300 seats. **Send over the actual seating plan for Andrijiet Street**
(sections, rows, numbering) and this file should be updated to match before
going live - seat labels shown to the public should match what's physically
marked/painted at the venue.

## Local setup

```bash
cd fireworks-booking
python -m venv venv
venv\Scripts\activate          # on Windows
pip install -r requirements.txt
copy .env.example .env         # then fill in real values in .env
python seed.py                 # creates the 300 seats + admin account
python app.py                  # runs on http://127.0.0.1:5000
```

Admin dashboard: http://127.0.0.1:5000/admin/login (credentials from
`ADMIN_EMAIL` / `ADMIN_PASSWORD`).

If you already have a `bookings.db` from before the ticketing feature was
added and see database errors, delete it and re-run `python seed.py` - there's
no real booking data to lose before the site goes live, and there's no
migration tool set up yet (fine for now; worth adding before this holds real
production data long-term).

Without `.env` values for Stripe/SMTP, the site still runs: seat
selection/holding works, but checkout and emails will show a clear error until
those are configured.

## Deploying (Render.com example)

1. Push this folder to a git repo (GitHub/GitLab).
2. On Render: **New > Web Service**, connect the repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
3. Add a Render **PostgreSQL** database, copy its "Internal Database URL" into
   the `DATABASE_URL` environment variable on the web service.
4. Add all the other variables from `.env.example` as environment variables in
   the Render dashboard (Stripe keys, SMTP, `ADMIN_EMAIL`/`ADMIN_PASSWORD`,
   `TEAM_NOTIFY_EMAILS`, and `BASE_URL` set to the `https://...onrender.com`
   URL Render gives you).
5. After the first deploy, open a **Shell** on the service and run
   `python seed.py` once to create the seats and admin account.
6. In the Stripe dashboard, add a webhook endpoint pointing to
   `https://<your-app>.onrender.com/stripe/webhook`, subscribed to
   `checkout.session.completed`, and copy its signing secret into
   `STRIPE_WEBHOOK_SECRET`.

(PythonAnywhere or Azure App Service work the same way in principle: install
requirements, set the same environment variables, point the WSGI entry at
`app:app`, run `seed.py` once, and register the Stripe webhook with that
platform's public URL. PythonAnywhere's free tier does not allow outbound
Stripe webhook calls on some plans - check that before committing to it.)

## Email sending (Microsoft 365 / Outlook)

The app sends mail via SMTP (`smtp.office365.com:587`) using a real mailbox.
Microsoft 365 requires an **App Password** (or "SMTP AUTH" enabled for that
mailbox) rather than the normal login password - set it up under that
account's Outlook security settings, then put the mailbox address and app
password into `SMTP_USER` / `SMTP_PASSWORD`. If your tenant has SMTP AUTH
disabled organisation-wide, ask IT to enable it for this one mailbox, or swap
to a transactional email provider later (the sending code is isolated in
`emailer.py`).

**Live-tested and confirmed failing with `535 5.7.3 Authentication
unsuccessful`** - Microsoft is rejecting the SMTP login itself, before the app
even gets a chance to send anything. Ask IT to check, in order of likelihood:

1. **SMTP AUTH isn't enabled for this mailbox.** Microsoft 365 disables this
   by default now - an admin needs to turn it on per-mailbox (Exchange Admin
   Center -> that mailbox -> "Manage email apps" -> enable "Authenticated
   SMTP", or via PowerShell: `Set-CASMailbox -Identity <mailbox> -SmtpClientAuthenticationDisabled $false`).
2. **The password is the normal account password, not an App Password.** If
   MFA is on for this mailbox (likely), SMTP AUTH needs a dedicated App
   Password instead.
3. **A tenant-wide Security Defaults / Conditional Access policy is blocking
   legacy ("basic") authentication entirely**, regardless of the mailbox
   setting - this needs an explicit exception from whoever manages Conditional
   Access for the tenant.

### Reducing the chance of landing in spam

Once SMTP auth itself is fixed, a few things affect whether the confirmation
email lands in the inbox vs spam:

- **Already handled in the code**: every email now includes proper `Date` and
  `Message-ID` headers, and is sent as true `multipart/alternative` (a
  plain-text version alongside the HTML one) - missing either is a well-known
  spam signal, and plenty of transactional mail gets this wrong.
- **Worth asking IT to check on the Microsoft 365 / DNS side**, since these
  are outside what the app itself controls:
  - **SPF** for the sending domain includes Microsoft's senders (usually
    already true by default for a domain hosted on M365 - `include:spf.protection.outlook.com`).
  - **DKIM signing is enabled for the actual sending domain** (Exchange admin
    center -> Mail flow -> DKIM). M365 opportunistically signs the
    `*.onmicrosoft.com` domain, but a custom domain (e.g. `szpm.mt`) needs DKIM
    explicitly turned on and its CNAME records published - this meaningfully
    helps deliverability.
  - **A DMARC record exists** for the domain (a DNS TXT record) - even a
    permissive `p=none` policy helps mailbox providers trust the domain more.
  - If this mailbox rarely sends mail, its first few sends may land in spam
    regardless (a reputation/warm-up effect) - sending a few real bookings in
    the days before the event, rather than only on the day itself, helps.

## Apple Wallet / Google Wallet

Real "Add to Apple Wallet" / "Add to Google Wallet" buttons are wired up via
[WalletWallet.dev](https://www.walletwallet.dev) - a third-party service that
holds its own Apple/Google Wallet developer credentials, so **you don't need
an Apple Developer account or a Google Wallet issuer account**. Sign up there,
create an API key, and set it as `WALLETWALLET_API_KEY` (see `.env.example`).
Free tier covers 1,000 passes/month - far more than 300 seats.

Leave `WALLETWALLET_API_KEY` blank to skip this entirely - the QR code and PDF
ticket (`ticketing.py`) never depend on it and always work.

**Worth knowing before relying on it for a real event:**
- It's a small, independently-run service, not an established company -
  there's real (if fairly low) risk of downtime or discontinuation. If it's
  unreachable when a booking is confirmed, the wallet buttons are simply
  skipped for that ticket (logged as a warning) - the QR/PDF ticket still
  goes out normally.
- Using it means sending each attendee's name, seat number(s), and their
  check-in link to WalletWallet's servers to build the pass. Skim their
  [Terms](https://www.walletwallet.dev/terms/) and
  [Privacy Policy](https://www.walletwallet.dev/privacy/) yourself before
  going live, since it's your attendees' data and your call as the event
  organiser, not something I can accept on your behalf.
- Wallet pass data (Google save link + signed Apple pass) is cached on the
  `Booking` row after first generation, so re-downloading later
  (`/ticket/<token>/wallet/apple` and `/ticket/<token>/wallet/google`) doesn't
  depend on WalletWallet staying up after that point.
- Cancelling a booking in the admin dashboard also revokes its wallet pass via
  WalletWallet's API (best-effort - a failure here doesn't block the
  cancellation itself).

## Adjusting seat price / hold time

Set `SEAT_PRICE_EUR` and `SEAT_HOLD_MINUTES` as environment variables (see
`.env.example`) - no code changes needed. Current price is set to **EUR 4.00**.

## Refund policy and privacy notice

Both are plain text set once in `config.py` (`REFUND_POLICY_TEXT`,
`PRIVACY_NOTICE_TEXT`, `ADMIN_CONTACT_EMAIL`) and shown automatically on the
booking page, in the confirmation email, and on the PDF ticket - edit there to
change the wording everywhere at once. Current policy: **all sales final, no
refunds**; data is used for this booking and future SZPM promotional
communications, with `admin@szpm.mt` as the contact to cancel or opt out.

## Security

A few things are already in place, without changing the overall shape of the
app:

- **Rate limiting** (Flask-Limiter) on `/admin/login` (10/min - brute-force
  protection), `/api/hold` (20/min - seat-squatting/spam protection), and
  `/booking/checkout` (10/min). Uses in-memory storage, which is fine for a
  single always-on process (e.g. PythonAnywhere) but resets if the process
  restarts and doesn't share state across multiple worker processes - if you
  ever scale to multiple workers, point it at Redis instead (see the
  Flask-Limiter docs).
- **Security headers** on every response: `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.
- **Session cookies** are `HttpOnly`, `SameSite=Lax`, and automatically
  `Secure` (HTTPS-only) once `BASE_URL` starts with `https://`.
- **Debug mode defaults off** - `python app.py` only enables Flask's
  interactive debugger (a real risk if ever exposed publicly - it can execute
  arbitrary code) when `FLASK_DEBUG=1` is explicitly set. Not relevant on
  PythonAnywhere anyway, since it imports `app` directly via WSGI rather than
  calling `app.run()`.
- **CSRF protection** (Flask-WTF) on every state-changing form; JSON API
  endpoints instead rely on `SameSite` cookies plus unguessable tokens.
- Passwords are hashed with Werkzeug's salted hasher; check-in and ticket
  access tokens are 32-byte random values (`secrets.token_urlsafe`), not
  sequential IDs.

**Still worth doing before launch**: change `ADMIN_PASSWORD` from its
placeholder (see "Admin accounts" above), and make sure `SECRET_KEY` in your
deployed environment is a long random value, not the example placeholder -
both are checked into `.env.example` deliberately weak so nobody ships them
by accident.

## Files

- `app.py` - Flask app factory / entry point
- `models.py` - Seat / Booking / Admin database tables
- `seats.py` - atomic seat state transitions (hold/release/book/disable)
- `seat_config.py` - the 300-seat layout (placeholder - replace with the real chart)
- `payments.py` - Stripe Checkout integration
- `webhooks.py` - Stripe webhook handler that finalises paid bookings
- `emailer.py` - confirmation emails (client + team), with the QR + PDF ticket attached
- `ticketing.py` - QR code and PDF ticket generation
- `reports.py` - Excel booking report
- `routes_public.py` / `routes_api.py` - the public booking page and its API
- `routes_admin.py` - admin login, dashboard, seat management, cash bookings, report
- `templates/`, `static/` - front-end
