"""
Login flow for RO/CEO accounts: officer_id + password -> email OTP ->
verify OTP -> httpOnly session cookie. Deliberately separate from
booth.py's booth-officer login, since these accounts are higher
privilege and need the extra factor + lockout protection.
"""

import datetime
import hashlib
import secrets
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import APIRouter, Cookie, Response
from pydantic import BaseModel

from database import get_election_db
from security import verify_password
from otp import generate_otp, hash_otp, send_otp_email

router = APIRouter()

OTP_TTL_MINUTES = 5
MAX_OTP_ATTEMPTS = 5
SESSION_TTL_HOURS = 8
MAX_LOGIN_FAILURES = 5
LOCKOUT_MINUTES = 15


class AdminLoginRequest(BaseModel):
    officer_id: str
    password: str


class VerifyOtpRequest(BaseModel):
    officer_id: str
    code: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/api/admin/login")
def admin_login(request: AdminLoginRequest):
    officer_id = request.officer_id.strip().upper()

    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT password_hash, role, email, failed_attempts, locked_until, is_active
            FROM booth_officers
            WHERE officer_id = %s
            """,
            (officer_id,),
        )
        row = cur.fetchone()

        if not row:
            return {"status": "invalid_credentials", "message": "Incorrect officer ID or password."}

        password_hash, role, email, failed_attempts, locked_until, is_active = row

        if role not in ("RO", "CEO"):
            return {"status": "invalid_credentials", "message": "Incorrect officer ID or password."}

        if not is_active:
            return {"status": "account_disabled", "message": "This account has been disabled."}

        if locked_until and locked_until > datetime.datetime.now():
            return {
                "status": "locked",
                "message": f"Too many failed attempts. Try again after {locked_until.strftime('%H:%M:%S')}.",
            }

        if not email:
            return {"status": "no_email", "message": "No email on file for this account. Contact the CEO."}

        is_valid, _ = verify_password(request.password, password_hash)

        if not is_valid:
            new_failed = failed_attempts + 1
            if new_failed >= MAX_LOGIN_FAILURES:
                lock_until = datetime.datetime.now() + datetime.timedelta(minutes=LOCKOUT_MINUTES)
                cur.execute(
                    "UPDATE booth_officers SET failed_attempts = 0, locked_until = %s WHERE officer_id = %s",
                    (lock_until, officer_id),
                )
                conn.commit()
                return {
                    "status": "locked",
                    "message": f"Too many failed attempts. Try again after {lock_until.strftime('%H:%M:%S')}.",
                }
            cur.execute(
                "UPDATE booth_officers SET failed_attempts = %s WHERE officer_id = %s",
                (new_failed, officer_id),
            )
            conn.commit()
            return {"status": "invalid_credentials", "message": "Incorrect officer ID or password."}

        # Correct password - reset failure counter, issue an OTP
        cur.execute(
            "UPDATE booth_officers SET failed_attempts = 0, locked_until = NULL WHERE officer_id = %s",
            (officer_id,),
        )

        code = generate_otp()
        expires_at = datetime.datetime.now() + datetime.timedelta(minutes=OTP_TTL_MINUTES)
        cur.execute(
            "INSERT INTO otp_codes (officer_id, code_hash, expires_at) VALUES (%s, %s, %s)",
            (officer_id, hash_otp(code), expires_at),
        )
        conn.commit()

        send_otp_email(email, code)

        return {"status": "otp_sent", "message": f"A login code has been sent to {email[:2]}***{email[email.index('@'):]}."}
    finally:
        cur.close()
        conn.close()


@router.post("/api/admin/verify-otp")
def verify_otp(request: VerifyOtpRequest, response: Response):
    officer_id = request.officer_id.strip().upper()

    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, code_hash, expires_at, consumed, attempts
            FROM otp_codes
            WHERE officer_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (officer_id,),
        )
        row = cur.fetchone()

        if not row:
            return {"status": "invalid", "message": "No login code found. Please log in again."}

        otp_id, code_hash, expires_at, consumed, attempts = row

        if consumed:
            return {"status": "invalid", "message": "This code has already been used. Please log in again."}

        if attempts >= MAX_OTP_ATTEMPTS:
            return {"status": "invalid", "message": "Too many incorrect attempts. Please log in again."}

        if expires_at < datetime.datetime.now():
            return {"status": "expired", "message": "This code has expired. Please log in again."}

        if hash_otp(request.code.strip()) != code_hash:
            cur.execute("UPDATE otp_codes SET attempts = attempts + 1 WHERE id = %s", (otp_id,))
            conn.commit()
            return {"status": "invalid", "message": "Incorrect code."}

        cur.execute("UPDATE otp_codes SET consumed = TRUE WHERE id = %s", (otp_id,))

        cur.execute(
            "SELECT name, role, constituency FROM booth_officers WHERE officer_id = %s",
            (officer_id,),
        )
        name, role, constituency = cur.fetchone()

        token = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.now() + datetime.timedelta(hours=SESSION_TTL_HOURS)
        cur.execute(
            """
            INSERT INTO admin_sessions (token_hash, officer_id, role, constituency, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (_hash_token(token), officer_id, role, constituency, expires_at),
        )
        conn.commit()

        response.set_cookie(
            key="admin_session",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=SESSION_TTL_HOURS * 3600,
        )

        return {
            "status": "ok",
            "officer_name": name,
            "role": role,
            "constituency": constituency,
        }
    finally:
        cur.close()
        conn.close()


@router.post("/api/admin/logout")
def admin_logout(response: Response, admin_session: str | None = Cookie(default=None)):
    if admin_session:
        conn = get_election_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE admin_sessions SET revoked = TRUE WHERE token_hash = %s",
            (_hash_token(admin_session),),
        )
        conn.commit()
        cur.close()
        conn.close()

    response.delete_cookie("admin_session")
    return {"status": "ok"}