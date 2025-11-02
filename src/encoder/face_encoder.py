import pickle
import face_recognition
from pathlib import Path


class FaceEncoder:
    """A class to encode faces from images and save encodings."""

    def __init__(self, images_dir, output_file="models/encodings.pkl"):
        """
        Initialize with a directory of images and an output file for encodings.

        Args:
            images_dir (str): Directory containing images to encode.
            output_file (str): File path to save encodings (default: 'encodings/encodings.pkl').
        """
        self.images_dir = Path(images_dir)
        self.output_file = Path(output_file)
        self.encodings = {}
        # self.encode()

    def encode_images(self):
        """Encodes faces from images in the specified directory."""
        self.encodings.clear()
        for image_path in self.images_dir.iterdir():
            if image_path.is_file():
                try:
                    image = face_recognition.load_image_file(image_path)
                    face_encodings = face_recognition.face_encodings(image)
                    if face_encodings:
                        # Take first face encoding
                        self.encodings[image_path.stem] = face_encodings[0]
                    else:
                        print(f"No faces found in '{image_path}'.")
                except Exception as e:
                    print(f"Failed to process '{image_path}': {e}")

    def save_encodings(self):
        """Saves encodings to a .pkl file."""
        try:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_file, "wb") as file:
                pickle.dump(self.encodings, file, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"Encodings saved to '{self.output_file}'")
        except Exception as e:
            print(f"Failed to save encodings: {e}")

    def encode(self):
        """Encodes faces and saves the encodings to a file."""
        self.encode_images()
        self.save_encodings()
