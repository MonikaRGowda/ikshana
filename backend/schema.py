"""
Central place for idempotent schema migrations that aren't tied to a
single request handler (unlike booth_sessions, which is created lazily
inside booth.py today). Run automatically on app startup — see main.py.
"""

from database import get_election_db


def migrate_officer_roles():
    """
    Adds role-based access control fields to booth_officers:
      - role:         BLO / RO / CEO  (defaults existing rows to BLO,
                       since the app has so far only supported booth-level
                       login — promote specific officers to RO/CEO with
                       scripts/create_officer.py)
      - constituency: which constituency an RO is scoped to (NULL for
                       BLO/CEO, who don't need constituency scoping)
      - email:        needed for OTP delivery on RO/CEO login (Phase 2)
    Safe to run multiple times.
    """
    conn = get_election_db()
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        "ALTER TABLE booth_officers "
        "ADD COLUMN IF NOT EXISTS role VARCHAR(10) NOT NULL DEFAULT 'BLO'"
    )
    cur.execute(
        "ALTER TABLE booth_officers "
        "ADD COLUMN IF NOT EXISTS constituency VARCHAR(100)"
    )
    cur.execute(
        "ALTER TABLE booth_officers "
        "ADD COLUMN IF NOT EXISTS email VARCHAR(255)"
    )

    # Add a CHECK constraint on role if it isn't already there
    cur.execute(
        "SELECT 1 FROM pg_constraint WHERE conname = 'booth_officers_role_check'"
    )
    if not cur.fetchone():
        cur.execute(
            "ALTER TABLE booth_officers "
            "ADD CONSTRAINT booth_officers_role_check "
            "CHECK (role IN ('BLO', 'RO', 'CEO'))"
        )

    cur.close()
    conn.close()
    print("booth_officers: role / constituency / email columns ready.")


def migrate_password_hash_length():
    """
    password_hash was VARCHAR(64), sized for a SHA-256 hex digest.
    Argon2 hashes are longer (~95-100 chars) — widen the column so the
    new hashing scheme (security.py) fits.
    """
    conn = get_election_db()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("ALTER TABLE booth_officers ALTER COLUMN password_hash TYPE VARCHAR(255)")
    cur.close()
    conn.close()
    print("booth_officers: password_hash widened for argon2.")


def migrate_admin_auth_tables():
    """
    Tables for RO/CEO login: short-lived OTP codes, server-side admin
    sessions (looked up by hashed token from an httpOnly cookie), and
    basic lockout tracking on booth_officers to slow down brute force.
    """
    conn = get_election_db()
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS otp_codes (
            id          SERIAL PRIMARY KEY,
            officer_id  VARCHAR(20) NOT NULL,
            code_hash   VARCHAR(64) NOT NULL,
            expires_at  TIMESTAMP NOT NULL,
            consumed    BOOLEAN NOT NULL DEFAULT FALSE,
            attempts    INTEGER NOT NULL DEFAULT 0,
            created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_sessions (
            id           SERIAL PRIMARY KEY,
            token_hash   VARCHAR(64) NOT NULL UNIQUE,
            officer_id   VARCHAR(20) NOT NULL,
            role         VARCHAR(10) NOT NULL,
            constituency VARCHAR(100),
            ip_address   VARCHAR(45),
            expires_at   TIMESTAMP NOT NULL,
            created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            revoked      BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)

    cur.execute(
        "ALTER TABLE booth_officers "
        "ADD COLUMN IF NOT EXISTS failed_attempts INTEGER NOT NULL DEFAULT 0"
    )
    cur.execute(
        "ALTER TABLE booth_officers "
        "ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP"
    )

    cur.close()
    conn.close()
    print("otp_codes / admin_sessions tables ready; login lockout columns ready.")


def migrate_fraud_log_original_vote():
    """
    Adds columns to reference the ORIGINAL vote when a fraud_log entry is
    a duplicate-vote attempt. Columns only - the logic to populate them
    lives in biometric.py's _log_fraud call sites (Phase 3 bug fix), so
    these will read as NULL until that lands.
    """
    conn = get_election_db()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "ALTER TABLE fraud_log ADD COLUMN IF NOT EXISTS original_vote_booth_id VARCHAR(10)"
    )
    cur.execute(
        "ALTER TABLE fraud_log ADD COLUMN IF NOT EXISTS original_vote_timestamp TIMESTAMP"
    )
    cur.close()
    conn.close()
    print("fraud_log: original_vote_booth_id / original_vote_timestamp columns ready.")


