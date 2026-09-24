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
from crypto import decrypt_field, encrypt_field, encrypt_bytes, decrypt_bytes
from realtime import broadcast_booth_event
from biometrics.face import decode_base64_image, find_matching_face, get_face_embedding, cosine_distance
from biometrics.fingerprint import capture_iso, find_matching_voter, match_iso

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
        SELECT voter_id, name, has_voted, booth_id
        FROM voters WHERE voter_id = %s
        FOR UPDATE
        """,
        (voter_id.upper(),),
    )
    row = cur.fetchone()
    if not row:
        return None
    voter_id, name, has_voted, assigned_booth = row
    return voter_id, decrypt_field(name), has_voted, assigned_booth


def _load_stored_records(cur):
    cur.execute(
        """
        SELECT voter_id, fingerprint_iso, face_embedding, booth_id, timestamp
        FROM biometric_log
        """
    )
    records = cur.fetchall()
    stored_fingerprints = [
        {"voter_id": record[0], "iso_template": decrypt_bytes(bytes(record[1])), "booth_id": record[3], "timestamp": record[4]}
        for record in records
        if record[1]
    ]
    stored_faces = [
        {"voter_id": record[0], "face_embedding": decrypt_field(record[2]), "booth_id": record[3], "timestamp": record[4]}
        for record in records
        if record[2]
    ]
    return stored_fingerprints, stored_faces


def _get_original_vote(voter_id: str):
    """
    Looks up when/where a voter originally voted, by querying biometric_log
    directly. Used for the has_voted short-circuit paths below, which run
    BEFORE biometric_conn is normally opened - so this opens its own
    connection just for this lookup. Returns (booth_id, timestamp) or None.
    """
    conn = None
    cur = None
    try:
        conn = get_biometric_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT booth_id, timestamp FROM biometric_log WHERE voter_id = %s ORDER BY timestamp ASC LIMIT 1",
            (voter_id,),
        )
        return cur.fetchone()
    except Exception as e:
        print(f"Could not look up original vote for {voter_id}: {e}")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def _encrypt_evidence_file(path: str) -> None:
    """
    Encrypts a just-written evidence photo in place, so the JPEG never
    sits on disk in plaintext even momentarily longer than necessary.
    evidence.py decrypts on read.
    """
    with open(path, "rb") as f:
        plaintext = f.read()
    with open(path, "wb") as f:
        f.write(encrypt_bytes(plaintext))


def _save_fraud_evidence(face_image_b64: Optional[str], voter_id: str) -> Optional[str]:
    """Persist a fraud evidence photo for any fraud outcome and return its DB path."""
    if not face_image_b64:
        return None

    evidence_path = f"evidence/fraud_{voter_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    if not decode_base64_image(face_image_b64, evidence_path):
        print(f"Could not decode face image for fraud evidence ({voter_id}); logging without a photo.")
        return None

    _encrypt_evidence_file(evidence_path)
    return evidence_path


def _fingerprint_score(candidate_iso: Optional[bytes], stored_iso: Optional[bytes]) -> tuple[bool, Optional[int]]:
    if not candidate_iso or not stored_iso:
        return False, None
    if candidate_iso == stored_iso:
        return True, 1000
    try:
        is_match, score = match_iso(candidate_iso, stored_iso)
        return bool(is_match), int(score) if score is not None else None
    except Exception:
        return False, None


def _fingerprint_matches(candidate_iso: Optional[bytes], stored_iso: Optional[bytes]) -> bool:
    return _fingerprint_score(candidate_iso, stored_iso)[0]


def _face_distance(candidate_embedding: Optional[list], stored_embedding: Optional[str | list]) -> tuple[bool, Optional[float]]:
    if not candidate_embedding or not stored_embedding:
        return False, None
    try:
        target = json.loads(stored_embedding) if isinstance(stored_embedding, str) else stored_embedding
        distance = float(cosine_distance(candidate_embedding, target))
        return bool(distance < 0.4), distance
    except Exception:
        return False, None


def _face_matches(candidate_embedding: Optional[list], stored_embedding: Optional[str | list]) -> bool:
    return _face_distance(candidate_embedding, stored_embedding)[0]


def classify_fraud(
    voter_id: str,
    fingerprint_iso: Optional[bytes] = None,
    face_embedding: Optional[list] = None,
    stored_fingerprints: Optional[list[dict]] = None,
    stored_faces: Optional[list[dict]] = None,
) -> Optional[dict]:
    """Categorise fraud according to the required rules:
      - same biometric + same Voter ID -> Duplicate Voting
      - same biometric + different Voter ID -> Identity Fraud
      - different biometric + same Voter ID -> Voter ID Forgery

    Every returned dict includes original_vote_booth_id/timestamp from
    the matched record (when there is one) - these were previously
    computed and then discarded, silently losing that data for any
    fraud caught here rather than via the older has_voted/fp_match path.
    """
    stored_fingerprints = stored_fingerprints or []
    stored_faces = stored_faces or []

    voter_key = str(voter_id).upper()

    own_fp_record = next(
        (record for record in stored_fingerprints if str(record.get("voter_id", "")).upper() == voter_key),
        None,
    )
    own_face_record = next(
        (record for record in stored_faces if str(record.get("voter_id", "")).upper() == voter_key),
        None,
    )

    if own_fp_record and fingerprint_iso:
        fp_match, fp_score = _fingerprint_score(fingerprint_iso, own_fp_record.get("iso_template"))
        if fp_match:
            return {
                "fraud_type": "Duplicate Voting",
                "message": f"Fingerprint matches the same voter {voter_id}. Duplicate Voting detected.",
                "match_metric": "fingerprint_score",
                "match_score": fp_score,
                "original_vote_booth_id": own_fp_record.get("booth_id"),
                "original_vote_timestamp": own_fp_record.get("timestamp"),
            }

    if own_face_record and face_embedding:
        face_match, face_distance = _face_distance(face_embedding, own_face_record.get("face_embedding"))
        if face_match:
            return {
                "fraud_type": "Duplicate Voting",
                "message": f"Face matches the same voter {voter_id}. Duplicate Voting detected.",
                "match_metric": "face_distance",
                "match_score": round(face_distance, 6) if face_distance is not None else None,
                "original_vote_booth_id": own_face_record.get("booth_id"),
                "original_vote_timestamp": own_face_record.get("timestamp"),
            }

    for record in stored_fingerprints:
        if str(record.get("voter_id", "")).upper() == voter_key:
            continue
        if fingerprint_iso:
            fp_match, fp_score = _fingerprint_score(fingerprint_iso, record.get("iso_template"))
            if fp_match:
                return {
                    "fraud_type": "Identity Fraud",
                    "message": f"Fingerprint matches voter {record.get('voter_id')}. Identity fraud detected.",
                    "match_metric": "fingerprint_score",
                    "match_score": fp_score,
                    "original_vote_booth_id": record.get("booth_id"),
                    "original_vote_timestamp": record.get("timestamp"),
                }

    for record in stored_faces:
        if str(record.get("voter_id", "")).upper() == voter_key:
            continue
        if face_embedding:
            face_match, face_distance = _face_distance(face_embedding, record.get("face_embedding"))
            if face_match:
                return {
                    "fraud_type": "Identity Fraud",
                    "message": f"Face matches voter {record.get('voter_id')}. Identity fraud detected.",
                    "match_metric": "face_distance",
                    "match_score": round(face_distance, 6) if face_distance is not None else None,
                    "original_vote_booth_id": record.get("booth_id"),
                    "original_vote_timestamp": record.get("timestamp"),
                }

    if own_fp_record and fingerprint_iso:
        fp_match, fp_score = _fingerprint_score(fingerprint_iso, own_fp_record.get("iso_template"))
        if not fp_match:
            return {
                "fraud_type": "Voter ID Forgery",
                "message": f"Fingerprint does not match the stored biometric for voter {voter_id}. Voter ID forgery suspected.",
                "match_metric": "fingerprint_score",
                "match_score": fp_score,
                "original_vote_booth_id": own_fp_record.get("booth_id"),
                "original_vote_timestamp": own_fp_record.get("timestamp"),
            }

    if own_face_record and face_embedding:
        face_match, face_distance = _face_distance(face_embedding, own_face_record.get("face_embedding"))
        if not face_match:
            return {
                "fraud_type": "Voter ID Forgery",
                "message": f"Face does not match the stored biometric for voter {voter_id}. Voter ID forgery suspected.",
                "match_metric": "face_distance",
                "match_score": round(face_distance, 6) if face_distance is not None else None,
                "original_vote_booth_id": own_face_record.get("booth_id"),
                "original_vote_timestamp": own_face_record.get("timestamp"),
            }

    return None


def _log_fraud(
    cur, voter_id: str, booth_id: str, fraud_type: str, message: str,
    evidence_path: Optional[str] = None,
    original_vote_booth_id: Optional[str] = None,
    original_vote_timestamp=None,
    match_score: Optional[float] = None,
    match_metric: Optional[str] = None,
) -> None:
    cur.execute(
        """
        INSERT INTO fraud_log
            (voter_id, booth_id, fraud_type, details, offender_face_image,
             original_vote_booth_id, original_vote_timestamp, match_score, match_metric)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (voter_id, booth_id, fraud_type, message, evidence_path,
         original_vote_booth_id, original_vote_timestamp, match_score, match_metric),
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

        voter_id, voter_name, has_voted, assigned_booth = voter

        # Server-side enforcement of booth/constituency correctness -
        # cannot be bypassed by skipping verify-voter, since it's
        # checked again here independently.
        if assigned_booth != request.booth_id:
            return FingerprintResponse(
                status="failed",
                message=f"{voter_name} is not registered at this booth. Please direct them to Booth {assigned_booth}.",
            )

        iso_bytes = capture_iso()
        if iso_bytes is None:
            return FingerprintResponse(status="failed", message="Fingerprint capture failed. Try again.")

        # Option B: don't block here. Work out what the verdict WOULD be,
        # store it alongside the pending fingerprint, and let the officer
        # proceed to the face-scan step regardless - that's where a photo
        # can actually be captured, so that's where fraud now gets logged.
        suspected_fraud = None

        if has_voted:
            original_vote = _get_original_vote(voter_id)
            ov_booth, ov_timestamp = original_vote if original_vote else (None, None)
            suspected_fraud = {
                "fraud_type": "Duplicate Voting",
                "message": f"{voter_name} has already voted. Duplicate attempt blocked.",
                "original_vote_booth_id": ov_booth,
                "original_vote_timestamp": ov_timestamp,
            }
        else:
            biometric_conn = get_biometric_db()
            biometric_cur = biometric_conn.cursor()
            stored_fingerprints, _ = _load_stored_records(biometric_cur)
            fp_match = find_matching_voter(iso_bytes, stored_fingerprints)

            if fp_match:
                if fp_match["voter_id"] == voter_id:
                    fraud_type = "Duplicate Voting"
                    message = f"{voter_name} has already voted. Duplicate attempt blocked."
                else:
                    fraud_type = "Identity Fraud"
                    message = f"Fingerprint matches voter {fp_match['voter_id']}. Identity fraud detected."
                suspected_fraud = {
                    "fraud_type": fraud_type,
                    "message": message,
                    "original_vote_booth_id": fp_match.get("booth_id"),
                    "original_vote_timestamp": fp_match.get("timestamp"),
                }

        pending_fingerprints[_pending_key(voter_id, request.session_token)] = {
            "iso": iso_bytes,
            "booth_id": request.booth_id,
            "created_at": datetime.now(),
            "suspected_fraud": suspected_fraud,
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

        voter_id, voter_name, has_voted, assigned_booth = voter

        if assigned_booth != request.booth_id:
            return BiometricVerifyResponse(
                status="failed",
                message=f"{voter_name} is not registered at this booth. Please direct them to Booth {assigned_booth}.",
            )

        pending = pending_fingerprints.get(pending_key)
        if not pending or pending["booth_id"] != request.booth_id:
            return BiometricVerifyResponse(
                status="failed",
                message="Fingerprint scan is required before face scan. Please retry fingerprint capture.",
            )

        if pending.get("suspected_fraud"):
            fraud_info = pending["suspected_fraud"]
        elif has_voted:
            # Race-condition safety net: has_voted became true AFTER the
            # fingerprint step ran (e.g. voted at another booth in between).
            original_vote = _get_original_vote(voter_id)
            ov_booth, ov_timestamp = original_vote if original_vote else (None, None)
            fraud_info = {
                "fraud_type": "Duplicate Voting",
                "message": f"{voter_name} has already voted. Duplicate attempt blocked.",
                "original_vote_booth_id": ov_booth, "original_vote_timestamp": ov_timestamp,
            }
        else:
            fraud_info = None

        biometric_conn = get_biometric_db()
        biometric_cur = biometric_conn.cursor()

        if not decode_base64_image(request.face_image, temp_face_path):
            return BiometricVerifyResponse(status="failed", message="Face image decode failed. Try again.")

        face_embedding = get_face_embedding(temp_face_path)
        if face_embedding is None:
            return BiometricVerifyResponse(status="failed", message="Face not detected clearly. Try again.")

        stored_fingerprints, stored_faces = _load_stored_records(biometric_cur)
        classified_fraud = classify_fraud(
            voter_id,
            pending.get("iso"),
            face_embedding,
            stored_fingerprints,
            stored_faces,
        )

        if fraud_info and classified_fraud is None:
            classified_fraud = {
                "fraud_type": fraud_info["fraud_type"],
                "message": fraud_info["message"],
            }

        if classified_fraud is not None:
            evidence_path = _save_fraud_evidence(request.face_image, voter_id)
            _log_fraud(
                election_cur,
                voter_id,
                request.booth_id,
                classified_fraud["fraud_type"],
                classified_fraud["message"],
                evidence_path,
                original_vote_booth_id=(
                    classified_fraud.get("original_vote_booth_id")
                    or (fraud_info.get("original_vote_booth_id") if fraud_info else None)
                ),
                original_vote_timestamp=(
                    classified_fraud.get("original_vote_timestamp")
                    or (fraud_info.get("original_vote_timestamp") if fraud_info else None)
                ),
                match_score=classified_fraud.get("match_score"),
                match_metric=classified_fraud.get("match_metric"),
            )
            election_conn.commit()
            pending_fingerprints.pop(pending_key, None)
            await _emit_fraud(voter_id, voter_name, request.booth_id, classified_fraud["fraud_type"], classified_fraud["message"])
            return BiometricVerifyResponse(
                status="fraud_detected",
                message=classified_fraud["message"],
                voter_name=voter_name,
                fraud_type=classified_fraud["fraud_type"],
            )

        # Fall back to legacy same-person duplicate detection if no biometric mismatch was found.
        face_match = find_matching_face(face_embedding, stored_faces)

        if face_match:
            if face_match["voter_id"] == voter_id:
                fraud_type = "Duplicate Voting"
                message = f"{voter_name} has already voted. Duplicate attempt blocked."
            else:
                fraud_type = "Identity Fraud"
                message = f"Face matches voter {face_match['voter_id']}. Identity fraud detected."

            evidence_path = _save_fraud_evidence(request.face_image, voter_id)
            _log_fraud(
                election_cur, voter_id, request.booth_id, fraud_type, message, evidence_path,
                original_vote_booth_id=face_match.get("booth_id"),
                original_vote_timestamp=face_match.get("timestamp"),
                match_score=float(cosine_distance(face_embedding, json.loads(face_match["face_embedding"]))),
                match_metric="face_distance",
            )
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
            (
                voter_id, request.booth_id,
                encrypt_bytes(pending["iso"]),
                encrypt_field(json.dumps(face_embedding)),
            ),
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