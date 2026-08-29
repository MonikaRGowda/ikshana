from datetime import datetime, timedelta
import json
import os
import psycopg2
import shutil
import sys
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_biometric_db, get_election_db
from realtime import broadcast_booth_event
from biometrics.face import decode_base64_image, find_matching_face, get_face_embedding
from biometrics.fingerprint import capture_iso, find_matching_voter

router = APIRouter()

FINGERPRINT_TTL = timedelta(minutes=5)
pending_fingerprints: dict[str, dict] = {}


class FingerprintRequest(BaseModel):
    voter_id: str
    booth_id: str
    session_token: str


class FingerprintResponse(BaseModel):
    status: str
    message: str
    voter_name: Optional[str] = None
    fraud_type: Optional[str] = None


class BiometricVerifyRequest(BaseModel):
    voter_id: str
    booth_id: str
    session_token: str
    face_image: str


class BiometricVerifyResponse(BaseModel):
    status: str
    message: str
    voter_name: Optional[str] = None
    fraud_type: Optional[str] = None


def _pending_key(voter_id: str, session_token: str) -> str:
    return f"{voter_id.upper()}:{session_token}"


def _prune_pending_fingerprints() -> None:
    now = datetime.now()
    expired_keys = [
        key
        for key, value in pending_fingerprints.items()
        if now - value["created_at"] > FINGERPRINT_TTL
    ]
    for key in expired_keys:
        pending_fingerprints.pop(key, None)


def _validate_session(cur, session_token: str, booth_id: str) -> bool:
    cur.execute(
        """
        SELECT booth_id FROM booth_sessions
        WHERE session_token = %s AND is_active = TRUE
        """,
        (session_token,),
    )
    row = cur.fetchone()
    return bool(row and row[0] == booth_id)


def _get_voter(cur, voter_id: str):
    cur.execute(
        """
        SELECT voter_id, name, has_voted
        FROM voters WHERE voter_id = %s
        FOR UPDATE
        """,
        (voter_id.upper(),),
    )
    return cur.fetchone()


def _load_stored_records(cur):
    cur.execute(
        """
        SELECT voter_id, fingerprint_iso, face_embedding
        FROM biometric_log
        """
    )
    records = cur.fetchall()
    stored_fingerprints = [
        {"voter_id": record[0], "iso_template": record[1]}
        for record in records
        if record[1]
    ]
    stored_faces = [
        {"voter_id": record[0], "face_embedding": record[2]}
        for record in records
        if record[2]
    ]
    return stored_fingerprints, stored_faces


