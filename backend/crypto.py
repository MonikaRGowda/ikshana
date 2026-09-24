"""
Application-level encryption for voter PII at rest: name, phone,
address, dob on the voters table. Uses Fernet (AES-128 + HMAC,
authenticated encryption) - a database-only compromise (backup theft,
SQL injection, misconfigured access) doesn't expose plaintext voter
data on its own.

ENCRYPTION_KEY must be a Fernet key. Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Store it in .env, NEVER in source control. Losing this key means the
encrypted data is permanently unreadable - back it up somewhere
separate from the database itself (if the DB and the key are lost
together, you've lost nothing extra; if the key alone is lost, you've
lost the data even though the DB is fine).
"""

import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

_key = os.environ.get("ENCRYPTION_KEY")
if not _key:
    raise RuntimeError(
        "ENCRYPTION_KEY is not set. Generate one with:\n"
        '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"\n'
        "and add it to .env as ENCRYPTION_KEY=<value>"
    )
_fernet = Fernet(_key.encode())


def encrypt_field(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _fernet.encrypt(value.encode()).decode()


def decrypt_field(value: Optional[str]) -> Optional[str]:
    """
    Returns the plaintext value, or the input unchanged if it wasn't
    encrypted with the current key. That fallback matters during
    migration: existing rows are plaintext until the one-time
    re-encryption script runs, and a raised exception here would break
    every read of a not-yet-migrated voter instead of just showing
    them un-decrypted (still correct, just not yet re-encrypted).
    """
    if value is None:
        return None
    try:
        return _fernet.decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return value


def is_encrypted(value: Optional[str]) -> bool:
    """True if value decrypts successfully under the current key."""
    if value is None:
        return True
    try:
        _fernet.decrypt(value.encode())
        return True
    except (InvalidToken, ValueError):
        return False


def encrypt_bytes(value: Optional[bytes]) -> Optional[bytes]:
    """
    Byte-level counterpart to encrypt_field, for data that isn't valid
    UTF-8 text - fingerprint ISO templates and evidence photo files.
    """
    if value is None:
        return None
    return _fernet.encrypt(value)


def decrypt_bytes(value: Optional[bytes]) -> Optional[bytes]:
    """
    Same lazy-migration fallback as decrypt_field: returns the input
    unchanged if it wasn't encrypted with the current key, so
    not-yet-migrated rows/files still work.
    """
    if value is None:
        return None
    try:
        return _fernet.decrypt(value)
    except InvalidToken:
        return value


def is_bytes_encrypted(value: Optional[bytes]) -> bool:
    if value is None:
        return True
    try:
        _fernet.decrypt(value)
        return True
    except InvalidToken:
        return False