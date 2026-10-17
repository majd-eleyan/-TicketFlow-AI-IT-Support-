# فحص المدخلات وتنظيف البيانات
import re
import config
from models import ValidationResult

SECRET_PATTERNS = [
    (r"(?i)\b(password|passcode|pwd)\b\s*[:=]\s*\S+", r"\1: [REDACTED]"),
    (r"(?i)\b(api[ _-]?key|secret|token)\b\s*[:=]\s*\S+", r"\1: [REDACTED]"),
    (r"(?i)\b(otp|code)\b\s*[:=]\s*\d{4,8}\b", r"\1: [REDACTED]"),
    (r"\bsk-[A-Za-z0-9_-]{10,}\b", "[REDACTED]"),
    (r"\b(?:\d[ -]?){13,16}\b", "[REDACTED]"),
]


def normalize_whitespace(text):
    return " ".join((text or "").split())


def redact_secrets(text):
    found = False
    for pattern, replacement in SECRET_PATTERNS:
        text, count = re.subn(pattern, replacement, text)
        if count > 0:
            found = True
    return text, found


def clean_optional_field(value):
    value = normalize_whitespace(value)[:getattr(config, "MAX_FIELD_CHARS", 100)]
    clean_val, _ = redact_secrets(value)
    return clean_val


def validate_input(customer_id, message, min_chars=None):
    min_chars = min_chars or getattr(config, "MIN_MESSAGE_CHARS", 10)
    customer_id = normalize_whitespace(customer_id)
    message = normalize_whitespace(message)
    if not customer_id:
        return ValidationResult(ok=False, error="Customer ID is required.")
    if len(customer_id) > getattr(config, "MAX_FIELD_CHARS", 100):
        return ValidationResult(ok=False, error="Customer ID is too long.")
    if not message:
        return ValidationResult(ok=False, error="The message cannot be empty.")
    max_chars = getattr(config, "MAX_MESSAGE_CHARS", 2000)
    if len(message) > max_chars:
        return ValidationResult(
            ok=False,
            error=f"Message is too long (maximum {max_chars} characters allowed).",
        )
    if len(message) < min_chars:
        return ValidationResult(
            ok=False,
            error=f"Message is too short (minimum {min_chars} characters required).",
        )
    clean_message, secrets_found = redact_secrets(message)
    return ValidationResult(
        ok=True,
        error="",
        clean_message=clean_message,
        secrets_removed=secrets_found,
    )
