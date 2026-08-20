# User Guide - Fireworks Seat Booking (for SZPM committee & door staff)

This is a plain-language guide to running the booking system day-to-day - no
coding knowledge needed. For how the system is built, see
[TECHNICAL.md](TECHNICAL.md).

## Contents

1. [Logging in](#1-logging-in)
2. [The admin dashboard](#2-the-admin-dashboard)
3. [Selling a seat for cash](#3-selling-a-seat-for-cash)
4. [Disabling / re-enabling seats](#4-disabling--re-enabling-seats)
5. [Bookings list and reports](#5-bookings-list-and-reports)
6. [Checking guests in on the day](#6-checking-guests-in-on-the-day)
7. [If a confirmation email didn't arrive](#7-if-a-confirmation-email-didnt-arrive)
8. [Managing admin / door-staff accounts](#8-managing-admin--door-staff-accounts)
9. [Installing the site as an app on your phone](#9-installing-the-site-as-an-app-on-your-phone)
10. [What guests see and experience](#10-what-guests-see-and-experience)
11. [Getting help](#11-getting-help)

---

## 1. Logging in

Go to `https://festa26.szpm.mt/admin/login` and sign in with your admin
email/password. If you don't have an account yet, ask whoever holds a
**superadmin** account to create one for you (see section 8) - no server
access is needed for this.

## 2. The admin dashboard

After logging in you'll see:

- **Stats at the top**: total seats, available, held (mid-checkout right
  now), booked, disabled, and revenue collected so far.
- **Ticket check-in card**: the "Scan Ticket QR" button and a manual
  booking-reference lookup box (see section 6).
- **Seat map**: click seats to select them (they turn a different colour
  while selected), then use the buttons underneath to act on the selection.
- **Bookings table**: every booking so far, with its reference, name,
  email, seats, amount, payment method, status, and check-in progress
  (e.g. `2/3` seats checked in). Click a reference to open that booking's
  full seat-by-seat check-in overview.

**Seat colours**: available, selected, held (someone else is mid-checkout),
booked, disabled - shown in the legend above the seat map itself.

## 3. Selling a seat for cash

For a guest paying in person (e.g. at the parish office, or door sales):

1. Click the seat(s) they want on the seat map (they'll show as "selected").
2. Click **"Book for cash payment"**.
3. Fill in their name, email, and phone (email is required - that's where
   their ticket goes), and an optional note (e.g. "paid at parish office").
4. Click **Confirm booking**.

The seat(s) immediately turn "Booked", and a confirmation email with their
ticket goes out right away, the same as an online payment.

## 4. Disabling / re-enabling seats

To hold a seat back from public sale (reserved seating, given away, etc.):
select it on the seat map and click **"Disable selected"**. To put it back
on sale, select it and click **"Enable selected"**. Disabling a seat that
someone is *currently* mid-checkout on will cancel their hold - use with
that in mind close to the event.

## 5. Bookings list and reports

- The **Bookings** table on the dashboard shows everything as it happens.
- Click **"Download report (.xlsx)"** at the top of the dashboard for a full
  Excel export - every booking's name, email, seats, amount, payment
  method/status, and check-in detail per seat. Good for reconciling with
  Stripe payouts or for committee records.

## 6. Checking guests in on the day

Each seat in a booking has its **own** QR code and its **own** independent
check-in status - so a group that arrives in separate waves can each be
checked in without triggering a false "already scanned" warning for the
others.

**Three ways to check someone in**, all equivalent:

1. **In-app scanner** - click **"Scan Ticket QR"** on the dashboard, allow
   camera access when your phone/tablet asks, and point it at the guest's
   QR code (on their phone or printed ticket). It opens that seat's page
   automatically once recognised.
2. **Your phone's normal camera app** - just point it at the QR code like
   you would for any QR code; it opens the same check-in page directly
   (you'll be asked to log in first if you aren't already).
3. **Manual lookup** - type the booking reference (e.g. `FW-AB12CD`) into
   the box on the dashboard and click **Look up**. This opens an overview
   of *every* seat in that booking, each with its own status and check-in
   button - handy for checking a whole group in from one screen without
   scanning each one.

Once you're on a seat's check-in page, click **"Mark Checked In"**. A green
banner confirms it. If that seat gets scanned again later, it shows a **red
"already scanned"** warning instead and the check-in button disappears -
that's the system protecting against a duplicate/shared ticket, and it's
normal to see it if you accidentally scan the same ticket twice.

**Resetting a check-in** (e.g. undoing an accidental test scan before the
event) can only be done by a **superadmin** account, from that seat's
check-in page or the booking overview page.

## 7. If a confirmation email didn't arrive

Open the booking on the dashboard (click its reference in the Bookings
table, or type the reference into the manual lookup box), and click
**"Resend confirmation email"** near the top of that page - it re-sends the
same email with the same ticket(s) attached. This only appears for bookings
marked "paid".

If it still doesn't arrive after resending, check the guest typed their
email correctly (it's shown on that same page), then ask whoever manages
the technical side to check the server's error log - see
[TECHNICAL.md](TECHNICAL.md) section 9 for what to look for.

## 8. Managing admin / door-staff accounts

Only **superadmin** accounts can do this - click **"Manage admins"** on the
dashboard (only visible to superadmins).

- **To add someone** (e.g. door staff for the event): fill in their email
  and a password (at least 8 characters), tick "superadmin" only if they
  should have full rights (create/remove other accounts, reset check-ins),
  and click Create. No server access needed.
- **To remove someone**: click Delete next to their account. You can't
  delete your own account, and you can't delete the last remaining
  superadmin (there must always be at least one).

Regular (non-superadmin) accounts can do everything day-to-day - seat map,
cash bookings, check-in, reports, resending emails - just not reset a
check-in or manage other admin accounts.

## 9. Installing the site as an app on your phone

Open `https://festa26.szpm.mt` in your phone's browser, then:
- **iPhone (Safari)**: tap the Share icon -> "Add to Home Screen".
- **Android (Chrome)**: tap the menu (⋮) -> "Add to Home Screen" or "Install
  app" (wording varies by Chrome version).

This adds an icon that opens the site full-screen, without the browser's
address bar - handy for the scan page if you'll be using it repeatedly on
the event day. If Android shows a warning about "an older version of
Android" when installing, that's a known Chrome-side quirk unrelated to
this site - updating Chrome from the Play Store usually clears it, and it's
generally safe to tap "Install anyway" if it persists.

## 10. What guests see and experience

Useful to know so you can answer guest questions:

- They pick seats on the live seat map on the homepage; a seat they click
  is held for them for a few minutes while they enter their details and pay
  (so nobody else can take it mid-checkout).
- Payment is by card via Stripe's secure checkout page - SZPM never sees or
  stores card details.
- Once paid, they get an email with: a PDF ticket (one page per seat, each
  with its own QR code) and, if set up, Apple/Google Wallet buttons to add
  each seat's pass to their phone's wallet app.
- They can re-download their PDF ticket anytime using the personal link in
  their confirmation email - no login needed.
- **Refund policy**: all bookings are final, tickets are non-refundable -
  shown on the booking page, in the email, and on the ticket itself.
- **Privacy notice**: their details are used for this booking and future
  SZPM promotional communications; they can email `admin@szpm.mt` anytime
  to cancel a booking or opt out - also shown in the same three places.

## 11. Getting help

- **A guest's specific booking issue** (wrong seat, wants to change
  details, etc.): look them up by reference on the dashboard - most things
  can be handled from there (resend email, view status). Cancelling a
  booking frees its seat(s) back to available.
- **Something looks technically broken** (error message, seats stuck, etc.):
  pass it on to whoever manages the technical side, ideally with the
  booking reference and roughly when it happened - see
  [TECHNICAL.md](TECHNICAL.md) section 9 for the troubleshooting steps
  already known to work for the most common issues.
