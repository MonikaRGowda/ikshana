"""
One-time-password generation/hashing and delivery for RO/CEO login.

DEV MODE: if RESEND_API_KEY isn't set in the environment, the OTP is printed
to the backend console instead of emailed.
"""

import hashlib
import os
import secrets

import resend


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def send_otp_email(to_email: str, code: str):
    resend_api_key = os.environ.get("RESEND_API_KEY")

    # Development mode
    if not resend_api_key:
        print("=" * 60)
        print(
            f"DEV MODE (no RESEND_API_KEY configured): "
            f"OTP for {to_email} is {code}"
        )
        print("=" * 60)
        return

    resend_from_email = os.environ.get("RESEND_FROM_EMAIL")

    if not resend_from_email:
        raise RuntimeError(
            "RESEND_FROM_EMAIL is not set. "
            "Configure a valid from address before sending OTP emails."
        )

    try:
        resend.api_key = resend_api_key

        response = resend.Emails.send(
            {
                "from": resend_from_email,
                "to": [to_email],
                "subject": "Ikshana Admin Login Code",
                "html": (
                    "<p>Your Ikshana admin login code is: "
                    f"<strong>{code}</strong></p>"
                    "<p>This code expires in 5 minutes. "
                    "If you didn't request this, contact your "
                    "election administrator immediately.</p>"
                ),
                "text": (
                    f"Your Ikshana admin login code is: {code}\n\n"
                    "This code expires in 5 minutes. "
                    "If you didn't request this, contact your "
                    "election administrator immediately."
                ),
            }
        )

        response_id = getattr(response, "id", None)

        if not response_id and isinstance(response, dict):
            response_id = response.get("id")

        if not response_id:
            raise RuntimeError("Resend returned no successful email ID.")

        print(f"OTP email sent successfully. Resend ID: {response_id}")

    except Exception as exc:
        raise RuntimeError(
            f"Failed to send OTP email via Resend to {to_email}: {exc}"
        ) from exc