def migrate_fraud_review_fields():
    """Adds review metadata and match data for fraud review and accuracy reporting."""
    conn = get_election_db()
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT to_regclass('public.fraud_log')")
    if not cur.fetchone()[0]:
        cur.close()
        conn.close()
        print("fraud_log table not present yet; skipping review metadata migration.")
        return

    cur.execute("ALTER TABLE fraud_log ADD COLUMN IF NOT EXISTS match_score DOUBLE PRECISION")
    cur.execute("ALTER TABLE fraud_log ADD COLUMN IF NOT EXISTS match_metric VARCHAR(30)")
    cur.execute("ALTER TABLE fraud_log ADD COLUMN IF NOT EXISTS review_status VARCHAR(20)")
    cur.execute("ALTER TABLE fraud_log ADD COLUMN IF NOT EXISTS review_note TEXT")
    cur.execute("ALTER TABLE fraud_log ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP")
    cur.execute("ALTER TABLE fraud_log ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(20)")

    cur.execute(
        "SELECT 1 FROM pg_constraint WHERE conname = 'fraud_log_review_status_check'"
    )
    if not cur.fetchone():
        cur.execute(
            "ALTER TABLE fraud_log ADD CONSTRAINT fraud_log_review_status_check "
            "CHECK (review_status IN ('confirmed', 'false_positive'))"
        )

    cur.close()
    conn.close()
    print("fraud_log: review metadata / match metrics columns ready.")


def migrate_election_stepup():
    """
    Step-up auth for election start/stop: otp_codes needs a 'purpose'
    column so a login OTP and a start/stop-action OTP for the same
    officer never get confused with each other. election_action_log is
    a permanent, append-only record of every start/end action taken.
    """
    conn = get_election_db()
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        "ALTER TABLE otp_codes ADD COLUMN IF NOT EXISTS purpose VARCHAR(30) NOT NULL DEFAULT 'login'"
    )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS election_action_log (
            id          SERIAL PRIMARY KEY,
            officer_id  VARCHAR(20) NOT NULL,
            action      VARCHAR(10) NOT NULL,
            reason      TEXT NOT NULL,
            ip_address  VARCHAR(45),
            timestamp   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.close()
    conn.close()
    print("otp_codes.purpose column ready; election_action_log table ready.")


def migrate_voter_pii_columns():
    """
    Encrypted values (crypto.py) are longer than their plaintext
    originals - widen name/phone/address/dob to TEXT so they always fit,
    regardless of whatever narrower type they started as. USING ::TEXT
    handles the cast safely whether the column was already text-like or
    an actual DATE type (dob).
    """
    conn = get_election_db()
    conn.autocommit = True
    cur = conn.cursor()
    for column in ("name", "phone", "address", "dob"):
        cur.execute(f"ALTER TABLE voters ALTER COLUMN {column} TYPE TEXT USING {column}::TEXT")
    cur.close()
    conn.close()
    print("voters: name/phone/address/dob widened to TEXT for encrypted values.")


def run_migrations():
    migrate_officer_roles()
    migrate_password_hash_length()
    migrate_admin_auth_tables()
    migrate_fraud_log_original_vote()
    migrate_fraud_review_fields()
    migrate_election_stepup()
    migrate_voter_pii_columns()


if __name__ == "__main__":
    run_migrations()