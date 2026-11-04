
import os
import sqlite3
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from database import init_db


# ---------------- FLASK CONFIGURATION ----------------

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-only-change-me"
)

init_db()


# ---------------- DATABASE CONNECTION ----------------

def get_db_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    database_path = os.path.join(base_dir, "hotel.db")

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row

    return connection


# ---------------- ROOM INFORMATION ----------------

ROOM_CAPACITY = {
    "Standard Room": 2,
    "Deluxe Room": 3,
    "Luxury Suite": 4
}

BOOKING_STATUSES = (
    "Pending",
    "Confirmed",
    "Cancelled"
)


# ---------------- DATE VALIDATION ----------------

def validate_dates(check_in, check_out):
    try:
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d")

        nights = (check_out_date - check_in_date).days

        if nights <= 0:
            return None

        return nights

    except (ValueError, TypeError):
        return None


# ---------------- ROOM AVAILABILITY ----------------

def check_room_availability(
    connection,
    room_type,
    check_in,
    check_out
):
    return connection.execute("""
        SELECT id
        FROM bookings
        WHERE room_type = ?
          AND status != 'Cancelled'
          AND check_in < ?
          AND check_out > ?
        LIMIT 1
    """, (
        room_type,
        check_out,
        check_in
    )).fetchone()


# ---------------- HOME PAGE ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- ROOMS PAGE ----------------

@app.route("/rooms")
def rooms():
    return render_template("rooms.html")


# ---------------- BOOKING PAGE ----------------

@app.route("/booking", methods=["GET", "POST"])
def booking():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        room_type = request.form.get("room_type", "")
        check_in = request.form.get("check_in", "")
        check_out = request.form.get("check_out", "")

        try:
            guests = int(request.form.get("guests", "0"))
        except (ValueError, TypeError):
            return "Please enter a valid number of guests."

        if not all([
            name, email, phone,
            room_type, check_in, check_out
        ]):
            return "Please fill in all required fields."

        if room_type not in ROOM_CAPACITY:
            return "Invalid room type."

        if guests <= 0:
            return "Number of guests must be at least 1."

        if guests > ROOM_CAPACITY[room_type]:
            return render_template(
                "capacity_error.html",
                room_type=room_type,
                capacity=ROOM_CAPACITY[room_type]
            )

        nights = validate_dates(check_in, check_out)

        if nights is None:
            return "Invalid dates. Check-out must be after check-in."

        connection = get_db_connection()

        try:
            existing_booking = check_room_availability(
                connection,
                room_type,
                check_in,
                check_out
            )

            if existing_booking:
                return render_template(
                    "not_available.html",
                    room_type=room_type,
                    check_in=check_in,
                    check_out=check_out
                )

            room = connection.execute(
                "SELECT price FROM rooms WHERE room_type = ?",
                (room_type,)
            ).fetchone()

            if room is None:
                return "Room not found."

            price = room["price"]
            total_amount = price * nights

        finally:
            connection.close()

        return render_template(
            "payment.html",
            name=name,
            email=email,
            phone=phone,
            room_type=room_type,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            nights=nights,
            total_amount=total_amount
        )

    return render_template("booking.html")


