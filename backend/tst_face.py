from deepface import DeepFace
import cv2

def test_camera():
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("FAILED - Camera not accessible")
        return
    
    print("SUCCESS - Camera opened!")
    print("Make sure your face is well lit and centered")
    print("Press SPACE to capture, Q to quit...")
    
    captured_frame = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Mirror the frame so it feels natural
        frame = cv2.flip(frame, 1)
        
        # Draw a face guide rectangle in center
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.rectangle(frame, (cx-100, cy-130), (cx+100, cy+130), (0, 255, 0), 2)
        cv2.putText(frame, "Align face in box - SPACE to capture", 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        cv2.imshow("Face Capture", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            # Capture without the overlay
            ret, clean_frame = cap.read()
            clean_frame = cv2.flip(clean_frame, 1)
            captured_frame = clean_frame
            print("Frame captured!")
            break
        elif key == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    if captured_frame is None:
        print("No frame captured")
        return
    
    # Show the captured image
    cv2.imshow("Captured - press any key", captured_frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    # Save and detect
    cv2.imwrite("test_capture.jpg", captured_frame)
    print("Detecting face...")
    
    try:
        result = DeepFace.extract_faces(
            img_path="test_capture.jpg",
            detector_backend="opencv",
            enforce_detection=False  # won't crash if no face found
        )
        
        if result and result[0]['confidence'] > 0.5:
            print(f"SUCCESS - Face detected!")
            print(f"Confidence: {result[0]['confidence']:.2f}")
            print(f"Face region: {result[0]['facial_area']}")
        else:
            print(f"Face confidence too low: {result[0]['confidence']:.2f}")
            print("Try better lighting or move closer to camera")
            
    except Exception as e:
        print(f"FAILED - {e}")

if __name__ == "__main__":
    test_camera()