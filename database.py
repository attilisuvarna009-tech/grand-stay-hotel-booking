import sqlite3

connection = sqlite3.connect("hotel.db")

cursor = connection.cursor()

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
    total_amount REAL NOT NULL
)
""")

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

print("Database created successfully!")