# ---------------- CONFIRM BOOKING ----------------

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    room_type = request.form.get("room_type", "")
    check_in = request.form.get("check_in", "")
    check_out = request.form.get("check_out", "")

    payment_method = request.form.get("payment_method", "")

    try:
        guests = int(request.form.get("guests", "0"))
    except (ValueError, TypeError):
        return "Invalid number of guests."

    if not all([
        name, email, phone,
        room_type, check_in, check_out,
        payment_method
    ]):
        return "Missing booking or payment details."

    if room_type not in ROOM_CAPACITY:
        return "Invalid room type."

    if guests <= 0:
        return "Number of guests must be at least 1."

    if guests > ROOM_CAPACITY[room_type]:
        return render_template(
            "capacity_error.html",
            room_type=room_type,
            capacity=ROOM_CAPACITY[room_type]
        )

    nights = validate_dates(check_in, check_out)

    if nights is None:
        return "Invalid booking dates."

    connection = get_db_connection()

    try:
        existing_booking = check_room_availability(
            connection,
            room_type,
            check_in,
            check_out
        )

        if existing_booking:
            return render_template(
                "not_available.html",
                room_type=room_type,
                check_in=check_in,
                check_out=check_out
            )

        room = connection.execute(
            "SELECT price FROM rooms WHERE room_type = ?",
            (room_type,)
        ).fetchone()

        if room is None:
            return "Room not found."

        total_amount = room["price"] * nights

        cursor = connection.execute("""
            INSERT INTO bookings (
                customer_name,
                email,
                phone,
                room_type,
                check_in,
                check_out,
                guests,
                total_amount,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            phone,
            room_type,
            check_in,
            check_out,
            guests,
            total_amount,
            "Pending"
        ))

        booking_id = cursor.lastrowid

        connection.commit()

    finally:
        connection.close()

    return render_template(
        "confirmation.html",
        booking_id=booking_id,
        name=name,
        email=email,
        phone=phone,
        room_type=room_type,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        nights=nights,
        total_amount=total_amount,
        payment_method=payment_method
    )


# ---------------- CANCEL BOOKING ----------------

@app.route("/cancel_booking", methods=["GET", "POST"])
def cancel_booking():

    if request.method == "POST":

        booking_id = request.form.get("booking_id", "").strip()

        if not booking_id.isdigit():
            return "Please enter a valid booking ID."

        connection = get_db_connection()

        try:
            booking_record = connection.execute(
                "SELECT * FROM bookings WHERE id = ?",
                (booking_id,)
            ).fetchone()

            if booking_record is None:
                return """
                <h2 style="text-align:center; margin-top:50px;">
                    Booking not found.
                </h2>
                <p style="text-align:center;">
                    <a href="/cancel_booking">Try Again</a>
                </p>
                """

            connection.execute("""
                UPDATE bookings
                SET status = 'Cancelled'
                WHERE id = ?
            """, (booking_id,))

            connection.commit()

        finally:
            connection.close()

        return render_template(
            "cancel_success.html",
            booking_id=booking_id
        )

    return render_template("cancel_booking.html")


# ---------------- ADMIN LOGIN ----------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get("username", "")
        password = request.form.get("password", "")

        admin_username = os.environ.get("ADMIN_USERNAME")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if (
            admin_username
            and admin_password
            and username == admin_username
            and password == admin_password
        ):
            session.clear()
            session["admin_logged_in"] = True

            return redirect(url_for("admin"))

        return render_template(
            "admin_login.html",
            error="Invalid username or password."
        )

    return render_template("admin_login.html")


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin")
def admin():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    connection = get_db_connection()

    try:
        bookings = connection.execute("""
            SELECT *
            FROM bookings
            ORDER BY id DESC
        """).fetchall()

        total_bookings = connection.execute("""
            SELECT COUNT(*) AS count
            FROM bookings
        """).fetchone()["count"]

        total_customers = connection.execute("""
            SELECT COUNT(DISTINCT LOWER(TRIM(email))) AS count
            FROM bookings
            WHERE email IS NOT NULL
              AND TRIM(email) != ''
        """).fetchone()["count"]

        total_revenue = connection.execute("""
            SELECT COALESCE(SUM(total_amount), 0) AS revenue
            FROM bookings
            WHERE status != 'Cancelled'
        """).fetchone()["revenue"]

        standard_bookings = connection.execute("""
            SELECT COUNT(*) AS count
            FROM bookings
            WHERE room_type = 'Standard Room'
              AND status != 'Cancelled'
        """).fetchone()["count"]

        deluxe_bookings = connection.execute("""
            SELECT COUNT(*) AS count
            FROM bookings
            WHERE room_type = 'Deluxe Room'
              AND status != 'Cancelled'
        """).fetchone()["count"]

        luxury_bookings = connection.execute("""
            SELECT COUNT(*) AS count
            FROM bookings
            WHERE room_type = 'Luxury Suite'
              AND status != 'Cancelled'
        """).fetchone()["count"]

    finally:
        connection.close()

    return render_template(
        "admin.html",
        bookings=bookings,
        total_bookings=total_bookings,
        total_customers=total_customers,
        total_revenue=total_revenue,
        standard_bookings=standard_bookings,
        deluxe_bookings=deluxe_bookings,
        luxury_bookings=luxury_bookings
    )


# ---------------- UPDATE BOOKING STATUS (ADMIN) ----------------

@app.route(
    "/admin/update_booking_status/<int:booking_id>",
    methods=["POST"]
)
def update_booking_status(booking_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status", "").strip()

    if new_status not in BOOKING_STATUSES:
        return "Invalid booking status.", 400

    connection = get_db_connection()

    try:
        booking_record = connection.execute(
            "SELECT id FROM bookings WHERE id = ?",
            (booking_id,)
        ).fetchone()

        if booking_record is None:
            return "Booking not found.", 404

        connection.execute("""
            UPDATE bookings
            SET status = ?
            WHERE id = ?
        """, (new_status, booking_id))

        connection.commit()

    finally:
        connection.close()

    return redirect(url_for("admin"))


# ---------------- ADMIN CUSTOMER MANAGEMENT ----------------

@app.route("/admin/customers")
def admin_customers():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    search = request.args.get("search", "").strip()
    selected_email = request.args.get("email", "").strip()

    connection = get_db_connection()

    try:
        customer_bookings = []
        selected_customer = None

        if selected_email:

            selected_customer = connection.execute("""
                SELECT
                    MAX(customer_name) AS customer_name,
                    LOWER(TRIM(email)) AS email,
                    MAX(phone) AS phone,
                    COUNT(*) AS booking_count,
                    COALESCE(SUM(total_amount), 0) AS total_booking_value
                FROM bookings
                WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))
                GROUP BY LOWER(TRIM(email))
            """, (selected_email,)).fetchone()

            if selected_customer:

                customer_bookings = connection.execute("""
                    SELECT *
                    FROM bookings
                    WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))
                    ORDER BY id DESC
                """, (selected_email,)).fetchall()

        customers = connection.execute("""
            SELECT
                MAX(customer_name) AS customer_name,
                LOWER(TRIM(email)) AS email,
                MAX(phone) AS phone,
                COUNT(*) AS booking_count,
                COALESCE(SUM(total_amount), 0) AS total_booking_value
            FROM bookings
            WHERE email IS NOT NULL
              AND TRIM(email) != ''
              AND (
                  customer_name LIKE ?
                  OR email LIKE ?
                  OR phone LIKE ?
              )
            GROUP BY LOWER(TRIM(email))
            ORDER BY MAX(customer_name) COLLATE NOCASE
        """, (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        )).fetchall()

    finally:
        connection.close()

    return render_template(
        "admin_customers.html",
        customers=customers,
        search=search,
        selected_customer=selected_customer,
        customer_bookings=customer_bookings
    )


# ---------------- DELETE BOOKING (ADMIN) ----------------

@app.route("/delete_booking/<int:booking_id>", methods=["POST"])
def delete_booking(booking_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    connection = get_db_connection()

    try:
        connection.execute(
            "DELETE FROM bookings WHERE id = ?",
            (booking_id,)
        )

        connection.commit()

    finally:
        connection.close()

    return redirect(url_for("admin"))


# ---------------- ADMIN LOGOUT ----------------

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(url_for("admin_login"))


# ---------------- RUN FLASK ----------------

if __name__ == "__main__":
    app.run(debug=True)
