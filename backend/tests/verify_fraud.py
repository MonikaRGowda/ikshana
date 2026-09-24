import sys
sys.path.append(r'c:\Users\LENOVO\ikshana\backend')
from routers.biometric import classify_fraud

print(classify_fraud('V1001', b'fp-123', [0.1, 0.2, 0.3], [{'voter_id': 'V1001', 'iso_template': b'fp-123'}], [{'voter_id': 'V1001', 'face_embedding': '[0.1, 0.2, 0.3]'}]))
print(classify_fraud('V1001', b'fp-123', [0.1, 0.2, 0.3], [{'voter_id': 'V2002', 'iso_template': b'fp-123'}], [{'voter_id': 'V2002', 'face_embedding': '[0.1, 0.2, 0.3]'}]))
print(classify_fraud('V1001', b'fp-new', [0.8, 0.9, 0.7], [{'voter_id': 'V1001', 'iso_template': b'fp-old'}], [{'voter_id': 'V1001', 'face_embedding': '[0.2, 0.3, 0.4]'}]))
