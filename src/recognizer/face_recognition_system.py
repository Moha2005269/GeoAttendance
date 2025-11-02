import cv2
import pickle
import numpy as np
import face_recognition
from pathlib import Path
from ..utils.draw_box_label import draw_box_label


class FaceRecognition:
    """A class for face recognition using OpenCV and face_recognition libraries."""

    def __init__(self, encodings_path):
        """
        Initialize with the path to saved encodings.

        Args:
            encodings_path (str): Path to .pkl file containing face encodings.
        """
        self.encodings_path = Path(encodings_path)
        self.known_face_names, self.known_face_encodings = self.load_encodings()

    def load_encodings(self):
        """Loads encodings from a .pkl file."""
        if self.encodings_path.exists():
            with self.encodings_path.open("rb") as file:
                encodings = pickle.load(file)
                self.known_face_names = [str(name) for name in encodings.keys()]
                self.known_face_encodings = list(encodings.values())

                if not self.known_face_encodings:
                    raise ValueError(
                        f"No face encodings found in the file '{self.encodings_path}'"
                    )

                return self.known_face_names, self.known_face_encodings
        else:
            raise FileNotFoundError(
                f"File '{self.encodings_path}' does not exist. Please run FaceEncoder first."
            )

    def detect_known_faces(self, image, tolerance=0.6, draw_box=True, scale_factor=0.5):
        """
        Detects and recognizes faces in the image.

        Args:
            image (numpy.ndarray): Input image in BGR format.
            tolerance (float): Face matching tolerance (default: 0.6).
            draw_box (bool): Whether to draw boxes around faces (default: True).
            scale_factor (float): Factor to scale down image for processing (default: 0.5).

        Returns:
            tuple: (face_locations, face_names) with locations scaled to original size.
        """
        # Downscale image for faster processing
        small_image = cv2.resize(image, (0, 0), fx=scale_factor, fy=scale_factor)
        rgb_image = cv2.cvtColor(small_image, cv2.COLOR_BGR2RGB)

        # Detect face locations and encodings
        face_locations = face_recognition.face_locations(rgb_image)
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)

        face_names = []
        # Process each detected face
        for (top, right, bottom, left), face_encoding in zip(
            face_locations, face_encodings
        ):
            name = "Unknown"
            face_distances = face_recognition.face_distance(
                self.known_face_encodings, face_encoding
            )
            best_match_index = np.argmin(face_distances)
            if face_distances[best_match_index] < tolerance:
                name = self.known_face_names[best_match_index]
            face_names.append(name)

            # Draw box and label on original image
            if draw_box:
                # Scale box coordinates individually for drawing
                box = np.array([left, top, right, bottom]) / scale_factor
                draw_box_label(image, box, name)

        # Scale all face locations back to original size using NumPy
        face_locations = np.array(face_locations) / scale_factor
        face_locations = face_locations.astype(int)

        return face_locations, face_names
