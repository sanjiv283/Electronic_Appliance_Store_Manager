"""Server-side input validation shared by all services."""
import re
from decimal import Decimal, InvalidOperation

from .errors import ValidationError

_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_PHONE = re.compile(r"^\+?[0-9][0-9 \-()]{5,18}$")


def text(form, key, label, max_len, required=True):
    value = (form.get(key) or "").strip()
    if not value:
        if required:
            raise ValidationError(f"{label} is required.")
        return None
    if len(value) > max_len:
        raise ValidationError(f"{label} must be at most {max_len} characters.")
    return value


def integer(value, label, minimum=0, maximum=10**8):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a whole number.") from None
    if not minimum <= number <= maximum:
        raise ValidationError(f"{label} must be between {minimum} and {maximum}.")
    return number


def record_id(value, label="ID"):
    return integer(value, label, 1, 10**12)


def money(value, label="Price", maximum=Decimal("99999999.99")):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError(f"{label} must be a number.") from None
    if not amount.is_finite() or amount < 0 or amount > maximum:
        raise ValidationError(f"{label} must be between 0 and {maximum}.")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValidationError(f"{label} can have at most 2 decimal places.")
    return amount.quantize(Decimal("0.01"))


def email(form, key="email", label="Email", required=True):
    value = text(form, key, label, 120, required)
    if value and not _EMAIL.match(value):
        raise ValidationError(f"{label} is not a valid email address.")
    return value


def phone(form, key="phone", label="Phone", required=True):
    value = text(form, key, label, 20, required)
    if value and (not _PHONE.match(value) or not 7 <= sum(c.isdigit() for c in value) <= 15):
        raise ValidationError(f"{label} must contain 7-15 digits (digits, spaces, +, -, parentheses).")
    return value
