import cv2
import os
import numpy as np
import face_recognition
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from src import FaceRecognition
from app.database import mark_attendance
from PIL import Image, ImageTk
import time

class AttendanceManager:
    """Manages face detection and attendance marking with advanced confidence."""

    def __init__(self, encodings_file="models/encodings.pkl"):
        self.recognizer = FaceRecognition(encodings_file)
        print("✅ Loaded face encodings:", list(self.recognizer.known_face_names))
        self.logged_students = set()
        self.cap = None
        self.camera_running = False
        self.retry_count = 0  # Track retries for low confidence
        self.max_retries = 3  # Max retries before failing

    def start_camera(self):
        """Start camera feed."""
        if not self.camera_running:
            try:
                self.cap = cv2.VideoCapture(0)
                if not self.cap.isOpened():
                    raise Exception("Could not open camera.")
                print("✅ Camera opened successfully")
                self.camera_running = True
            except Exception as e:
                messagebox.showerror("Error", str(e))
                self.camera_running = False

    def stop_camera(self):
        """Stop camera feed."""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.camera_running = False
        self.retry_count = 0  # Reset retry count

    def detect_and_mark(self, student_id, student_name, session_id=None, callback=None):
        """Detect face and mark attendance with advanced confidence logic."""
        if not self.cap or not self.cap.isOpened():
            if callback:
                callback(False, "Camera not started.")
            return False, "Camera not started."

        # Reset retry count on new attempt
        self.retry_count = 0

        # Try up to max_retries
        for attempt in range(self.max_retries):
            ret, frame = self.cap.read()
            if not ret:
                if callback:
                    callback(False, "Failed to capture frame.")
                return False, "Failed to capture frame."

            print(f"📸 Captured frame (Attempt {attempt + 1})")

            # Detect faces
            face_locations, face_names = self.recognizer.detect_known_faces(frame, scale_factor=1.0)

            print("🔍 Detected face names:", face_names)

            # Check if detected name matches logged-in user
            for name in face_names:
                if isinstance(name, str) and name == student_name:
                    # Get the face encoding for this face
                    small_image = cv2.resize(frame, (0, 0), fx=1.0, fy=1.0)
                    rgb_image = cv2.cvtColor(small_image, cv2.COLOR_BGR2RGB)
                    face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
                    
                    # Find the index of the matching face
                    for i, (top, right, bottom, left) in enumerate(face_locations):
                        if name == student_name:
                            # Calculate face distance for this specific face
                            face_encoding = face_encodings[i]
                            face_distances = face_recognition.face_distance(
                                self.recognizer.known_face_encodings,
                                face_encoding
                            )
                            best_match_index = np.argmin(face_distances)
                            distance = face_distances[best_match_index]

                            # Convert distance to confidence (0-100%)
                            confidence = max(0, min(100, int((1 - distance) * 100)))

                            # Enhanced: Check face landmarks for stability (frontal face)
                            face_landmarks = face_recognition.face_landmarks(rgb_image, [face_locations[i]])
                            if not face_landmarks:
                                continue  # Skip if no landmarks detected

                            # Simple landmark check: ensure eyes and nose are visible
                            if len(face_landmarks[0]['left_eye']) < 6 or len(face_landmarks[0]['right_eye']) < 6:
                                if callback:
                                    callback(False, f"Face not frontal enough (Attempt {attempt + 1}/{self.max_retries}). Please adjust position.")
                                continue

                            # For now, use fixed 50% 
                            min_confidence = 50

                            if confidence >= min_confidence:
                                # Save snapshot
                                photo_dir = Path("attendance_photos")
                                photo_dir.mkdir(exist_ok=True)
                                photo_filename = f"{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                                photo_path = photo_dir / photo_filename
                                cv2.imwrite(str(photo_path), frame)

                                # Mark attendance with confidence
                                mark_attendance(student_id, student_name, session_id, str(photo_path), confidence)

                                # Return success
                                if callback:
                                    callback(True, f"Attendance marked for {student_name} (Confidence: {confidence}% | Attempt {attempt + 1})")
                                return True, f"Attendance marked for {student_name} (Confidence: {confidence}% | Attempt {attempt + 1})"
                            else:
                                # Low confidence → suggest retry
                                if attempt < self.max_retries - 1:
                                    if callback:
                                        callback(False, f"Confidence too low ({confidence}%). Retrying... ({attempt + 2}/{self.max_retries})")
                                    # Wait a bit before retrying
                                    time.sleep(1)
                                else:
                                    if callback:
                                        callback(False, f"Face recognized but confidence too low ({confidence}%). Minimum required: {min_confidence}%. No more retries.")
                                    return False, f"Face recognized but confidence too low ({confidence}%). Minimum required: {min_confidence}%. No more retries."

        if callback:
            callback(False, "Face not recognized after maximum retries.")
        return False, "Face not recognized after maximum retries."