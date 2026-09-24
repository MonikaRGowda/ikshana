"""
One-time migration: encrypts any voters rows that are still plaintext
(loaded before crypto.py existed). Safe to run multiple times - rows
already encrypted are detected via is_encrypted() and skipped.

Run from backend/:
    python scripts/encrypt_existing_voters.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_election_db  # noqa: E402
from crypto import encrypt_field, is_encrypted  # noqa: E402

FIELDS = ["name", "phone", "address", "dob"]


def main():
    conn = get_election_db()
    cur = conn.cursor()

    cur.execute(f"SELECT voter_id, {', '.join(FIELDS)} FROM voters")
    rows = cur.fetchall()

    updated = 0
    skipped = 0

    for row in rows:
        voter_id = row[0]
        values = dict(zip(FIELDS, row[1:]))

        # Only re-encrypt fields that aren't already encrypted - lets
        # this run safely against a mix of old and new rows, or be
        # re-run without double-encrypting anything.
        needs_update = any(not is_encrypted(v) for v in values.values())
        if not needs_update:
            skipped += 1
            continue

        new_values = {
            field: (v if is_encrypted(v) else encrypt_field(v))
            for field, v in values.items()
        }

        cur.execute(
            f"UPDATE voters SET {', '.join(f'{f} = %s' for f in FIELDS)} WHERE voter_id = %s",
            (*[new_values[f] for f in FIELDS], voter_id),
        )
        updated += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"Encrypted {updated} voter rows. {skipped} were already encrypted and left unchanged.")


if __name__ == "__main__":
    main()