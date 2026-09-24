"""
Data endpoints for the admin-ceo page - global (no constituency scoping),
guarded by require_role("CEO").
"""

import os
import sys
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import get_election_db
from deps import require_role
from security import hash_password

router = APIRouter()


class OverviewResponse(BaseModel):
    total_voters: int
    voters_authenticated: int
    active_booths: int
    total_booths: int


class OriginalVote(BaseModel):
    booth_id: str
    timestamp: str


class FraudLogEntry(BaseModel):
    id: int
    timestamp: str
    voter_id: str
    booth_id: str
    fraud_type: Optional[str] = None
    details: Optional[str] = None
    evidence_photo_url: Optional[str] = None
    original_vote: Optional[OriginalVote] = None
    match_score: Optional[float] = None
    match_metric: Optional[str] = None
    review_status: Optional[str] = None


class BoothInfo(BaseModel):
    booth_id: str
    status: str
    officer_name: Optional[str] = None
    constituency: Optional[str] = None


class OfficerInfo(BaseModel):
    officer_id: str
    name: str
    role: str
    assigned_booth: Optional[str] = None
    constituency: Optional[str] = None


class RegisterOfficerRequest(BaseModel):
    officer_id: str
    name: str
    password: str
    assigned_booth: str
    constituency: Optional[str] = None


class RegisterOfficerResponse(BaseModel):
    status: str  # "ok" | "duplicate" | "error"
    message: str


@router.get("/api/admin/ceo/overview", response_model=OverviewResponse)
def ceo_overview(officer: dict = Depends(require_role("CEO"))):
    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE has_voted) FROM voters")
        total_voters, voters_authenticated = cur.fetchone()

        cur.execute("SELECT COUNT(DISTINCT booth_id) FROM voters")
        total_booths = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT booth_id) FROM booth_sessions WHERE is_active = TRUE")
        active_booths = cur.fetchone()[0]

        return OverviewResponse(
            total_voters=total_voters or 0,
            voters_authenticated=voters_authenticated or 0,
            active_booths=active_booths or 0,
            total_booths=total_booths or 0,
        )
    finally:
        cur.close()
        conn.close()


@router.get("/api/admin/ceo/fraud-log", response_model=List[FraudLogEntry])
def ceo_fraud_log(officer: dict = Depends(require_role("CEO"))):
    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                id, timestamp::text, voter_id, booth_id, fraud_type, details,
                offender_face_image, original_vote_booth_id, original_vote_timestamp::text,
                match_score, match_metric, review_status
            FROM fraud_log
            ORDER BY timestamp DESC
            LIMIT 200
            """
        )
        rows = cur.fetchall()

        entries = []
        for row in rows:
            fraud_id, ts, voter_id, booth_id, fraud_type, details, evidence_path, ov_booth, ov_ts, match_score, match_metric, review_status = row
            evidence_url = f"/api/admin/evidence/{os.path.basename(evidence_path)}" if evidence_path else None
            original_vote = OriginalVote(booth_id=ov_booth, timestamp=ov_ts) if ov_booth and ov_ts else None
            entries.append(FraudLogEntry(
                id=fraud_id,
                timestamp=ts, voter_id=voter_id, booth_id=booth_id,
                fraud_type=fraud_type, details=details,
                evidence_photo_url=evidence_url, original_vote=original_vote,
                match_score=match_score,
                match_metric=match_metric,
                review_status=review_status,
            ))
        return entries
    finally:
        cur.close()
        conn.close()


@router.get("/api/admin/ceo/booths", response_model=List[BoothInfo])
def ceo_booths(officer: dict = Depends(require_role("CEO"))):
    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                v.booth_id,
                CASE WHEN bs.booth_id IS NOT NULL THEN 'active' ELSE 'inactive' END,
                bo.name,
                v.constituency
            FROM (SELECT DISTINCT booth_id, constituency FROM voters) v
            LEFT JOIN (SELECT DISTINCT booth_id FROM booth_sessions WHERE is_active = TRUE) bs
                ON bs.booth_id = v.booth_id
            LEFT JOIN booth_officers bo
                ON bo.assigned_booth = v.booth_id AND bo.role = 'BLO' AND bo.is_active = TRUE
            ORDER BY v.booth_id
            """
        )
        return [
            BoothInfo(booth_id=r[0], status=r[1], officer_name=r[2], constituency=r[3])
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


@router.get("/api/admin/ceo/officers", response_model=List[OfficerInfo])
def ceo_officers(officer: dict = Depends(require_role("CEO"))):
    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT officer_id, name, role, assigned_booth, constituency
            FROM booth_officers
            WHERE role = 'BLO'
            ORDER BY assigned_booth
            """
        )
        return [
            OfficerInfo(officer_id=r[0], name=r[1], role=r[2], assigned_booth=r[3], constituency=r[4])
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()


@router.post("/api/admin/ceo/officers/register", response_model=RegisterOfficerResponse)
def ceo_register_officer(request: RegisterOfficerRequest, officer: dict = Depends(require_role("CEO"))):
    officer_id = request.officer_id.strip().upper()
    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM booth_officers WHERE officer_id = %s", (officer_id,))
        if cur.fetchone():
            return RegisterOfficerResponse(status="duplicate", message=f"Officer ID {officer_id} already exists.")

        cur.execute(
            """
            INSERT INTO booth_officers
                (officer_id, name, designation, password_hash, role, assigned_booth, constituency, is_active)
            VALUES (%s, %s, 'Booth Level Officer', %s, 'BLO', %s, %s, TRUE)
            """,
            (officer_id, request.name, hash_password(request.password), request.assigned_booth, request.constituency),
        )
        conn.commit()
        return RegisterOfficerResponse(status="ok", message=f"Officer {officer_id} registered.")
    except Exception as e:
        conn.rollback()
        return RegisterOfficerResponse(status="error", message=str(e))
    finally:
        cur.close()
        conn.close()