import json
import os

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

# ─── DB CONFIG (from environment — never hardcode credentials here) ───

DB_CONFIG = {
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
}
DB_NAME = os.environ.get("DB_NAME", "election_db")
BIOMETRIC_DB_NAME = os.environ.get(
    "BIOMETRIC_DB_NAME",
    os.environ.get("DB_TEMP_NAME", "biometric_db"),
)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()

# ─── PERMANENT DB (election_db) ───────────────────────────────

def get_election_db():
    return psycopg2.connect(
        dbname=DB_NAME,
        **DB_CONFIG
    )

# ─── EPHEMERAL DB (biometric_db) ──────────────────────────────

def create_biometric_db():
    # Render provides one database; never create another database there.
    if ENVIRONMENT == "production" or BIOMETRIC_DB_NAME == DB_NAME:
        print(f"Using shared database {BIOMETRIC_DB_NAME} for biometric_log")
    else:
        conn = psycopg2.connect(dbname="postgres", **DB_CONFIG)
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (BIOMETRIC_DB_NAME,))
        exists = cur.fetchone()

        if not exists:
            cur.execute(
                sql.SQL("CREATE DATABASE {} ").format(sql.Identifier(BIOMETRIC_DB_NAME))
            )
            print(f"{BIOMETRIC_DB_NAME} created!")
        else:
            print(f"{BIOMETRIC_DB_NAME} already exists")

        cur.close()
        conn.close()

    # Now connect to the configured biometric database and create the table.
    conn2 = psycopg2.connect(dbname=BIOMETRIC_DB_NAME, **DB_CONFIG)
    cur2 = conn2.cursor()

    cur2.execute("""
    CREATE TABLE IF NOT EXISTS biometric_log (
        id                  SERIAL PRIMARY KEY,
        voter_id            VARCHAR(10),
        booth_id            VARCHAR(10),
        fingerprint_iso     BYTEA,
        face_embedding      TEXT,
        timestamp           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
    cur2.execute("ALTER TABLE biometric_log ADD COLUMN IF NOT EXISTS face_embedding TEXT")

    conn2.commit()
    print("biometric_log table ready!")
    cur2.close()
    conn2.close()

def get_biometric_db():
    return psycopg2.connect(
        dbname=BIOMETRIC_DB_NAME,
        **DB_CONFIG
    )

def drop_biometric_db():
    if ENVIRONMENT == "production" or BIOMETRIC_DB_NAME == DB_NAME:
        print("Skipping biometric database drop in the deployed/shared database.")
        return

    conn = psycopg2.connect(dbname="postgres", **DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    # Terminate all active connections to biometric_db first
    cur.execute("""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = %s
    """, (BIOMETRIC_DB_NAME,))

    # Now drop it
    cur.execute(
        sql.SQL("DROP DATABASE IF EXISTS {} ").format(sql.Identifier(BIOMETRIC_DB_NAME))
    )
    print(f"{BIOMETRIC_DB_NAME} dropped and destroyed!")

    cur.close()
    conn.close()

# ─── VOTER SEEDING ─────────────────────────────────────────────

def load_voters():
    if ENVIRONMENT == "production":
        raise RuntimeError("load_voters() is disabled in production.")

    # Load voters.json
    voters_path = os.path.join(os.path.dirname(__file__), "data", "voters.json")
    with open(voters_path, "r") as f:
        voters = json.load(f)

    print(f"Loaded {len(voters)} voters from JSON")

    conn = get_election_db()
    cur = conn.cursor()

    # Clear existing voters first (clean slate)
    cur.execute("TRUNCATE TABLE voters RESTART IDENTITY CASCADE")
    print("Cleared existing voter records")

    # Insert all voters
    inserted = 0
    skipped = 0

    for voter in voters:
        try:
            cur.execute("""
                INSERT INTO voters (
                    voter_id,
                    name,
                    relative_name,
                    relative_type,
                    dob,
                    gender,
                    phone,
                    address,
                    constituency,
                    booth_id,
                    part_number,
                    has_voted
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                voter["voter_id"],
                voter["name"],
                voter["relative_name"],
                voter["relative_type"],
                voter["dob"],
                voter["gender"],
                voter["phone"],
                voter["address"],
                voter["constituency"],
                voter["booth_id"],
                voter["part_number"],
                voter["has_voted"]
            ))
            inserted += 1

        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            skipped += 1
            continue

        conn.commit()

    print(f"Inserted: {inserted} voters")
    print(f"Skipped (duplicate voter_id): {skipped} voters")

    # Verify
    cur.execute("SELECT COUNT(*) FROM voters")
    count = cur.fetchone()[0]
    print(f"Total voters in database: {count}")

    # Show sample
    cur.execute("SELECT voter_id, name, constituency, booth_id FROM voters LIMIT 5")
    rows = cur.fetchall()
    print("\nSample records:")
    for row in rows:
        print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]}")

    cur.close()
    conn.close()

# ─── TEST ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Creating biometric_db...")
    create_biometric_db()

    print("\nConnecting to election_db...")
    conn = get_election_db()
    print("election_db connected!")
    conn.close()

    print("\nAll good! Both databases working.")