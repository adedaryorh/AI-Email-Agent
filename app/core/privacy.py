import re

_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)")

def redact(value):
    """Best-effort email/phone masking, not a guarantee of anonymization."""
    if isinstance(value, str):
        return _PHONE.sub("[PHONE]", _EMAIL.sub("[EMAIL]", value))
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value
