"""
Password hashing. Existing booth_officers rows were hashed with plain
SHA-256 (no salt) — this module replaces that with argon2, while
transparently upgrading old hashes the first time each officer logs in
successfully, so nobody gets locked out on rollout.
"""

import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def _is_legacy_sha256(stored_hash: str) -> bool:
    return len(stored_hash) == 64 and not stored_hash.startswith("$argon2")


def verify_password(password: str, stored_hash: str) -> tuple[bool, bool]:
    """
    Returns (is_valid, needs_rehash).

    needs_rehash is True when the password was correct but stored under
    the old SHA-256 scheme (or an outdated argon2 parameter set) — the
    caller should then call hash_password() and save the new hash.
    """
    if _is_legacy_sha256(stored_hash):
        is_valid = hashlib.sha256(password.encode()).hexdigest() == stored_hash
        return is_valid, is_valid

    try:
        _ph.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHash):
        return False, False

    return True, _ph.check_needs_rehash(stored_hash)