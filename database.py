
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "hotel.db")


def init_db():
    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    # Enable foreign key support
    cursor.execute("PRAGMA foreign_keys = ON")

    # ---------------- ROOMS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT NOT NULL,
        room_type TEXT NOT NULL,
        price REAL NOT NULL,
        capacity INTEGER NOT NULL,
        availability TEXT NOT NULL
    )
    """)

    # ---------------- BOOKINGS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        room_type TEXT NOT NULL,
        check_in TEXT NOT NULL,
        check_out TEXT NOT NULL,
        guests INTEGER NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        is_demo INTEGER NOT NULL DEFAULT 0
    )
    """)

    # Safely migrate existing bookings table
    cursor.execute("PRAGMA table_info(bookings)")
    booking_columns = [column[1] for column in cursor.fetchall()]

    if "status" not in booking_columns:
        cursor.execute("""
        ALTER TABLE bookings
        ADD COLUMN status TEXT NOT NULL DEFAULT 'Confirmed'
        """)

    if "is_demo" not in booking_columns:
        cursor.execute("""
        ALTER TABLE bookings
        ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0
        """)

    # ---------------- REVIEWS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL UNIQUE,
        customer_name TEXT NOT NULL,
        email TEXT NOT NULL,
        rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        feedback TEXT NOT NULL,
        created_at TEXT NOT NULL,
        is_demo INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (booking_id) REFERENCES bookings(id)
            ON DELETE CASCADE
    )
    """)

    # ---------------- SEED ROOMS ----------------
    cursor.execute("SELECT COUNT(*) FROM rooms")
    room_count = cursor.fetchone()[0]

    if room_count == 0:
        rooms = [
            ("101", "Standard Room", 2000, 2, "Available"),
            ("102", "Deluxe Room", 3000, 3, "Available"),
            ("201", "Luxury Suite", 5000, 4, "Available")
        ]

        cursor.executemany("""
        INSERT INTO rooms
        (room_number, room_type, price, capacity, availability)
        VALUES (?, ?, ?, ?, ?)
        """, rooms)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    init_db()
    print("Grand Stay database initialized successfully.")
