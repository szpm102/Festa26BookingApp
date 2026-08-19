# Fireworks Seat Booking - "Light Up the Sky", Munxar 2026

Web app for booking the 300 viewing seats for the Festa Munxar fireworks display
(Andrijiet Street, Munxar, Sat 12 Sept 2026, 21:30). Seats are held live while a
visitor is checking out, paid via Stripe, and permanently marked booked once
payment succeeds. Admins can also book a seat manually for a cash payment, or
disable a seat entirely (e.g. reserved seating).

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
  email, seats, amount, payment method/status).

## IMPORTANT - seat layout is a placeholder

No real venue seating chart was available yet, so `seat_config.py` currently
generates a generic 20-row x 15-seat grid (rows A-T) = 300 seats. **Send over
the actual seating plan for Andrijiet Street** (sections, rows, numbering) and
this file should be updated to match before going live - seat labels shown to
the public should match what's physically marked/painted at the venue.

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

## Adjusting seat price / hold time

Set `SEAT_PRICE_EUR` and `SEAT_HOLD_MINUTES` as environment variables (see
`.env.example`) - no code changes needed.

## Files

- `app.py` - Flask app factory / entry point
- `models.py` - Seat / Booking / Admin database tables
- `seats.py` - atomic seat state transitions (hold/release/book/disable)
- `seat_config.py` - the 300-seat layout (placeholder - replace with the real chart)
- `payments.py` - Stripe Checkout integration
- `webhooks.py` - Stripe webhook handler that finalises paid bookings
- `emailer.py` - confirmation emails (client + team)
- `reports.py` - Excel booking report
- `routes_public.py` / `routes_api.py` - the public booking page and its API
- `routes_admin.py` - admin login, dashboard, seat management, cash bookings, report
- `templates/`, `static/` - front-end
