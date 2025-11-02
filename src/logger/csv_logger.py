import csv
from pathlib import Path
from datetime import datetime


class CSVLogger:
    """
    A class to manage attendance records by storing names and time in a CSV file.
    """

    def __init__(self, file_path: str):
        """
        Initialize the attendance logger with a file path.

        Args:
            file_path (str): Path to the CSV file for storing attendance
        """
        self.base_path = Path(file_path)
        self.file_path = self._create_dated_filepath()
        self.logged_names = set()  # Track names logged in current session
        self._write_header()

    def _create_dated_filepath(self) -> Path:
        """
        Create a filename with current date prefix.

        Returns:
            Path: New path with dated filename
        """
        datetime_str = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        filename = f"{datetime_str}_{self.base_path.stem}{self.base_path.suffix}"
        return self.base_path.parent / filename

    def _write_header(self) -> None:
        """
        Write CSV header if file doesn't exist.
        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists() or self.file_path.stat().st_size == 0:
            with self.file_path.open(mode="w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Name", "Time"])

    def log_attendance(self, name: str) -> None:
        """
        Log attendance for a person if not already recorded in this session.

        Args:
            name (str): Name of the person to log
        """
        if name not in self.logged_names:
            self.logged_names.add(name)
            timestamp = datetime.now().strftime("%H:%M:%S")
            with self.file_path.open(mode="a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([name, timestamp])


if __name__ == "__main__":
    logger = CSVLogger("attendance/attendance.csv")
    logger.log_attendance("Mhmad")  
