import psycopg2

# Your postgres credentials
DB_CONFIG = {
    "user": "postgres",
    "password": "postgres_election_2024", 
    "host": "localhost",
    "port": "5432"
}
# ─── PERMANENT DB (election_db) ───────────────────────────────

def get_election_db():
    return psycopg2.connect(
        dbname="election_db",
        **DB_CONFIG
    )

# ─── EPHEMERAL DB (biometric_db) ──────────────────────────────

def create_biometric_db():
    # Connect to default postgres db to create biometric_db
    conn = psycopg2.connect(dbname="postgres", **DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    # Check if it already exists
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'biometric_db'")
    exists = cur.fetchone()

    if not exists:
        cur.execute("CREATE DATABASE biometric_db")
        print("biometric_db created!")
    else:
        print("biometric_db already exists")

    cur.close()
    conn.close()

    # Now connect to biometric_db and create the table
    conn2 = psycopg2.connect(dbname="biometric_db", **DB_CONFIG)
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
        dbname="biometric_db",
        **DB_CONFIG
    )

def drop_biometric_db():
    conn = psycopg2.connect(dbname="postgres", **DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    # Terminate all active connections to biometric_db first
    cur.execute("""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = 'biometric_db'
    """)

    # Now drop it
    cur.execute("DROP DATABASE IF EXISTS biometric_db")
    print("biometric_db dropped and destroyed!")

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
import json

DB_CONFIG = {
    "user": "postgres",
    "password": "g67mbz9h",  # replace with yours
    "host": "localhost",
    "port": "5432"
}

def load_voters():
    # Load voters.json
    with open("data/voters.json", "r") as f:
        voters = json.load(f)

    print(f"Loaded {len(voters)} voters from JSON")

    # Connect to election_db
    conn = psycopg2.connect(dbname="election_db", **DB_CONFIG)
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

if __name__ == "__main__":
    load_voters()
