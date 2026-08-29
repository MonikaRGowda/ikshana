from deepface import DeepFace
import cv2
import hashlib

def capture_face(label):
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("FAILED - Camera not accessible")
        return None
    
    print(f"Capturing face for: {label}")
    print("Align your face in the green box and press SPACE...")
    
    captured_frame = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.rectangle(frame, (cx-100, cy-130), (cx+100, cy+130), (0, 255, 0), 2)
        cv2.putText(frame, f"Capturing: {label} - SPACE to capture",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        cv2.imshow("Face Capture", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            ret, clean_frame = cap.read()
            clean_frame = cv2.flip(clean_frame, 1)
            captured_frame = clean_frame
            print(f"Captured {label}!")
            break
        elif key == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    return captured_frame

def face_to_hash(image_path):
    # Get face embedding from DeepFace
    embedding = DeepFace.represent(
        img_path=image_path,
        model_name="Facenet",
        enforce_detection=False
    )
    # Convert embedding to a hash
    embedding_str = str(embedding[0]['embedding'])
    return hashlib.sha256(embedding_str.encode()).hexdigest()

def test_face_comparison():
    print("=" * 50)
    print("TEST 1 — Same person twice (should MATCH)")
    print("=" * 50)
    
    # Capture first scan
    frame1 = capture_face("First scan")
    if frame1 is None:
        return
    cv2.imwrite("face1.jpg", frame1)
    
    print("Now capture your face again for second scan...")
    input("Press ENTER when ready...")
    
    # Capture second scan
    frame2 = capture_face("Second scan")
    if frame2 is None:
        return
    cv2.imwrite("face2.jpg", frame2)
    
    # Compare
    print("Comparing faces...")
    try:
        result = DeepFace.verify(
            img1_path="face1.jpg",
            img2_path="face2.jpg",
            model_name="Facenet",
            enforce_detection=False
        )
        
        print(f"Same person: {result['verified']}")
        print(f"Distance: {result['distance']:.4f}")
        print(f"Threshold: {result['threshold']:.4f}")
        
        if result['verified']:
            print("CORRECT - Same person detected as same person")
        else:
            print("WRONG - Same person detected as different")
            
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 50)
    print("TEST 2 — Face hashing")
    print("=" * 50)
    
    hash1 = face_to_hash("face1.jpg")
    hash2 = face_to_hash("face2.jpg")
    
    print(f"Hash 1: {hash1[:20]}...")
    print(f"Hash 2: {hash2[:20]}...")
    print(f"Hashes match: {hash1 == hash2}")

if __name__ == "__main__":
    test_face_comparison()