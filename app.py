
import os
import sqlite3
from datetime import datetime, date, timedelta

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from database import init_db


# ==========================================================
# APPLICATION CONFIGURATION
# ==========================================================

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

init_db()

ROOM_CAPACITY = {
    "Standard Room": 2,
    "Deluxe Room": 3,
    "Luxury Suite": 4
}

BOOKING_STATUSES = ("Pending", "Confirmed", "Cancelled")


# ==========================================================
# DATABASE CONNECTION
# ==========================================================

def get_db_connection():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    database_path = os.path.join(base_dir, "hotel.db")

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def admin_required():
    return session.get("admin_logged_in") is True


def check_room_availability(connection, room_type, check_in, check_out):
    return connection.execute("""
        SELECT id
        FROM bookings
        WHERE room_type = ?
          AND status != 'Cancelled'
          AND check_in < ?
          AND check_out > ?
        LIMIT 1
    """, (room_type, check_out, check_in)).fetchone() is None


def get_room_price(connection, room_type):
    return connection.execute("""
        SELECT price
        FROM rooms
        WHERE room_type = ?
    """, (room_type,)).fetchone()


# ==========================================================
# HOME PAGE
# ==========================================================

@app.route("/")
def home():
    connection = get_db_connection()

    rating_data = connection.execute("""
        SELECT
            COUNT(*) AS total_reviews,
            ROUND(AVG(rating), 1) AS average_rating
        FROM reviews
    """).fetchone()

    latest_reviews = connection.execute("""
        SELECT customer_name, rating, feedback, created_at, is_demo
        FROM reviews
        ORDER BY id DESC
        LIMIT 6
    """).fetchall()

    connection.close()

    return render_template(
        "index.html",
        total_reviews=rating_data["total_reviews"],
        average_rating=rating_data["average_rating"] or 0,
        latest_reviews=latest_reviews
    )


# ==========================================================
# ROOMS PAGE
# ==========================================================

@app.route("/rooms")
def rooms():
    return render_template("rooms.html")


# ==========================================================
# BOOKING PAGE
# ==========================================================