def _log_fraud(cur, voter_id: str, booth_id: str, fraud_type: str, message: str, evidence_path: Optional[str] = None) -> None:
    cur.execute(
        """
        INSERT INTO fraud_log
            (voter_id, booth_id, fraud_type, details, offender_face_image)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (voter_id, booth_id, fraud_type, message, evidence_path),
    )


async def _emit_fraud(voter_id: str, voter_name: str, booth_id: str, fraud_type: str, message: str) -> None:
    await broadcast_booth_event("fraud_detected", {
        "voter_id": voter_id,
        "voter_name": voter_name,
        "booth_id": booth_id,
        "fraud_type": fraud_type,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    })


async def _emit_authenticated(voter_id: str, voter_name: str, booth_id: str) -> None:
    await broadcast_booth_event("voter_authenticated", {
        "voter_id": voter_id,
        "voter_name": voter_name,
        "booth_id": booth_id,
        "status": "authenticated",
        "timestamp": datetime.now().isoformat(),
    })


async def _emit_election_stats(total_votes: int, active_booths: int) -> None:
    await broadcast_booth_event("election_stats_updated", {
        "total_votes": total_votes,
        "active_booths": active_booths,
    })


def _system_error_response(error: Exception, response_model):
    message = str(error)
    if isinstance(error, psycopg2.OperationalError) and "biometric_db" in message:
        message = "Biometric database is not ready. Start the election before biometric scanning."
    return response_model(status="failed", message=f"System error: {message}")


@router.post("/biometric/fingerprint", response_model=FingerprintResponse)
async def scan_fingerprint(request: FingerprintRequest):
    _prune_pending_fingerprints()

    election_conn = None
    biometric_conn = None
    election_cur = None
    biometric_cur = None

    try:
        election_conn = get_election_db()
        election_cur = election_conn.cursor()

        if not _validate_session(election_cur, request.session_token, request.booth_id):
            return FingerprintResponse(status="failed", message="Invalid session. Please login again.")

        voter = _get_voter(election_cur, request.voter_id)
        if not voter:
            return FingerprintResponse(status="failed", message="Voter not found.")

        voter_id, voter_name, has_voted = voter
        if has_voted:
            fraud_type = "Duplicate Voting"
            message = f"{voter_name} has already voted. Duplicate attempt blocked."
            _log_fraud(election_cur, voter_id, request.booth_id, fraud_type, message)
            election_conn.commit()
            await _emit_fraud(voter_id, voter_name, request.booth_id, fraud_type, message)
            return FingerprintResponse(
                status="fraud_detected",
                message=message,
                voter_name=voter_name,
                fraud_type=fraud_type,
            )

        biometric_conn = get_biometric_db()
        biometric_cur = biometric_conn.cursor()

        iso_bytes = capture_iso()
        if iso_bytes is None:
            return FingerprintResponse(status="failed", message="Fingerprint capture failed. Try again.")

        stored_fingerprints, _ = _load_stored_records(biometric_cur)
        fp_match = find_matching_voter(iso_bytes, stored_fingerprints)

        if fp_match:
            if fp_match["voter_id"] == voter_id:
                fraud_type = "Duplicate Voting"
                message = f"{voter_name} has already voted. Duplicate attempt blocked."
            else:
                fraud_type = "Identity Fraud"
                message = f"Fingerprint matches voter {fp_match['voter_id']}. Identity fraud detected."

            _log_fraud(election_cur, voter_id, request.booth_id, fraud_type, message)
            election_conn.commit()
            await _emit_fraud(voter_id, voter_name, request.booth_id, fraud_type, message)
            return FingerprintResponse(
                status="fraud_detected",
                message=message,
                voter_name=voter_name,
                fraud_type=fraud_type,
            )

        pending_fingerprints[_pending_key(voter_id, request.session_token)] = {
            "iso": iso_bytes,
            "booth_id": request.booth_id,
            "created_at": datetime.now(),
        }

        return FingerprintResponse(
            status="ready",
            message="Fingerprint captured. Now proceed to face scan.",
            voter_name=voter_name,
        )

    except Exception as e:
        print(f"Fingerprint error: {e}")
        return _system_error_response(e, FingerprintResponse)

    finally:
        if election_cur:
            election_cur.close()
        if biometric_cur:
            biometric_cur.close()
        if election_conn:
            election_conn.close()
        if biometric_conn:
            biometric_conn.close()


@router.post("/biometric/verify", response_model=BiometricVerifyResponse)
async def verify_biometric(request: BiometricVerifyRequest):
    _prune_pending_fingerprints()

    election_conn = None
    biometric_conn = None
    election_cur = None
    biometric_cur = None

    os.makedirs("temp", exist_ok=True)
    os.makedirs("evidence", exist_ok=True)
    temp_face_path = f"temp/face_{request.voter_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    pending_key = _pending_key(request.voter_id, request.session_token)

    try:
        election_conn = get_election_db()
        election_cur = election_conn.cursor()

        if not _validate_session(election_cur, request.session_token, request.booth_id):
            return BiometricVerifyResponse(status="failed", message="Invalid session. Please login again.")

        voter = _get_voter(election_cur, request.voter_id)
        if not voter:
            return BiometricVerifyResponse(status="failed", message="Voter not found.")

        voter_id, voter_name, has_voted = voter
        pending = pending_fingerprints.get(pending_key)
        if not pending or pending["booth_id"] != request.booth_id:
            return BiometricVerifyResponse(
                status="failed",
                message="Fingerprint scan is required before face scan. Please retry fingerprint capture.",
            )

        if has_voted:
            fraud_type = "Duplicate Voting"
            message = f"{voter_name} has already voted. Duplicate attempt blocked."
            _log_fraud(election_cur, voter_id, request.booth_id, fraud_type, message)
            election_conn.commit()
            pending_fingerprints.pop(pending_key, None)
            await _emit_fraud(voter_id, voter_name, request.booth_id, fraud_type, message)
            return BiometricVerifyResponse(
                status="fraud_detected",
                message=message,
                voter_name=voter_name,
                fraud_type=fraud_type,
            )

        biometric_conn = get_biometric_db()
        biometric_cur = biometric_conn.cursor()

        if not decode_base64_image(request.face_image, temp_face_path):
            return BiometricVerifyResponse(status="failed", message="Face image decode failed. Try again.")

        face_embedding = get_face_embedding(temp_face_path)
        if face_embedding is None:
            return BiometricVerifyResponse(status="failed", message="Face not detected clearly. Try again.")

        _, stored_faces = _load_stored_records(biometric_cur)
        face_match = find_matching_face(face_embedding, stored_faces)

        if face_match:
            if face_match["voter_id"] == voter_id:
                fraud_type = "Duplicate Voting"
                message = f"{voter_name} has already voted. Duplicate attempt blocked."
            else:
                fraud_type = "Identity Fraud"
                message = f"Face matches voter {face_match['voter_id']}. Identity fraud detected."

            evidence_path = f"evidence/fraud_{voter_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            shutil.copy(temp_face_path, evidence_path)
            _log_fraud(election_cur, voter_id, request.booth_id, fraud_type, message, evidence_path)
            election_conn.commit()
            pending_fingerprints.pop(pending_key, None)
            await _emit_fraud(voter_id, voter_name, request.booth_id, fraud_type, message)
            return BiometricVerifyResponse(
                status="fraud_detected",
                message=message,
                voter_name=voter_name,
                fraud_type=fraud_type,
            )

        biometric_cur.execute(
            """
            INSERT INTO biometric_log
                (voter_id, booth_id, fingerprint_iso, face_embedding)
            VALUES (%s, %s, %s, %s)
            """,
            (voter_id, request.booth_id, pending["iso"], json.dumps(face_embedding)),
        )
        biometric_conn.commit()

        election_cur.execute(
            """
            UPDATE voters SET has_voted = TRUE
            WHERE voter_id = %s
            """,
            (voter_id,),
        )
        election_cur.execute(
            """
            UPDATE election_status
            SET total_votes = COALESCE(total_votes, 0) + 1
            WHERE id = (SELECT id FROM election_status ORDER BY id DESC LIMIT 1)
            RETURNING total_votes, active_booths
            """
        )
        election_stats = election_cur.fetchone()
        election_conn.commit()
        pending_fingerprints.pop(pending_key, None)
        await _emit_authenticated(voter_id, voter_name, request.booth_id)
        if election_stats:
            await _emit_election_stats(*election_stats)
        return BiometricVerifyResponse(
            status="authenticated",
            message=f"{voter_name} successfully authenticated. Proceed to EVM.",
            voter_name=voter_name,
        )

    except Exception as e:
        print(f"Biometric error: {e}")
        return _system_error_response(e, BiometricVerifyResponse)

    finally:
        if os.path.exists(temp_face_path):
            os.remove(temp_face_path)
        if election_cur:
            election_cur.close()
        if biometric_cur:
            biometric_cur.close()
        if election_conn:
            election_conn.close()
        if biometric_conn:
            biometric_conn.close()
