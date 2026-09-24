"""
One-time bootstrap CLI for creating or promoting an officer account,
since there's no logged-in CEO yet to use the (future) admin-ceo
registration screen for the very first CEO/RO accounts.

Run from backend/:
    python scripts/create_officer.py --officer-id ... --name ... \
        --password ... --role ... --email ...

Passwords are hashed with argon2 (security.py) — the same scheme used
by the rest of the app.
"""

import argparse
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_election_db  # noqa: E402
from security import hash_password  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Create or promote an officer account")
    parser.add_argument("--officer-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", required=True, choices=["BLO", "RO", "CEO"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--constituency", default=None, help="Required for RO")
    parser.add_argument("--assigned-booth", default=None, help="Required for BLO")
    args = parser.parse_args()

    if args.role == "RO" and not args.constituency:
        parser.error("--constituency is required for role RO")
    if args.role == "BLO" and not args.assigned_booth:
        parser.error("--assigned-booth is required for role BLO")

    officer_id = args.officer_id.upper()
    password_hash = hash_password(args.password)

    conn = get_election_db()
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT 1 FROM booth_officers WHERE officer_id = %s", (officer_id,)
        )
        exists = cur.fetchone()

        if exists:
            cur.execute(
                """
                UPDATE booth_officers
                SET name = %s, password_hash = %s, role = %s, email = %s,
                    constituency = %s, assigned_booth = %s, is_active = TRUE
                WHERE officer_id = %s
                """,
                (
                    args.name, password_hash, args.role, args.email,
                    args.constituency, args.assigned_booth, officer_id,
                ),
            )
            print(f"Updated existing officer {officer_id} -> role {args.role}")
        else:
            cur.execute(
                """
                INSERT INTO booth_officers
                    (officer_id, name, designation, password_hash, role,
                     email, constituency, assigned_booth, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                """,
                (
                    officer_id, args.name, args.role, password_hash, args.role,
                    args.email, args.constituency, args.assigned_booth,
                ),
            )
            print(f"Created new officer {officer_id} with role {args.role}")

        conn.commit()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()