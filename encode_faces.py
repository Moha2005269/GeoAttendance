from src import FaceEncoder


def run_encoding(images_dir: str, output_file: str):
    """
    Encodes faces from a given directory of images and saves the encodings to a file.

    Args:
        images_dir (str): Path to the directory containing face images. Each image should represent one person.
        output_file (str): Path to the output .pkl file where the face encodings will be saved.

    The encoded faces can later be used for recognition and matching.
    """
    encoder = FaceEncoder(images_dir, output_file)
    encoder.encode()
    print("Encoding completed and saved to:", output_file)


if __name__ == "__main__":
    images_dir = "./known_faces_data"
    output_file = "models/encodings.pkl"
    run_encoding(images_dir, output_file)
