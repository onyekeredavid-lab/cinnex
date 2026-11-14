import getpass
import os
import secrets
import smtplib
import subprocess
import sys

import mysql.connector


def main():
    email_address = input("Gmail address: ").strip()
    gmail_app_password = getpass.getpass("Google App Password (input hidden): ").replace(" ", "")
    database_password = getpass.getpass("Cinnex database password (input hidden): ")
    if "@" not in email_address or not gmail_app_password or not database_password:
        print("Enter a Gmail address and both passwords to continue.")
        return 1

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(email_address, gmail_app_password)
    except (OSError, smtplib.SMTPException) as exc:
        print(f"Gmail SMTP check failed ({type(exc).__name__}). Check the address and Google App Password.")
        return 1

    os.environ.update(
        MYSQL_HOST="127.0.0.1",
        MYSQL_PORT="3306",
        MYSQL_DATABASE="cinnex",
        MYSQL_USER="cinnex_app",
        MYSQL_PASSWORD=database_password,
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT="587",
        SMTP_USERNAME=email_address,
        SMTP_PASSWORD=gmail_app_password,
        SMTP_FROM=email_address,
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
            cursor.execute("SELECT 1")
            database_ok = cursor.fetchone()[0] == 1
            cursor.close()
            connection.close()
        if not database_ok:
            print("MySQL connection check failed.")
            return 1
    except (mysql.connector.Error, RuntimeError) as exc:
        print(f"MySQL connection check failed ({type(exc).__name__}). Check the Cinnex database password.")
        return 1

    print("Gmail SMTP authentication passed.")
    print("MySQL connection passed.")
    print("Starting Cinnex for Business at http://127.0.0.1:8000")
    bind_address = os.environ.get("CINNEX_BIND", "0.0.0.0:8000")
    return subprocess.call([
        sys.executable,
        "-m",
        "gunicorn",
        "app:app",
        "--workers",
        "4",
        "--bind",
        bind_address,
    ])


if __name__ == "__main__":
    sys.exit(main())