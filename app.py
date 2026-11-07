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
