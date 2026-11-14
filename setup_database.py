import getpass
import os
import secrets
import sys

import mysql.connector


def main():
    root_password = getpass.getpass("MySQL root password (input hidden): ")
    app_password = getpass.getpass("Choose a strong Cinnex database password (input hidden): ")
    confirm_password = getpass.getpass("Confirm Cinnex database password: ")
    if len(app_password) < 16 or app_password != confirm_password:
        print("The app password must be at least 16 characters and both entries must match.")
        return 1

    root_connection = None
    cursor = None
    try:
        root_connection = mysql.connector.connect(
            host="127.0.0.1",
            port=3306,
            user="root",
            password=root_password,
            connection_timeout=5,
        )
        cursor = root_connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS cinnex CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'cinnex_app'@'127.0.0.1' IDENTIFIED BY %s",
            (app_password,),
        )
        cursor.execute(
            "ALTER USER 'cinnex_app'@'127.0.0.1' IDENTIFIED BY %s",
            (app_password,),
        )
        cursor.execute(
            "GRANT CREATE, ALTER, INDEX, SELECT, INSERT, UPDATE "
            "ON cinnex.* TO 'cinnex_app'@'127.0.0.1'"
        )
        root_connection.commit()
    except mysql.connector.Error as exc:
        print(f"MySQL setup failed ({type(exc).__name__}). Check the root password and MySQL permissions.")
        return 1
    finally:
        if cursor:
            cursor.close()
        if root_connection and root_connection.is_connected():
            root_connection.close()

    os.environ.update(
        MYSQL_HOST="127.0.0.1",
        MYSQL_PORT="3306",
        MYSQL_DATABASE="cinnex",
        MYSQL_USER="cinnex_app",
        MYSQL_PASSWORD=app_password,
        FLASK_SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    )

    try:
        try:
            from login_app import app
        except ModuleNotFoundError:
            from app import app
        from business_portal import db_connection

        with app.app_context():
            connection = db_connection()
            cursor = connection.cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            connection.close()
        required_tables = {"users", "rooms", "room_bookings", "business_policies", "business_orders", "invoices"}
        missing = required_tables - set(tables)
        if missing:
            print("Database connected, but required tables are missing: " + ", ".join(sorted(missing)))
            return 1
    except mysql.connector.Error as exc:
        print(f"Database schema test failed ({type(exc).__name__}). Check the Cinnex app user's grants.")
        return 1

    print("MySQL connection passed. Cinnex tables are ready: " + ", ".join(sorted(required_tables)))
    print("Starting Cinnex for Business at http://127.0.0.1:5003")
    app.run(host="127.0.0.1", port=5003, debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())