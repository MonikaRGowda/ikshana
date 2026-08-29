from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_election_db

router = APIRouter()

class AuditEntry(BaseModel):
    timestamp: str
    voter_id: str
    booth_id: str
    status: str
    fraud_type: Optional[str] = None
    details: Optional[str] = None

@router.get("/audit-log", response_model=List[AuditEntry])
async def get_audit_log():
    conn = get_election_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT 
                timestamp::text,
                voter_id,
                booth_id,
                fraud_type,
                details
            FROM fraud_log
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        rows = cur.fetchall()

        return [
            AuditEntry(
                timestamp=row[0],
                voter_id=row[1],
                booth_id=row[2],
                status="fraud_detected",
                fraud_type=row[3],
                details=row[4],
            )
            for row in rows
        ]

    finally:
        cur.close()
        conn.close()
