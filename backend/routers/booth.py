from fastapi import APIRouter, Request
import hashlib
import secrets
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_election_db
from realtime import broadcast_booth_event
from pydantic import BaseModel

router = APIRouter()

# Input model
class BoothLoginRequest(BaseModel):
    officer_id: str
    password: str

# Output model
class BoothLoginResponse(BaseModel):
    status: str        # "success" / "invalid_credentials" / "wrong_booth"
    message: str
    officer_name: str = None
    designation: str = None
    assigned_booth: str = None
    session_token: str = None

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _refresh_active_booth_count(cur):
    """Persist the number of distinct booths with an active officer session."""
    cur.execute(
        """
        UPDATE election_status
        SET active_booths = (
            SELECT COUNT(DISTINCT booth_id)
            FROM booth_sessions
            WHERE is_active = TRUE
        )
        WHERE id = (SELECT id FROM election_status ORDER BY id DESC LIMIT 1)
        RETURNING total_votes, active_booths
        """
    )
    return cur.fetchone()


async def _broadcast_stats(stats) -> None:
    if not stats:
        return
    await broadcast_booth_event("election_stats_updated", {
        "total_votes": stats[0],
        "active_booths": stats[1],
    })

@router.post("/booth/login", response_model=BoothLoginResponse)
async def booth_login(request: BoothLoginRequest, req: Request):

    conn = get_election_db()
    cur = conn.cursor()

    try:
        # Look up officer by ID
        cur.execute("""
            SELECT 
                officer_id,
                name,
                designation,
                assigned_booth,
                password_hash,
                is_active
            FROM booth_officers
            WHERE officer_id = %s
        """, (request.officer_id.upper(),))

        officer = cur.fetchone()

        # Case 1 — Officer not found
        if not officer:
            return BoothLoginResponse(
                status="invalid_credentials",
                message="Officer ID not found. Check your credentials."
            )

        officer_id, name, designation, assigned_booth, password_hash, is_active = officer

        # Case 2 — Officer not active
        if not is_active:
            return BoothLoginResponse(
                status="invalid_credentials",
                message="Officer account is inactive. Contact Election Commission."
            )

        # Case 3 — Wrong password
        if hash_password(request.password) != password_hash:
            return BoothLoginResponse(
                status="invalid_credentials",
                message="Incorrect password. Try again."
            )

        # Case 4 — Success
        # Log the login
        session_token = secrets.token_urlsafe(32)
        client_ip = req.client.host

        cur.execute("""
            CREATE TABLE IF NOT EXISTS booth_sessions (
                id SERIAL PRIMARY KEY,
                session_token VARCHAR(255) UNIQUE NOT NULL,
                officer_id VARCHAR(50),
                booth_id VARCHAR(20),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("ALTER TABLE booth_sessions ADD COLUMN IF NOT EXISTS session_token VARCHAR(255)")
        cur.execute("ALTER TABLE booth_sessions ADD COLUMN IF NOT EXISTS officer_id VARCHAR(50)")
        cur.execute("ALTER TABLE booth_sessions ADD COLUMN IF NOT EXISTS booth_id VARCHAR(20)")
        cur.execute("ALTER TABLE booth_sessions ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        cur.execute("ALTER TABLE booth_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        cur.execute("""
            UPDATE booth_sessions
            SET is_active = FALSE
            WHERE officer_id = %s OR booth_id = %s
        """, (officer_id, assigned_booth))

        cur.execute("""
            INSERT INTO booth_sessions
                (session_token, officer_id, booth_id, is_active)
            VALUES (%s, %s, %s, TRUE)
        """, (session_token, officer_id, assigned_booth))
        cur.execute("""
            INSERT INTO officer_login_log 
                (officer_id, booth_id, ip_address)
            VALUES (%s, %s, %s)
        """, (officer_id, assigned_booth, client_ip))
        stats = _refresh_active_booth_count(cur)
        conn.commit()
        await _broadcast_stats(stats)

        return BoothLoginResponse(
            status="success",
            message=f"Welcome {name}. Booth {assigned_booth} is now active.",
            officer_name=name,
            designation=designation,
            assigned_booth=assigned_booth,
            session_token=session_token
        )

    finally:
        cur.close()
        conn.close()
class BoothLogoutRequest(BaseModel):
    session_token: str

class BoothLogoutResponse(BaseModel):
    ok: bool
    message: str

@router.post("/booth/logout", response_model=BoothLogoutResponse)
async def booth_logout(request: BoothLogoutRequest):
    conn = get_election_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE booth_sessions
            SET is_active = FALSE
            WHERE session_token = %s
        """, (request.session_token,))
        stats = _refresh_active_booth_count(cur)
        conn.commit()
        await _broadcast_stats(stats)

        return BoothLogoutResponse(
            ok=True,
            message="Booth logged out successfully"
        )

    finally:
        cur.close()
        conn.close()
