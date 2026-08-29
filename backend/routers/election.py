from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_election_db, create_biometric_db, drop_biometric_db
from realtime import broadcast_booth_event

router = APIRouter()

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

# ─── START ELECTION ───────────────────────────────────────────

class ElectionActionResponse(BaseModel):
    ok: bool
    message: str

@router.post("/election/start", response_model=ElectionActionResponse)
async def start_election():
    conn = get_election_db()
    cur = conn.cursor()

    try:
        # Check if already active
        cur.execute("SELECT status FROM election_status ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()

        if row and row[0] == "active":
            return ElectionActionResponse(
                ok=False,
                message="Election is already active"
            )

        # Create biometric_db
        create_biometric_db()

        # Update election status
        cur.execute("""
            UPDATE election_status
            SET status = 'active',
                started_at = %s,
                total_votes = 0,
                active_booths = 0
        """, (datetime.now(),))
        conn.commit()

        await broadcast_booth_event("election_started", {
            "timestamp": datetime.now().isoformat(),
        })

        return ElectionActionResponse(
            ok=True,
            message="Election started. biometric_db created and ready."
        )

    finally:
        cur.close()
        conn.close()

# ─── END ELECTION ─────────────────────────────────────────────

@router.post("/election/end", response_model=ElectionActionResponse)
async def end_election():
    conn = get_election_db()
    cur = conn.cursor()

    try:
        # Check if active
        cur.execute("SELECT status FROM election_status ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()

        if not row or row[0] != "active":
            return ElectionActionResponse(
                ok=False,
                message="No active election to end"
            )

        # Deactivate all booth sessions
        cur.execute("UPDATE booth_sessions SET is_active = FALSE")

        # Update election status
        cur.execute("""
            UPDATE election_status
            SET status = 'ended',
                ended_at = %s,
                active_booths = 0
        """, (datetime.now(),))
        conn.commit()

        # Notify terminals before their now-invalid sessions are disconnected.
        await broadcast_booth_event("election_reset", {
            "timestamp": datetime.now().isoformat(),
        })

        # Drop biometric_db
        drop_biometric_db()

        return ElectionActionResponse(
            ok=True,
            message="Election ended. biometric_db destroyed. Fraud log preserved."
        )

    finally:
        cur.close()
        conn.close()
