"""
Serves fraud evidence photos and reasons to logged-in RO/CEO officers
only. These are photos of the person at a fraud attempt - never expose
them unauthenticated or as a static file mount.
"""

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from database import get_election_db
from deps import require_role
from crypto import decrypt_bytes

router = APIRouter()

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evidence")


class OriginalVote(BaseModel):
    booth_id: str
    timestamp: str


class EvidenceEntry(BaseModel):
    timestamp: str
    voter_id: str
    booth_id: str
    constituency: Optional[str] = None
    fraud_type: Optional[str] = None
    details: Optional[str] = None
    evidence_photo_url: str
    original_vote: Optional[OriginalVote] = None


@router.get("/api/admin/evidence", response_model=List[EvidenceEntry])
def list_evidence(officer: dict = Depends(require_role("RO", "CEO"))):
    """
    Every fraud_log entry that actually HAS a photo, paired with the
    reason (fraud_type/details) it was flagged for. RO gets only their
    own constituency's entries; CEO gets all of them.
    """
    conn = get_election_db()
    cur = conn.cursor()
    try:
        base_query = """
            SELECT
                f.timestamp::text, f.voter_id, f.booth_id, v.constituency,
                f.fraud_type, f.details, f.offender_face_image,
                f.original_vote_booth_id, f.original_vote_timestamp::text
            FROM fraud_log f
            LEFT JOIN voters v ON v.voter_id = f.voter_id
            WHERE f.offender_face_image IS NOT NULL
        """

        if officer["role"] == "RO":
            cur.execute(base_query + " AND v.constituency = %s ORDER BY f.timestamp DESC LIMIT 200",
                        (officer["constituency"],))
        else:
            cur.execute(base_query + " ORDER BY f.timestamp DESC LIMIT 200")

        entries = []
        for row in cur.fetchall():
            ts, voter_id, booth_id, constituency, fraud_type, details, evidence_path, ov_booth, ov_ts = row
            original_vote = OriginalVote(booth_id=ov_booth, timestamp=ov_ts) if ov_booth and ov_ts else None
            entries.append(EvidenceEntry(
                timestamp=ts, voter_id=voter_id, booth_id=booth_id, constituency=constituency,
                fraud_type=fraud_type, details=details,
                evidence_photo_url=f"/api/admin/evidence/{os.path.basename(evidence_path)}",
                original_vote=original_vote,
            ))
        return entries
    finally:
        cur.close()
        conn.close()


@router.get("/api/admin/evidence/{filename}")
def get_evidence_photo(filename: str, officer: dict = Depends(require_role("RO", "CEO"))):
    # basename() strips any path components the client might sneak in
    # (e.g. "../../etc/passwd") so this can only ever resolve inside EVIDENCE_DIR.
    safe_name = os.path.basename(filename)
    path = os.path.join(EVIDENCE_DIR, safe_name)

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Evidence photo not found.")

    with open(path, "rb") as f:
        ciphertext = f.read()

    return Response(content=decrypt_bytes(ciphertext), media_type="image/jpeg")