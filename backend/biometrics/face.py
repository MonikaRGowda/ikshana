import cv2
import base64
import numpy as np
import json
import os
from deepface import DeepFace
from datetime import datetime

FACE_THRESHOLD = 0.1  # cosine distance below this = same person

def decode_base64_image(base64_str: str, save_path: str) -> bool:
    """Decode base64 image from frontend and save to disk"""
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        img_bytes = base64.b64decode(base64_str)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            return False
        cv2.imwrite(save_path, img)
        return True
    except Exception as e:
        print(f"Image decode error: {e}")
        return False

def get_face_embedding(image_path: str) -> list | None:
    """Get 128-dimension face embedding from image"""
    try:
        result = DeepFace.represent(
            img_path=image_path,
            model_name="Facenet",
            enforce_detection=False
        )
        return result[0]['embedding']
    except Exception as e:
        print(f"Face embedding error: {e}")
        return None

def cosine_distance(emb1: list, emb2: list) -> float:
    """Calculate cosine distance between two embeddings"""
    import numpy as np
    a = np.array(emb1)
    b = np.array(emb2)
    if a.ndim != 1 or b.ndim != 1 or a.shape != b.shape:
        raise ValueError("Face embeddings must be one-dimensional vectors of equal length")
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        raise ValueError("Face embeddings must not be zero vectors")
    return float(1 - np.dot(a, b) / denominator)

def find_matching_face(
    new_embedding: list,
    stored_records: list[dict]
) -> dict | None:
    """
    Compare new face embedding against all stored embeddings
    Returns matching record if found, None otherwise
    
    stored_records: list of {voter_id, face_embedding (list)}
    """
    for record in stored_records:
        try:
            stored_value = record["face_embedding"]
            stored_embedding = json.loads(stored_value) if isinstance(stored_value, str) else stored_value
            distance = cosine_distance(new_embedding, stored_embedding)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if distance < FACE_THRESHOLD:
            print(f"Face match found! voter_id: {record['voter_id']}, distance: {distance:.4f}")
            return record
    return None