@app.route("/booking", methods=["GET", "POST"])
def booking():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        room_type = request.form.get("room_type", "").strip()
        check_in = request.form.get("check_in", "").strip()
        check_out = request.form.get("check_out", "").strip()

        try:
            guests = int(request.form.get("guests", "0"))
            check_in_date = datetime.strptime(check_in, "%Y-%m-%d").date()
            check_out_date = datetime.strptime(check_out, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return "Please enter valid booking details and dates.", 400

        if not all([name, email, phone]):
            return "Please fill in all customer details.", 400

        if room_type not in ROOM_CAPACITY:
            return "Invalid room type.", 400

        if guests < 1:
            return "Number of guests must be at least 1.", 400

        if guests > ROOM_CAPACITY[room_type]:
            return render_template(
                "capacity_error.html",
                room_type=room_type,
                capacity=ROOM_CAPACITY[room_type]
            )

        nights = (check_out_date - check_in_date).days

        if nights <= 0:
            return "Check-out date must be after check-in date.", 400

        if check_in_date < date.today():
            return "Check-in date cannot be in the past.", 400

        connection = get_db_connection()

        try:
            if not check_room_availability(
                connection, room_type, check_in, check_out
            ):
                return render_template(
                    "not_available.html",
                    room_type=room_type,
                    check_in=check_in,
                    check_out=check_out
                )

            room = get_room_price(connection, room_type)

            if room is None:
                return "Room not found.", 404

            total_amount = room["price"] * nights

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


# ==========================================================
# CONFIRM BOOKING
# ==========================================================

@app.route("/confirm_booking", methods=["POST"])
def confirm_booking():

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    room_type = request.form.get("room_type", "").strip()
    check_in = request.form.get("check_in", "").strip()
    check_out = request.form.get("check_out", "").strip()
    payment_method = request.form.get("payment_method", "Not specified")

    try:
        guests = int(request.form.get("guests", "0"))
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d").date()
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return "Invalid booking details.", 400

    if not all([name, email, phone]):
        return "Please fill in all customer details.", 400

    if room_type not in ROOM_CAPACITY:
        return "Invalid room type.", 400

    if guests < 1 or guests > ROOM_CAPACITY[room_type]:
        return render_template(
            "capacity_error.html",
            room_type=room_type,
            capacity=ROOM_CAPACITY[room_type]
        )

    nights = (check_out_date - check_in_date).days

    if nights <= 0 or check_in_date < date.today():
        return "Please select valid future booking dates.", 400

    connection = get_db_connection()

    try:
        if not check_room_availability(
            connection, room_type, check_in, check_out
        ):
            return render_template(
                "not_available.html",
                room_type=room_type,
                check_in=check_in,
                check_out=check_out
            )

        room = get_room_price(connection, room_type)

        if room is None:
            return "Room not found.", 404

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
                status,
                is_demo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending', 0)
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


# ==========================================================
# CUSTOMER BOOKING CANCELLATION
# ==========================================================

@app.route("/cancel_booking", methods=["GET", "POST"])
def cancel_booking():

    if request.method == "POST":

        booking_id = request.form.get("booking_id", "").strip()

        if not booking_id.isdigit():
            return "Please enter a valid booking ID.", 400

        connection = get_db_connection()

        booking = connection.execute("""
            SELECT * FROM bookings
            WHERE id = ?
        """, (booking_id,)).fetchone()

        if booking is None:
            connection.close()
            return """
                <h2 style="text-align:center;margin-top:50px;">
                    Booking not found.
                </h2>
                <p style="text-align:center;">
                    <a href="/cancel_booking">Try Again</a>
                </p>
            """

        if booking["status"] == "Cancelled":
            connection.close()
            return "This booking is already cancelled.", 400

        connection.execute("""
            UPDATE bookings
            SET status = 'Cancelled'
            WHERE id = ?
        """, (booking_id,))

        connection.commit()
        connection.close()

        return render_template(
            "cancel_success.html",
            booking_id=booking_id
        )

    return render_template("cancel_booking.html")


# ==========================================================
# CUSTOMER REVIEW PAGE
# ==========================================================

@app.route("/review")
def review():
    return render_template("review.html")


# ==========================================================
# CUSTOMER REVIEW SUBMISSION
# ==========================================================

@app.route("/submit_review", methods=["POST"])
def submit_review():

    booking_id = request.form.get("booking_id", "").strip()
    email = request.form.get("email", "").strip()
    feedback = request.form.get("feedback", "").strip()

    try:
        rating = int(request.form.get("rating", "0"))
    except ValueError:
        return "Please select a valid rating.", 400

    if not booking_id.isdigit() or not email:
        return "Please enter a valid booking ID and email.", 400

    if rating not in range(1, 6):
        return "Please select a rating from 1 to 5.", 400

    if len(feedback) < 5 or len(feedback) > 1000:
        return "Feedback must contain 5 to 1000 characters.", 400

    connection = get_db_connection()

    try:
        booking = connection.execute("""
            SELECT *
            FROM bookings
            WHERE id = ?
              AND LOWER(TRIM(email)) = LOWER(TRIM(?))
        """, (booking_id, email)).fetchone()

        if booking is None:
            return "Booking not found. Check your booking ID and email.", 404

        if booking["status"] != "Confirmed":
            return "Only confirmed bookings can submit reviews.", 400

        if booking["check_out"] >= date.today().isoformat():
            return "You can submit feedback after your check-out date.", 400

        existing_review = connection.execute("""
            SELECT id FROM reviews
            WHERE booking_id = ?
        """, (booking_id,)).fetchone()

        if existing_review:
            return "A review has already been submitted for this booking.", 409

        connection.execute("""
            INSERT INTO reviews (
                booking_id,
                customer_name,
                email,
                rating,
                feedback,
                created_at,
                is_demo
            )
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (
            booking_id,
            booking["customer_name"],
            booking["email"],
            rating,
            feedback,
            datetime.now().isoformat()
        ))

        connection.commit()

    finally:
        connection.close()

    return """
        <h2>Thank you for your feedback!</h2>
        <p>Your review has been submitted successfully.</p>
        <a href="/">Return to Grand Stay</a>
    """


# ==========================================================
# ADMIN LOGIN
# ==========================================================

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


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@app.route("/admin")
def admin():

    if not admin_required():
        return redirect(url_for("admin_login"))

    connection = get_db_connection()

    bookings = connection.execute("""
        SELECT *
        FROM bookings
        ORDER BY id DESC
    """).fetchall()

    total_bookings = connection.execute("""
        SELECT COUNT(*) AS count
        FROM bookings
        WHERE status != 'Cancelled'
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

    review_stats = connection.execute("""
        SELECT
            COUNT(*) AS total_reviews,
            ROUND(AVG(rating), 1) AS average_rating
        FROM reviews
    """).fetchone()

    connection.close()

    return render_template(
        "admin.html",
        bookings=bookings,
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        standard_bookings=standard_bookings,
        deluxe_bookings=deluxe_bookings,
        luxury_bookings=luxury_bookings,
        total_reviews=review_stats["total_reviews"],
        average_rating=review_stats["average_rating"] or 0
    )


# ==========================================================
# ADMIN UPDATE BOOKING STATUS
# ==========================================================

@app.route(
    "/admin/update_booking_status/<int:booking_id>",
    methods=["POST"]
)
def update_booking_status(booking_id):

    if not admin_required():
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status", "")

    if new_status not in BOOKING_STATUSES:
        flash("Invalid booking status.", "error")
        return redirect(url_for("admin"))

    connection = get_db_connection()

    connection.execute("""
        UPDATE bookings
        SET status = ?
        WHERE id = ?
    """, (new_status, booking_id))

    connection.commit()
    connection.close()

    flash("Booking status updated successfully.", "success")

    return redirect(url_for("admin"))


# ==========================================================
# ADMIN CUSTOMER MANAGEMENT
# ==========================================================

@app.route("/admin/customers")
def admin_customers():

    if not admin_required():
        return redirect(url_for("admin_login"))

    search = request.args.get("search", "").strip()

    connection = get_db_connection()

    if search:
        customers = connection.execute("""
            SELECT
                email,
                customer_name,
                phone,
                COUNT(*) AS booking_count,
                COALESCE(SUM(
                    CASE WHEN status != 'Cancelled'
                    THEN total_amount ELSE 0 END
                ), 0) AS booking_value,
                MAX(is_demo) AS has_demo_record
            FROM bookings
            WHERE customer_name LIKE ?
               OR email LIKE ?
               OR phone LIKE ?
            GROUP BY email
            ORDER BY customer_name
        """, (f"%{search}%", f"%{search}%", f"%{search}%")).fetchall()
    else:
        customers = connection.execute("""
            SELECT
                email,
                customer_name,
                phone,
                COUNT(*) AS booking_count,
                COALESCE(SUM(
                    CASE WHEN status != 'Cancelled'
                    THEN total_amount ELSE 0 END
                ), 0) AS booking_value,
                MAX(is_demo) AS has_demo_record
            FROM bookings
            GROUP BY email
            ORDER BY customer_name
        """).fetchall()

    connection.close()

    return render_template(
        "admin_customers.html",
        customers=customers,
        search=search
    )


# ==========================================================
# ADMIN REVIEW MANAGEMENT
# ==========================================================

@app.route("/admin/reviews")
def admin_reviews():

    if not admin_required():
        return redirect(url_for("admin_login"))

    connection = get_db_connection()

    reviews = connection.execute("""
        SELECT *
        FROM reviews
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "admin_reviews.html",
        reviews=reviews
    )


@app.route(
    "/admin/delete_review/<int:review_id>",
    methods=["POST"]
)
def delete_review(review_id):

    if not admin_required():
        return redirect(url_for("admin_login"))

    connection = get_db_connection()

    connection.execute("""
        DELETE FROM reviews
        WHERE id = ?
    """, (review_id,))

    connection.commit()
    connection.close()

    flash("Review deleted successfully.", "success")

    return redirect(url_for("admin_reviews"))


# ==========================================================
# CREATE 10 DEMO CUSTOMERS, BOOKINGS AND REVIEWS
# ==========================================================

@app.route("/admin/create_demo_data", methods=["POST"])
def create_demo_data():

    if not admin_required():
        return redirect(url_for("admin_login"))

    demo_customers = [
        (
            "Priya Sharma", "priya.demo@example.com", "9000000001",
            "Standard Room", 5,
            "The room was clean and comfortable. Excellent experience!"
        ),
        (
            "Rahul Verma", "rahul.demo@example.com", "9000000002",
            "Deluxe Room", 4,
            "Good service and comfortable rooms. Enjoyed my stay."
        ),
        (
            "Ananya Reddy", "ananya.demo@example.com", "9000000003",
            "Luxury Suite", 5,
            "Beautiful suite, friendly staff and wonderful hospitality."
        ),
        (
            "Karthik Kumar", "karthik.demo@example.com", "9000000004",
            "Standard Room", 4,
            "A pleasant stay with good facilities."
        ),
        (
            "Sneha Patel", "sneha.demo@example.com", "9000000005",
            "Deluxe Room", 5,
            "Very clean room and excellent customer service."
        ),
        (
            "Arjun Rao", "arjun.demo@example.com", "9000000006",
            "Luxury Suite", 3,
            "The stay was good. Some improvements would make it better."
        ),
        (
            "Divya Nair", "divya.demo@example.com", "9000000007",
            "Standard Room", 5,
            "Comfortable room and peaceful atmosphere."
        ),
        (
            "Rohit Mehta", "rohit.demo@example.com", "9000000008",
            "Deluxe Room", 4,
            "Good experience and helpful staff."
        ),
        (
            "Meena Das", "meena.demo@example.com", "9000000009",
            "Standard Room", 3,
            "The room was fine and the overall experience was average."
        ),
        (
            "Vikas Singh", "vikas.demo@example.com", "9000000010",
            "Luxury Suite", 5,
            "Excellent luxury experience. Would definitely recommend!"
        )
    ]

    connection = get_db_connection()
    created_count = 0

    try:
        for index, customer in enumerate(demo_customers):

            name, email, phone, room_type, rating, feedback = customer

            existing = connection.execute("""
                SELECT id
                FROM bookings
                WHERE email = ? AND is_demo = 1
            """, (email,)).fetchone()

            if existing:
                continue

            room = get_room_price(connection, room_type)

            if room is None:
                continue

            checkout_date = date.today() - timedelta(days=2 + index)
            checkin_date = checkout_date - timedelta(days=2)

            total_amount = room["price"] * 2

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
                    status,
                    is_demo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed', 1)
            """, (
                name,
                email,
                phone,
                room_type,
                checkin_date.isoformat(),
                checkout_date.isoformat(),
                2,
                total_amount
            ))

            booking_id = cursor.lastrowid

            connection.execute("""
                INSERT INTO reviews (
                    booking_id,
                    customer_name,
                    email,
                    rating,
                    feedback,
                    created_at,
                    is_demo
                )
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (
                booking_id,
                name,
                email,
                rating,
                feedback,
                datetime.now().isoformat()
            ))

            created_count += 1

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return (
        f"Created {created_count} demo customers, bookings and reviews. "
        f"{len(demo_customers) - created_count} demo records already existed."
    )


# ==========================================================
# ADMIN DELETE BOOKING
# ==========================================================

@app.route(
    "/delete_booking/<int:booking_id>",
    methods=["POST"]
)
def delete_booking(booking_id):

    if not admin_required():
        return redirect(url_for("admin_login"))

    connection = get_db_connection()

    connection.execute("""
        DELETE FROM bookings
        WHERE id = ?
    """, (booking_id,))

    connection.commit()
    connection.close()

    return redirect(url_for("admin"))


# ==========================================================
# ADMIN LOGOUT
# ==========================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(url_for("admin_login"))


# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":
    app.run(debug=True)
