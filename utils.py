import random
import re
import string


def generate_reference(prefix="FW"):
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{suffix}"


# Deliberately simple format check (not full RFC 5322) - just enough to
# catch typos and garbage before a ticket gets "sent" to an address that was
# never going to receive it. Real deliverability can only be confirmed by
# actually sending the email.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(email):
    return bool(email) and bool(_EMAIL_RE.match(email.strip()))
