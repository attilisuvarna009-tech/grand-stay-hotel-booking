
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
        WHERE is_demo = 0
    """).fetchone()

    latest_reviews = connection.execute("""
        SELECT customer_name, rating, feedback, created_at
        FROM reviews
        WHERE is_demo = 0
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

    # All review errors return to the styled review page.
    def review_error(message):
        flash(message, "error")
        return redirect(url_for("review"))

    try:
        rating = int(request.form.get("rating", "0"))
    except (ValueError, TypeError):
        return review_error("Please select a valid rating.")

    if not booking_id.isdigit() or not email:
        return review_error(
            "Please enter a valid booking ID and email."
        )

    if rating not in range(1, 6):
        return review_error("Please select a rating from 1 to 5.")

    if len(feedback) < 5 or len(feedback) > 1000:
        return review_error(
            "Feedback must contain 5 to 1000 characters."
        )

    connection = get_db_connection()

    try:
        booking = connection.execute("""
            SELECT *
            FROM bookings
            WHERE id = ?
              AND LOWER(TRIM(email)) = LOWER(TRIM(?))
        """, (booking_id, email)).fetchone()

        if booking is None:
            return review_error(
                "Booking not found. Check your booking ID and email."
            )

        if booking["status"] != "Confirmed":
            return review_error(
                "Only confirmed bookings can submit reviews. "
                "Please contact the hotel if you need help."
            )

        if booking["check_out"] >= date.today().isoformat():
            return review_error(
                "You can submit feedback after your check-out date."
            )

        existing_review = connection.execute("""
            SELECT id
            FROM reviews
            WHERE booking_id = ?
        """, (booking_id,)).fetchone()

        if existing_review:
            return review_error(
                "A review has already been submitted for this booking."
            )

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

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Review submission failed.")

        return review_error(
            "We could not save your review. Please try again later."
        )

    finally:
        connection.close()

    flash(
        "Thank you! Your review has been submitted successfully.",
        "success"
    )

    return redirect(url_for("review"))


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
# CREATE OR REPLACE 10 DEMO CUSTOMERS, BOOKINGS AND REVIEWS
# ==========================================================

