from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys
sys.path.append("..")
from database import get_election_db

router = APIRouter()

# Input model
class VoterLookupRequest(BaseModel):
    voter_id: str
    booth_id: str

# Output model
class VoterLookupResponse(BaseModel):
    status: str
    message: str
    voter_name: str = None
    constituency: str = None
    booth_id: str = None
    timestamp: str = None  

@router.post("/verify-voter", response_model=VoterLookupResponse)
async def verify_voter(request: VoterLookupRequest):

    conn = get_election_db()
    cur = conn.cursor()

    try:
        # Look up voter by ID
        cur.execute("""
            SELECT 
                voter_id,
                name,
                constituency,
                booth_id,
                has_voted
            FROM voters
            WHERE voter_id = %s
        """, (request.voter_id.upper(),))

        voter = cur.fetchone()

        # Case 1 — Voter not found
        if not voter:
            return VoterLookupResponse(
                status="not_found",
                message=f"Voter ID {request.voter_id} not found in registry"
            )

        voter_id, name, constituency, assigned_booth, has_voted = voter

        # Case 2 — Voter already voted
        if has_voted:
            # Case 2 — Already voted
                return VoterLookupResponse(
                    status="duplicate",  # ✅ changed from "already_voted"
                    message=f"{name} has already voted. Duplicate attempt blocked.",
                    voter_name=name,
                    constituency=constituency,
                    booth_id=assigned_booth
                )

# Case 3 — Good to go
        return VoterLookupResponse(
            status="verified",  # ✅ changed from "proceed"
            message=f"Voter {name} verified. Proceed to biometric scan.",
            voter_name=name,
            constituency=constituency,
            booth_id=assigned_booth
        )

    finally:
        cur.close()
        conn.close()