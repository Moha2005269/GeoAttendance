import sqlite3
from pathlib import Path

DB_PATH = Path("database/attendance.db")

# Auto-create database folder if it doesn't exist
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_db():
    """Initialize the database and create tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Students table (simplified)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            class_name TEXT
        )
    """)

    # Sessions table (for multi-class support)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT
        )
    """)

    # Attendance table (simplified)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            name TEXT NOT NULL,
            session_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            photo_path TEXT,
            confidence REAL,
            is_late BOOLEAN DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()

def add_student(student_id, password, name, class_name=""):
    """Add a new student with basic fields."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO students (student_id, password, name, class_name) VALUES (?, ?, ?, ?)
        """, (student_id, password, name, class_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_student(student_id, password):
    """Get student by ID and password."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, student_id, name, class_name FROM students WHERE student_id = ? AND password = ?
    """, (student_id, password))
    row = cursor.fetchone()
    conn.close()
    return row

def mark_attendance(student_id, name, session_id=None, photo_path=None, confidence=None, is_late=False):
    """Mark attendance for a student."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attendance (student_id, name, session_id, photo_path, confidence, is_late) VALUES (?, ?, ?, ?, ?, ?)
    """, (student_id, name, session_id, photo_path, confidence, is_late))
    conn.commit()
    conn.close()

def get_attendance_history(student_id=None):
    """Get attendance history."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if student_id:
        cursor.execute("""
            SELECT timestamp, name, photo_path, confidence, is_late FROM attendance WHERE student_id = ? ORDER BY timestamp DESC
        """, (student_id,))
    else:
        cursor.execute("""
            SELECT timestamp, student_id, name, photo_path, confidence, is_late FROM attendance ORDER BY timestamp DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_student_count():
    """Get total number of students."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM students")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_today_attendance_count():
    """Get today's attendance count."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM attendance WHERE date(timestamp) = date('now')
    """)
    count = cursor.fetchone()[0]
    conn.close()
    return count