"""
Data endpoints for the admin-ro page - everything here is scoped to the
logged-in RO's own constituency via require_role("RO"), which returns
the officer's constituency from their validated session. The frontend
never passes a constituency param; it can't see or affect another RO's
data by construction.
"""

import os
import sys
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import get_election_db
from deps import require_role

router = APIRouter()


class OverviewResponse(BaseModel):
    constituency: str
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


@router.get("/api/admin/ro/overview", response_model=OverviewResponse)
def ro_overview(officer: dict = Depends(require_role("RO"))):
    constituency = officer["constituency"]
    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE has_voted) FROM voters WHERE constituency = %s",
            (constituency,),
        )
        total_voters, voters_authenticated = cur.fetchone()

        cur.execute(
            "SELECT COUNT(DISTINCT booth_id) FROM voters WHERE constituency = %s",
            (constituency,),
        )
        total_booths = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(DISTINCT bs.booth_id)
            FROM booth_sessions bs
            JOIN (SELECT DISTINCT booth_id, constituency FROM voters) v
                ON v.booth_id = bs.booth_id
            WHERE bs.is_active = TRUE AND v.constituency = %s
            """,
            (constituency,),
        )
        active_booths = cur.fetchone()[0]

        return OverviewResponse(
            constituency=constituency,
            total_voters=total_voters or 0,
            voters_authenticated=voters_authenticated or 0,
            active_booths=active_booths or 0,
            total_booths=total_booths or 0,
        )
    finally:
        cur.close()
        conn.close()


@router.get("/api/admin/ro/fraud-log", response_model=List[FraudLogEntry])
def ro_fraud_log(officer: dict = Depends(require_role("RO"))):
    constituency = officer["constituency"]
    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                f.id,
                f.timestamp::text,
                f.voter_id,
                f.booth_id,
                f.fraud_type,
                f.details,
                f.offender_face_image,
                f.original_vote_booth_id,
                f.original_vote_timestamp::text,
                f.match_score,
                f.match_metric,
                f.review_status
            FROM fraud_log f
            JOIN voters v ON v.voter_id = f.voter_id
            WHERE v.constituency = %s
            ORDER BY f.timestamp DESC
            LIMIT 200
            """,
            (constituency,),
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


