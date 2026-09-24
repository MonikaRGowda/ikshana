import unittest

from routers.biometric import classify_fraud


class FraudClassificationTests(unittest.TestCase):
    def test_duplicate_voting_when_same_biometric_same_voter(self):
        result = classify_fraud(
            voter_id="V1001",
            fingerprint="fp-123",
            face_embedding=[0.1, 0.2, 0.3],
            stored_fingerprints=[{"voter_id": "V1001", "iso_template": "fp-123"}],
            stored_faces=[{"voter_id": "V1001", "face_embedding": "[0.1, 0.2, 0.3]"}],
        )
        self.assertEqual(result["fraud_type"], "Duplicate Voting")

    def test_identity_fraud_when_same_biometric_different_voter(self):
        result = classify_fraud(
            voter_id="V1001",
            fingerprint="fp-123",
            face_embedding=[0.1, 0.2, 0.3],
            stored_fingerprints=[{"voter_id": "V2002", "iso_template": "fp-123"}],
            stored_faces=[{"voter_id": "V2002", "face_embedding": "[0.1, 0.2, 0.3]"}],
        )
        self.assertEqual(result["fraud_type"], "Identity Fraud")

    def test_voter_id_forgery_when_different_biometric_same_voter(self):
        result = classify_fraud(
            voter_id="V1001",
            fingerprint="fp-new",
            face_embedding=[0.8, 0.9, 0.7],
            stored_fingerprints=[{"voter_id": "V1001", "iso_template": "fp-old"}],
            stored_faces=[{"voter_id": "V1001", "face_embedding": "[0.2, 0.3, 0.4]"}],
        )
        self.assertEqual(result["fraud_type"], "Voter ID Forgery")


if __name__ == "__main__":
    unittest.main()
