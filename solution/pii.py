"""PII hashing and encryption helpers.

Phones are never stored in plaintext. Matching uses a stable HMAC-SHA256 of the
canonical +91XXXXXXXXXX form. Customer names are Fernet-encrypted at rest.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet

from solution.config import PII_KEY


def _hmac_key() -> bytes:
    return PII_KEY.encode("utf-8")


def phone_hash(canonical_phone: str) -> str:
    """HMAC-SHA256 hex digest of the canonical phone (+91XXXXXXXXXX)."""
    return hmac.new(_hmac_key(), canonical_phone.encode("utf-8"), hashlib.sha256).hexdigest()


def phone_last4(canonical_phone: str) -> str:
    """Last 4 digits of the 10-digit mobile (after +91)."""
    digits = "".join(c for c in canonical_phone if c.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits[-4:]


def _fernet() -> Fernet:
    # Derive a stable Fernet key from PII_KEY (32 url-safe base64-encoded bytes).
    digest = hashlib.sha256(_hmac_key()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_name(name: str) -> str:
    return _fernet().encrypt(name.encode("utf-8")).decode("utf-8")


def decrypt_name(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


def mask_phone(last4: str) -> str:
    """Report masking: +91******XXXX."""
    return f"+91******{last4}"
