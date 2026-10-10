import os
import time
from flask import Flask, jsonify, request, send_from_directory
import mysql.connector

app = Flask(__name__, static_folder="static")

DB_HOST = os.getenv("DB_HOST", "db")
DB_USER = os.getenv("DB_USER", "ticket_user")
DB_PASSWORD = os.getenv("DB_PASS", "ticket_pass")
DB_NAME = os.getenv("DB_NAME", "ticketing_db")

def get_db_connection():
    # Retry loop to wait for MySQL to fully boot up in Docker
    for _ in range(15):
        try:
            return mysql.connector.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                autocommit=False  # Crucial for explicit transactions!
            )
        except mysql.connector.Error:
            time.sleep(2)
    raise Exception("Could not connect to MySQL database.")

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/seats", methods=["GET"])
def get_seats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, seat_number, status, booked_by FROM seats ORDER BY seat_number ASC")
    seats = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(seats)

@app.route("/api/book", methods=["POST"])
def book_seat():
    data = request.json or {}
    seat_id = data.get("seat_id")
    user_name = data.get("user_name", "Anonymous")

    if not seat_id:
        return jsonify({"error": "Missing seat_id"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Start transaction & lock the targeted row exclusively
        cursor.execute("SELECT id, seat_number, status FROM seats WHERE id = %s FOR UPDATE", (seat_id,))
        seat = cursor.fetchone()

        if not seat:
            conn.rollback()
            return jsonify({"error": "Seat not found"}), 404

        if seat["status"] == "BOOKED":
            conn.rollback()
            return jsonify({"error": f"Seat {seat['seat_number']} is already booked!"}), 409

        # Update status
        cursor.execute(
            "UPDATE seats SET status = 'BOOKED', booked_by = %s WHERE id = %s",
            (user_name, seat_id)
        )
        conn.commit()
        return jsonify({"message": f"Seat {seat['seat_number']} successfully booked!", "seat_id": seat_id})

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)