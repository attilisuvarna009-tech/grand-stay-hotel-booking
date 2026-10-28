import os
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Secret key for login session
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


def get_db_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    database_path = os.path.join(base_dir, "hotel.db")
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


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

        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        room_type = request.form["room_type"]
        check_in = request.form["check_in"]
        check_out = request.form["check_out"]

        guests = int(request.form["guests"])

        # ---------------- ROOM CAPACITY CHECK ----------------

        room_capacity = {
            "Standard Room": 2,
            "Deluxe Room": 3,
            "Luxury Suite": 4
        }

        if room_type not in room_capacity:
            return "Invalid room type."

        if guests <= 0:
            return "Number of guests must be at least 1."

        if guests > room_capacity[room_type]:

            return render_template(
                "capacity_error.html",
                room_type=room_type,
                capacity=room_capacity[room_type]
            )

        # ---------------- DATE CHECK ----------------

        check_in_date = datetime.strptime(
            check_in,
            "%Y-%m-%d"
        )

        check_out_date = datetime.strptime(
            check_out,
            "%Y-%m-%d"
        )

        nights = (
            check_out_date - check_in_date
        ).days

        if nights <= 0:
            return "Check-out date must be after check-in date."

        connection = get_db_connection()

        # ---------------- ROOM AVAILABILITY CHECK ----------------

        existing_booking = connection.execute("""
            SELECT * FROM bookings
            WHERE room_type = ?
            AND check_in < ?
            AND check_out > ?
        """, (
            room_type,
            check_out,
            check_in
        )).fetchone()

        if existing_booking:

            connection.close()

            return render_template(
                "not_available.html",
                room_type=room_type,
                check_in=check_in,
                check_out=check_out
            )

        # ---------------- GET ROOM PRICE ----------------

        room = connection.execute(
            "SELECT price FROM rooms WHERE room_type = ?",
            (room_type,)
        ).fetchone()

        if room is None:

            connection.close()

            return "Room not found."

        price = room["price"]

        # ---------------- CALCULATE TOTAL ----------------

        total_amount = price * nights

        connection.close()

        # ---------------- GO TO PAYMENT ----------------

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

    name = request.form["name"]
    email = request.form["email"]
    phone = request.form["phone"]
    room_type = request.form["room_type"]
    check_in = request.form["check_in"]
    check_out = request.form["check_out"]

    guests = int(request.form["guests"])

    nights = request.form["nights"]
    total_amount = request.form["total_amount"]
    payment_method = request.form["payment_method"]

    # ---------------- ROOM CAPACITY CHECK ----------------

    room_capacity = {
        "Standard Room": 2,
        "Deluxe Room": 3,
        "Luxury Suite": 4
    }

    if room_type not in room_capacity:
        return "Invalid room type."

    if guests <= 0:
        return "Number of guests must be at least 1."

    if guests > room_capacity[room_type]:

        return render_template(
            "capacity_error.html",
            room_type=room_type,
            capacity=room_capacity[room_type]
        )

    connection = get_db_connection()

    # ---------------- CHECK AVAILABILITY AGAIN ----------------

    existing_booking = connection.execute("""
        SELECT * FROM bookings
        WHERE room_type = ?
        AND check_in < ?
        AND check_out > ?
    """, (
        room_type,
        check_out,
        check_in
    )).fetchone()

    if existing_booking:

        connection.close()

        return render_template(
            "not_available.html",
            room_type=room_type,
            check_in=check_in,
            check_out=check_out
        )

    # ---------------- SAVE BOOKING ----------------

    connection.execute("""
        INSERT INTO bookings
        (
            customer_name,
            email,
            phone,
            room_type,
            check_in,
            check_out,
            guests,
            total_amount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        email,
        phone,
        room_type,
        check_in,
        check_out,
        guests,
        total_amount
    ))

    connection.commit()
    connection.close()

    # ---------------- CONFIRMATION PAGE ----------------

    return render_template(
        "confirmation.html",
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

        booking_id = request.form["booking_id"]

        connection = get_db_connection()

        booking = connection.execute(
            "SELECT * FROM bookings WHERE id = ?",
            (booking_id,)
        ).fetchone()

        if booking is None:

            connection.close()

            return """
            <h2 style="text-align:center; margin-top:50px;">
                Booking not found.
            </h2>

            <p style="text-align:center;">
                <a href="/cancel_booking">
                    Try Again
                </a>
            </p>
            """

        connection.execute(
            "DELETE FROM bookings WHERE id = ?",
            (booking_id,)
        )

        connection.commit()
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

        username = request.form["username"]
        password = request.form["password"]

        # Prototype admin credentials
        if (
    username == os.environ.get("ADMIN_USERNAME")
    and password == os.environ.get("ADMIN_PASSWORD")
):
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

    # Get all bookings
    bookings = connection.execute(
        "SELECT * FROM bookings ORDER BY id DESC"
    ).fetchall()

    # ---------------- ANALYTICS ----------------

    # Total bookings
    total_bookings = connection.execute("""
        SELECT COUNT(*) AS count
        FROM bookings
    """).fetchone()["count"]

    # Total revenue
    total_revenue = connection.execute("""
        SELECT COALESCE(SUM(total_amount), 0) AS revenue
        FROM bookings
    """).fetchone()["revenue"]

    # Standard Room bookings
    standard_bookings = connection.execute("""
        SELECT COUNT(*) AS count
        FROM bookings
        WHERE room_type = 'Standard Room'
    """).fetchone()["count"]

    # Deluxe Room bookings
    deluxe_bookings = connection.execute("""
        SELECT COUNT(*) AS count
        FROM bookings
        WHERE room_type = 'Deluxe Room'
    """).fetchone()["count"]

    # Luxury Suite bookings
    luxury_bookings = connection.execute("""
        SELECT COUNT(*) AS count
        FROM bookings
        WHERE room_type = 'Luxury Suite'
    """).fetchone()["count"]

    connection.close()

    return render_template(
        "admin.html",
        bookings=bookings,
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        standard_bookings=standard_bookings,
        deluxe_bookings=deluxe_bookings,
        luxury_bookings=luxury_bookings
    )


# ---------------- DELETE BOOKING ----------------

@app.route(
    "/delete_booking/<int:booking_id>",
    methods=["POST"]
)
def delete_booking(booking_id):

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    connection = get_db_connection()

    connection.execute(
        "DELETE FROM bookings WHERE id = ?",
        (booking_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("admin"))


# ---------------- ADMIN LOGOUT ----------------

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    return redirect(
        url_for("admin_login")
    )


# ---------------- RUN FLASK ----------------

if __name__ == "__main__":

    app.run(
        debug=True
    )