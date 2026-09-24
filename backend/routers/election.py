from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_election_db, create_biometric_db, drop_biometric_db
from realtime import broadcast_booth_event
from deps import require_role
from security import verify_password
from otp import generate_otp, hash_otp, send_otp_email

router = APIRouter()

OTP_TTL_MINUTES = 5
MAX_OTP_ATTEMPTS = 5

# ─── ELECTION STATUS ──────────────────────────────────────────

class ElectionStatus(BaseModel):
    name: str
    status: str
    total_votes: int
    active_booths: int

@router.get("/election/status", response_model=ElectionStatus)
async def get_election_status():
    conn = get_election_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT 
                election_name,
                status,
                total_votes,
                active_booths
            FROM election_status
            ORDER BY id DESC
            LIMIT 1
        """)
        row = cur.fetchone()

        if not row:
            return ElectionStatus(
                name="No Election Configured",
                status="inactive",
                total_votes=0,
                active_booths=0
            )

        return ElectionStatus(
            name=row[0],
            status=row[1],
            total_votes=row[2],
            active_booths=row[3]
        )

    finally:
        cur.close()
        conn.close()

# ─── STEP-UP AUTH (shared by start/end) ───────────────────────
#
# Both actions require: password re-entry -> email OTP -> confirm with
# OTP + a mandatory reason, before anything destructive happens. This
# is deliberately two round trips (no otp_code yet -> otp_code provided)
# rather than one, so the frontend can show "check your email" between
# steps.

class ElectionStepUpRequest(BaseModel):
    password: Optional[str] = None
    reason: Optional[str] = None
    otp_code: Optional[str] = None
    confirmation_text: Optional[str] = None

class ElectionActionResponse(BaseModel):
    status: str
    message: str

def _request_step_up_otp(cur, conn, officer_id: str, password: str, purpose: str) -> Optional[ElectionActionResponse]:
    """
    Verifies the officer's password and, if correct, sends a fresh OTP
    for this specific action. Returns a response to send back immediately,
    or None if the caller should proceed (this never happens on this path -
    it always returns either an error or "otp_required").
    """
    cur.execute("SELECT password_hash, email FROM booth_officers WHERE officer_id = %s", (officer_id,))
    row = cur.fetchone()
    if not row:
        return ElectionActionResponse(status="error", message="Officer account not found.")

    password_hash, email = row
    is_valid, _ = verify_password(password, password_hash)
    if not is_valid:
        return ElectionActionResponse(status="invalid_password", message="Incorrect password.")

    if not email:
        return ElectionActionResponse(status="error", message="No email on file for this account.")

    code = generate_otp()
    expires_at = datetime.now() + timedelta(minutes=OTP_TTL_MINUTES)
    cur.execute(
        "INSERT INTO otp_codes (officer_id, code_hash, expires_at, purpose) VALUES (%s, %s, %s, %s)",
        (officer_id, hash_otp(code), expires_at, purpose),
    )
    conn.commit()
    send_otp_email(email, code)

    return ElectionActionResponse(
        status="otp_required",
        message=f"A confirmation code has been sent to {email[:2]}***{email[email.index('@'):]}.",
    )


def _verify_step_up_otp(cur, officer_id: str, otp_code: str, purpose: str) -> Optional[str]:
    """
    Returns None if the OTP is valid (caller should proceed), otherwise
    an error message to send back instead.
    """
    cur.execute(
        """
        SELECT id, code_hash, expires_at, consumed, attempts
        FROM otp_codes
        WHERE officer_id = %s AND purpose = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (officer_id, purpose),
    )
    row = cur.fetchone()
    if not row:
        return "No confirmation code found. Please start over."

    otp_id, code_hash, expires_at, consumed, attempts = row

    if consumed:
        return "This code has already been used. Please start over."
    if attempts >= MAX_OTP_ATTEMPTS:
        return "Too many incorrect attempts. Please start over."
    if expires_at < datetime.now():
        return "This code has expired. Please start over."
    if hash_otp(otp_code.strip()) != code_hash:
        cur.execute("UPDATE otp_codes SET attempts = attempts + 1 WHERE id = %s", (otp_id,))
        return "Incorrect code."

    cur.execute("UPDATE otp_codes SET consumed = TRUE WHERE id = %s", (otp_id,))
    return None


