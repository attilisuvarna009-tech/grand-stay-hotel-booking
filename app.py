# ---------------- ADMIN CUSTOMER MANAGEMENT ----------------

@app.route("/admin/customers")
def admin_customers():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    search = request.args.get("search", "").strip()
    selected_email = request.args.get("email", "").strip()

    connection = get_db_connection()

    # Show the selected customer's booking history when an email is selected
    customer_bookings = []
    selected_customer = None

    if selected_email:
        selected_customer = connection.execute("""
            SELECT
                MAX(customer_name) AS customer_name,
                email,
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

    # Search customers by name, email, or phone
    customers = connection.execute("""
        SELECT
            MAX(customer_name) AS customer_name,
            LOWER(TRIM(email)) AS email,
            MAX(phone) AS phone,
            COUNT(*) AS booking_count,
            COALESCE(SUM(total_amount), 0) AS total_booking_value
        FROM bookings
        WHERE email IS NOT NULL AND TRIM(email) != ''
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

    connection.close()

    return render_template(
        "admin_customers.html",
        customers=customers,
        search=search,
        selected_customer=selected_customer,
        customer_bookings=customer_bookings
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