@app.route("/admin/create_demo_data", methods=["POST"])
def create_demo_data():

    if not admin_required():
        return redirect(url_for("admin_login"))

    demo_customers = [
        {
            "name": "Priya Sharma",
            "email": "priya.demo@example.com",
            "phone": "9000000001",
            "room": "Standard Room",
            "guests": 2,
            "nights": 2,
            "days_ago": 15,
            "rating": 5,
            "feedback": (
                "I had a very comfortable stay at Grand Stay. "
                "The room was clean, the bed was comfortable, "
                "and the staff were polite and helpful. "
                "The check-in process was also smooth."
            )
        },
        {
            "name": "Rahul Verma",
            "email": "rahul.demo@example.com",
            "phone": "9000000002",
            "room": "Deluxe Room",
            "guests": 2,
            "nights": 3,
            "days_ago": 20,
            "rating": 4,
            "feedback": (
                "The Deluxe Room was spacious and well maintained. "
                "Room service was quick and the staff were friendly. "
                "Overall, it was a pleasant experience."
            )
        },
        {
            "name": "Ananya Reddy",
            "email": "ananya.demo@example.com",
            "phone": "9000000003",
            "room": "Luxury Suite",
            "guests": 3,
            "nights": 2,
            "days_ago": 25,
            "rating": 5,
            "feedback": (
                "The Luxury Suite was beautiful and comfortable. "
                "The interior was impressive, and the housekeeping "
                "team did an excellent job. I enjoyed the hospitality."
            )
        },
        {
            "name": "Karthik Kumar",
            "email": "karthik.demo@example.com",
            "phone": "9000000004",
            "room": "Standard Room",
            "guests": 1,
            "nights": 1,
            "days_ago": 30,
            "rating": 4,
            "feedback": (
                "A good hotel for a short stay. The room was tidy, "
                "the check-in was simple, and the staff were helpful. "
                "I would consider staying here again."
            )
        },
        {
            "name": "Sneha Patel",
            "email": "sneha.demo@example.com",
            "phone": "9000000005",
            "room": "Deluxe Room",
            "guests": 3,
            "nights": 2,
            "days_ago": 35,
            "rating": 5,
            "feedback": (
                "I really liked the cleanliness and atmosphere "
                "of the hotel. The room was comfortable, and the "
                "staff responded quickly whenever we needed help."
            )
        },
        {
            "name": "Arjun Rao",
            "email": "arjun.demo@example.com",
            "phone": "9000000006",
            "room": "Luxury Suite",
            "guests": 2,
            "nights": 3,
            "days_ago": 40,
            "rating": 3,
            "feedback": (
                "The suite was spacious and the location was convenient. "
                "However, room service took longer than expected. "
                "The overall stay was satisfactory."
            )
        },
        {
            "name": "Divya Nair",
            "email": "divya.demo@example.com",
            "phone": "9000000007",
            "room": "Standard Room",
            "guests": 2,
            "nights": 2,
            "days_ago": 45,
            "rating": 5,
            "feedback": (
                "The room was neat and peaceful. The housekeeping "
                "staff maintained everything properly, and the "
                "front desk team was welcoming. A lovely stay."
            )
        },
        {
            "name": "Rohit Mehta",
            "email": "rohit.demo@example.com",
            "phone": "9000000008",
            "room": "Deluxe Room",
            "guests": 2,
            "nights": 1,
            "days_ago": 50,
            "rating": 4,
            "feedback": (
                "Good room, comfortable beds, and courteous staff. "
                "The booking and check-out processes were easy. "
                "I had a good overall experience."
            )
        },
        {
            "name": "Meena Das",
            "email": "meena.demo@example.com",
            "phone": "9000000009",
            "room": "Standard Room",
            "guests": 1,
            "nights": 2,
            "days_ago": 55,
            "rating": 3,
            "feedback": (
                "The room was clean and suitable for a short visit. "
                "Some facilities could be improved, but the staff "
                "were polite and the stay was satisfactory."
            )
        },
        {
            "name": "Vikas Singh",
            "email": "vikas.demo@example.com",
            "phone": "9000000010",
            "room": "Luxury Suite",
            "guests": 4,
            "nights": 2,
            "days_ago": 60,
            "rating": 5,
            "feedback": (
                "The suite offered plenty of space for our family. "
                "The room was comfortable and well maintained. "
                "The staff made the stay pleasant and relaxing."
            )
        }
    ]

    connection = get_db_connection()

    try:
        connection.execute("""
            DELETE FROM reviews
            WHERE is_demo = 1
               OR booking_id IN (
                    SELECT id
                    FROM bookings
                    WHERE is_demo = 1
               )
        """)

        connection.execute("""
            DELETE FROM bookings
            WHERE is_demo = 1
        """)

        created_count = 0

        for customer in demo_customers:

            room = get_room_price(connection, customer["room"])

            if room is None:
                raise ValueError(
                    f"Room not found: {customer['room']}"
                )

            checkout_date = date.today() - timedelta(
                days=customer["days_ago"]
            )

            checkin_date = checkout_date - timedelta(
                days=customer["nights"]
            )

            total_amount = room["price"] * customer["nights"]

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
                customer["name"],
                customer["email"],
                customer["phone"],
                customer["room"],
                checkin_date.isoformat(),
                checkout_date.isoformat(),
                customer["guests"],
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
                customer["name"],
                customer["email"],
                customer["rating"],
                customer["feedback"],
                checkout_date.isoformat()
            ))

            created_count += 1

        connection.commit()

        flash(
            f"Successfully refreshed {created_count} demo customers, "
            "bookings and reviews. Genuine customer records were preserved.",
            "success"
        )

    except Exception:
        connection.rollback()
        app.logger.exception("Demo data generation failed.")
        flash(
            "Unable to generate demo data. No changes were saved. "
            "Please check the application logs.",
            "error"
        )

    finally:
        connection.close()

    return redirect(url_for("admin"))


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

    flash("Booking deleted successfully.", "success")

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