@router.post("/api/admin/fraud-log/{fraud_id}/review")
def review_fraud_log(fraud_id: int, payload: dict, officer: dict = Depends(require_role("RO", "CEO"))):
    status = payload.get("status")
    note = payload.get("note")
    if status not in {"confirmed", "false_positive"}:
        return {"status": "error", "message": "Invalid review status."}

    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE fraud_log
            SET review_status = %s,
                review_note = %s,
                reviewed_at = CURRENT_TIMESTAMP,
                reviewed_by = %s
            WHERE id = %s
            """,
            (status, note or None, officer["officer_id"], fraud_id),
        )
        conn.commit()
        return {"status": "ok", "message": "Fraud review saved."}
    except Exception as exc:  # pragma: no cover
        conn.rollback()
        return {"status": "error", "message": str(exc)}
    finally:
        cur.close()
        conn.close()


class AccuracySummary(BaseModel):
    scope: str
    total_flagged: int
    total_authenticated: int
    detection_rate: Optional[float] = None
    reviewed_count: int
    confirmed_count: int
    false_positive_count: int
    unreviewed_count: int
    precision: Optional[float] = None
    avg_fingerprint_score: Optional[float] = None
    avg_face_distance: Optional[float] = None


@router.get("/api/admin/accuracy", response_model=AccuracySummary)
def admin_accuracy(officer: dict = Depends(require_role("RO", "CEO"))):
    conn = get_election_db()
    cur = conn.cursor()
    try:
        if officer["role"] == "RO":
            constituency = officer["constituency"]
            total_flagged = cur.execute(
                "SELECT COUNT(*) FROM fraud_log f JOIN voters v ON v.voter_id = f.voter_id WHERE v.constituency = %s",
                (constituency,),
            )
            total_flagged = cur.fetchone()[0]
            total_authenticated = cur.execute(
                "SELECT COUNT(*) FROM voters WHERE constituency = %s AND has_voted = TRUE",
                (constituency,),
            )
            total_authenticated = cur.fetchone()[0]
            reviewed_rows = cur.execute(
                "SELECT COUNT(*), COUNT(*) FILTER (WHERE review_status = 'confirmed'), COUNT(*) FILTER (WHERE review_status = 'false_positive'), COUNT(*) FILTER (WHERE review_status IS NULL) FROM fraud_log f JOIN voters v ON v.voter_id = f.voter_id WHERE v.constituency = %s",
                (constituency,),
            )
            reviewed_count, confirmed_count, false_positive_count, unreviewed_count = cur.fetchone()
            detection_rate = (total_flagged / max(total_authenticated + total_flagged, 1)) if (total_authenticated + total_flagged) else None
            precision = None if reviewed_count == 0 else (confirmed_count / reviewed_count) if reviewed_count else None
            avg_fp = cur.execute(
                "SELECT AVG(match_score) FROM fraud_log f JOIN voters v ON v.voter_id = f.voter_id WHERE v.constituency = %s AND match_metric = 'fingerprint_score'",
                (constituency,),
            )
            avg_fingerprint_score = cur.fetchone()[0]
            avg_fd = cur.execute(
                "SELECT AVG(match_score) FROM fraud_log f JOIN voters v ON v.voter_id = f.voter_id WHERE v.constituency = %s AND match_metric = 'face_distance'",
                (constituency,),
            )
            avg_face_distance = cur.fetchone()[0]
            return AccuracySummary(
                scope="constituency",
                total_flagged=total_flagged,
                total_authenticated=total_authenticated,
                detection_rate=detection_rate,
                reviewed_count=reviewed_count or 0,
                confirmed_count=confirmed_count or 0,
                false_positive_count=false_positive_count or 0,
                unreviewed_count=unreviewed_count or 0,
                precision=precision,
                avg_fingerprint_score=avg_fingerprint_score,
                avg_face_distance=avg_face_distance,
            )

        total_flagged = cur.execute("SELECT COUNT(*) FROM fraud_log")
        total_flagged = cur.fetchone()[0]
        total_authenticated = cur.execute("SELECT COUNT(*) FROM voters WHERE has_voted = TRUE")
        total_authenticated = cur.fetchone()[0]
        reviewed_rows = cur.execute(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE review_status = 'confirmed'), COUNT(*) FILTER (WHERE review_status = 'false_positive'), COUNT(*) FILTER (WHERE review_status IS NULL) FROM fraud_log"
        )
        reviewed_count, confirmed_count, false_positive_count, unreviewed_count = cur.fetchone()
        detection_rate = (total_flagged / max(total_authenticated + total_flagged, 1)) if (total_authenticated + total_flagged) else None
        precision = None if reviewed_count == 0 else (confirmed_count / reviewed_count) if reviewed_count else None
        avg_fp = cur.execute("SELECT AVG(match_score) FROM fraud_log WHERE match_metric = 'fingerprint_score'")
        avg_fingerprint_score = cur.fetchone()[0]
        avg_fd = cur.execute("SELECT AVG(match_score) FROM fraud_log WHERE match_metric = 'face_distance'")
        avg_face_distance = cur.fetchone()[0]
        return AccuracySummary(
            scope="global",
            total_flagged=total_flagged,
            total_authenticated=total_authenticated,
            detection_rate=detection_rate,
            reviewed_count=reviewed_count or 0,
            confirmed_count=confirmed_count or 0,
            false_positive_count=false_positive_count or 0,
            unreviewed_count=unreviewed_count or 0,
            precision=precision,
            avg_fingerprint_score=avg_fingerprint_score,
            avg_face_distance=avg_face_distance,
        )
    finally:
        cur.close()
        conn.close()


@router.get("/api/admin/ro/booths", response_model=List[BoothInfo])
def ro_booths(officer: dict = Depends(require_role("RO"))):
    constituency = officer["constituency"]
    conn = get_election_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                v.booth_id,
                CASE WHEN bs.booth_id IS NOT NULL THEN 'active' ELSE 'inactive' END,
                bo.name
            FROM (SELECT DISTINCT booth_id FROM voters WHERE constituency = %s) v
            LEFT JOIN (SELECT DISTINCT booth_id FROM booth_sessions WHERE is_active = TRUE) bs
                ON bs.booth_id = v.booth_id
            LEFT JOIN booth_officers bo
                ON bo.assigned_booth = v.booth_id AND bo.role = 'BLO' AND bo.is_active = TRUE
            ORDER BY v.booth_id
            """,
            (constituency,),
        )
        return [
            BoothInfo(booth_id=r[0], status=r[1], officer_name=r[2])
            for r in cur.fetchall()
        ]
    finally:
        cur.close()
        conn.close()
        