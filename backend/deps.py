"""
FastAPI dependencies for RO/CEO route protection. Import require_role(...)
into any router that needs to restrict access - it reads the admin_session
cookie, validates it server-side against admin_sessions, and enforces
role membership. Nothing about authorization is ever trusted from the
frontend alone.
"""

import hashlib

from fastapi import Cookie, HTTPException, status

from database import get_election_db


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_role(*allowed_roles: str):
    """
    Usage:
        @router.post("/some-privileged-route")
        def handler(officer: dict = Depends(require_role("CEO"))):
            ...

    Returns a dict: {officer_id, role, constituency} on success.
    Raises 401 if there's no valid session, 403 if the role doesn't match.
    """

    def _dependency(admin_session: str | None = Cookie(default=None)):
        if not admin_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not logged in.",
            )

        token_hash = _hash_token(admin_session)

        conn = get_election_db()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT officer_id, role, constituency, expires_at, revoked
                FROM admin_sessions
                WHERE token_hash = %s
                """,
                (token_hash,),
            )
            row = cur.fetchone()
        finally:
            cur.close()
            conn.close()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found. Please log in again.",
            )

        officer_id, role, constituency, expires_at, revoked = row

        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked. Please log in again.",
            )

        import datetime
        if expires_at < datetime.datetime.now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please log in again.",
            )

        if allowed_roles and role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires role: {', '.join(allowed_roles)}.",
            )

        return {"officer_id": officer_id, "role": role, "constituency": constituency}

    return _dependency