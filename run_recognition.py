import cv2
from src import FaceRecognition, CSVLogger


def run_recognition(
    encodings_file: str,
    log_csv: bool = True,
    csv_path: str = "attendance_records/attendance.csv",
):
    """
    Runs the real-time face recognition system with optional attendance logging.

    Args:
        encodings_file (str): Path to the .pkl file containing known face encodings.
        log_csv (bool): If True, save attendance locally to a CSV file (default is True).
        csv_path (str): Path to the CSV file used for logging attendance.
    """
    recognizer = FaceRecognition(encodings_file)
    logger = CSVLogger(csv_path) if log_csv else None
    logged_students = set()

    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Detect faces and get names
        face_names, _ = recognizer.detect_known_faces(frame)

        for name in face_names:
            if isinstance(name, str) and name != "Unknown" and name not in logged_students:
                if logger:
                    logger.log_attendance(name)
                print(f"Detected: {name}")
                logged_students.add(name)

        cv2.imshow("Live Face Recognition", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    encodings_file = "models/encodings.pkl"
    log_csv = True
    csv_path = "attendance_records/attendance.csv"

    run_recognition(
        encodings_file=encodings_file,
        log_csv=log_csv,
        csv_path=csv_path,
    )