def _log_election_action(cur, officer_id: str, action: str, reason: str, ip_address: Optional[str]):
    cur.execute(
        "INSERT INTO election_action_log (officer_id, action, reason, ip_address) VALUES (%s, %s, %s, %s)",
        (officer_id, action, reason, ip_address),
    )

# ─── START ELECTION ───────────────────────────────────────────

@router.post("/election/start", response_model=ElectionActionResponse)
async def start_election(
    body: ElectionStepUpRequest,
    request: Request,
    officer: dict = Depends(require_role("CEO")),
):
    conn = get_election_db()
    cur = conn.cursor()

    try:
        cur.execute("SELECT status FROM election_status ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row and row[0] == "active":
            return ElectionActionResponse(status="already_active", message="Election is already active.")

        if not body.otp_code:
            if not body.password or not body.reason:
                return ElectionActionResponse(status="error", message="Password and reason are required.")
            return _request_step_up_otp(cur, conn, officer["officer_id"], body.password, "election_start")

        error = _verify_step_up_otp(cur, officer["officer_id"], body.otp_code, "election_start")
        if error:
            conn.commit()  # persist the attempts-increment from a wrong OTP
            return ElectionActionResponse(status="invalid_otp", message=error)

        # Confirmed — actually start the election.
        create_biometric_db()

        cur.execute("""
            UPDATE election_status
            SET status = 'active',
                started_at = %s,
                total_votes = 0,
                active_booths = 0
        """, (datetime.now(),))

        _log_election_action(cur, officer["officer_id"], "start", body.reason or "", request.client.host if request.client else None)
        conn.commit()

        await broadcast_booth_event("election_started", {
            "timestamp": datetime.now().isoformat(),
        })

        return ElectionActionResponse(status="ok", message="Election started. Biometric logging is ready.")

    finally:
        cur.close()
        conn.close()

# ─── END ELECTION ─────────────────────────────────────────────

@router.post("/election/end", response_model=ElectionActionResponse)
async def end_election(
    body: ElectionStepUpRequest,
    request: Request,
    officer: dict = Depends(require_role("CEO")),
):
    conn = get_election_db()
    cur = conn.cursor()

    try:
        cur.execute("SELECT status, election_name FROM election_status ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row or row[0] != "active":
            return ElectionActionResponse(status="not_active", message="No active election to end.")

        election_name = row[1]

        if not body.otp_code:
            # GitHub-style "type the name to confirm" gate - checked
            # server-side too, not just in the UI, before anything else.
            if (body.confirmation_text or "").strip() != (election_name or "").strip():
                return ElectionActionResponse(
                    status="invalid_confirmation",
                    message=f"Type the election name exactly ({election_name}) to confirm.",
                )
            if not body.password or not body.reason:
                return ElectionActionResponse(status="error", message="Password and reason are required.")
            return _request_step_up_otp(cur, conn, officer["officer_id"], body.password, "election_end")

        error = _verify_step_up_otp(cur, officer["officer_id"], body.otp_code, "election_end")
        if error:
            conn.commit()
            return ElectionActionResponse(status="invalid_otp", message=error)

        # Confirmed — actually end the election.
        cur.execute("UPDATE booth_sessions SET is_active = FALSE")

        # Reset every voter's has_voted flag so they aren't locked out of
        # the NEXT election. fraud_log is untouched, so records of this
        # election's fraud attempts are preserved.
        cur.execute("UPDATE voters SET has_voted = FALSE")

        cur.execute("""
            UPDATE election_status
            SET status = 'ended',
                ended_at = %s,
                active_booths = 0
        """, (datetime.now(),))

        _log_election_action(cur, officer["officer_id"], "end", body.reason or "", request.client.host if request.client else None)
        conn.commit()

        # Notify terminals before their now-invalid sessions are disconnected.
        await broadcast_booth_event("election_reset", {
            "timestamp": datetime.now().isoformat(),
        })

        # Local development may use a separate biometric database. Production
        # keeps biometric_log in the shared Render database.
        drop_biometric_db()

        return ElectionActionResponse(
            status="ok",
            message="Election ended. Fraud log preserved. Voter has_voted flags reset.",
        )

    finally:
        cur.close()
        conn.close()