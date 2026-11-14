import os
import re
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

import mysql.connector
from flask import Flask, render_template_string, request, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, static_folder="static")
app.config.update(
  SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
  SESSION_COOKIE_HTTPONLY=True,
  SESSION_COOKIE_SAMESITE="Lax",
  SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
)


def init_auth(flask_app, roles=None):
  configured_roles = tuple(roles or ("admin", "manager", "staff", "customer"))
  if not configured_roles or len(set(configured_roles)) != len(configured_roles):
    raise ValueError("Auth roles must be a non-empty list without duplicates.")
  if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,19}", role) for role in configured_roles):
    raise ValueError("Auth roles must use lowercase letters, numbers, or underscores.")
  flask_app.config["AUTH_ROLES"] = configured_roles
  flask_app.config["AUTH_DEFAULT_ROLE"] = "customer" if "customer" in configured_roles else configured_roles[-1]
  return flask_app


init_auth(app, roles=["admin", "manager", "staff", "customer"])


def get_db_connection():
  password = os.environ.get("MYSQL_PASSWORD")
  username = os.environ.get("MYSQL_USER")
  if not username or password is None:
    raise RuntimeError("Set MYSQL_USER and MYSQL_PASSWORD before starting the app.")

  connection = mysql.connector.connect(
    host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
    port=int(os.environ.get("MYSQL_PORT", "3306")),
    user=username,
    password=password,
    database=os.environ.get("MYSQL_DATABASE", "cinnex"),
    connection_timeout=5,
  )
  cursor = connection.cursor()
  try:
    cursor.execute("""
      CREATE TABLE IF NOT EXISTS users (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(80) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        email VARCHAR(254) NULL,
        phone_number VARCHAR(16) NULL,
        email_verified BOOLEAN NOT NULL DEFAULT FALSE,
        phone_verified BOOLEAN NOT NULL DEFAULT FALSE,
        email_otp_hash VARCHAR(255) NULL,
        phone_otp_hash VARCHAR(255) NULL,
        otp_expires_at DATETIME NULL,
        otp_sent_at DATETIME NULL,
        otp_attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
                role VARCHAR(20) NOT NULL DEFAULT 'customer',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_users_email (email),
        UNIQUE KEY uq_users_phone_number (phone_number)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("SHOW COLUMNS FROM users")
    columns = {row[0] for row in cursor.fetchall()}
    migrations = {
      "email": "VARCHAR(254) NULL",
      "phone_number": "VARCHAR(16) NULL",
      "email_verified": "BOOLEAN NOT NULL DEFAULT FALSE",
      "phone_verified": "BOOLEAN NOT NULL DEFAULT FALSE",
      "email_otp_hash": "VARCHAR(255) NULL",
      "phone_otp_hash": "VARCHAR(255) NULL",
      "otp_expires_at": "DATETIME NULL",
      "otp_sent_at": "DATETIME NULL",
      "otp_attempts": "TINYINT UNSIGNED NOT NULL DEFAULT 0",
                "role": "VARCHAR(20) NOT NULL DEFAULT 'customer'",
                "is_active": "BOOLEAN NOT NULL DEFAULT TRUE",
    }
    for column, definition in migrations.items():
      if column not in columns:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")

    cursor.execute("SHOW INDEX FROM users")
    indexes = {row[2] for row in cursor.fetchall()}
    if "uq_users_email" not in indexes:
      cursor.execute("CREATE UNIQUE INDEX uq_users_email ON users (email)")
    if "uq_users_phone_number" not in indexes:
      cursor.execute("CREATE UNIQUE INDEX uq_users_phone_number ON users (phone_number)")
    connection.commit()
  finally:
    cursor.close()
  return connection


def generate_otp():
  return f"{secrets.randbelow(1_000_000):06d}"


def send_verification_code(email_address, email_code):
  smtp_host = os.environ.get("SMTP_HOST")
  smtp_username = os.environ.get("SMTP_USERNAME")
  smtp_password = os.environ.get("SMTP_PASSWORD")
  smtp_from = os.environ.get("SMTP_FROM", smtp_username or "")
  if not all((smtp_host, smtp_username, smtp_password, smtp_from)):
    raise RuntimeError("Email delivery is not configured.")

  message = EmailMessage()
  message["Subject"] = "Your Cinnex verification code"
  message["From"] = smtp_from
  message["To"] = email_address
  message.set_content(f"Your Cinnex email verification code is {email_code}. It expires in 10 minutes.")
  try:
    with smtplib.SMTP(smtp_host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as server:
      server.starttls()
      server.login(smtp_username, smtp_password)
      server.send_message(message)
  except Exception as exc:
    raise RuntimeError("The verification email could not be delivered. Check your SMTP settings.") from exc


def valid_otp(code, stored_hash):
  return bool(code and stored_hash and check_password_hash(stored_hash, code))


@app.route("/", methods=["GET", "POST"])
def login_page():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        connection = None
        cursor = None
        try:
          connection = get_db_connection()
          cursor = connection.cursor(dictionary=True)
          cursor.execute(
            "SELECT id, username, password_hash, email_verified, role, is_active FROM users WHERE username = %s",
            (username,),
          )
          user = cursor.fetchone()
          if user and check_password_hash(user["password_hash"], password) and user["is_active"]:
            session.clear()
            if not user["email_verified"]:
              session["pending_user_id"] = user["id"]
              return redirect(url_for("verify_page"))
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
          error = "Invalid username or password."
        except (mysql.connector.Error, RuntimeError):
          error = "The database is unavailable. Check your MySQL settings and try again."
        finally:
          if cursor:
            cursor.close()
          if connection and connection.is_connected():
            connection.close()

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Login</title>
      <style>
        * { box-sizing: border-box; }
        body {
          margin: 0;
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: Arial, sans-serif;
          background: linear-gradient(135deg, #0f172a, #1d4ed8, #7c3aed);
          color: white;
        }
        .login-box {
          width: min(90%, 420px);
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid rgba(148, 163, 184, 0.25);
          border-radius: 18px;
          padding: 32px 28px;
          box-shadow: 0 22px 60px rgba(0,0,0,0.35);
        }
        .brand {
          text-align: center;
          margin-bottom: 18px;
        }
        .brand img {
          width: 220px;
          height: auto;
          display: block;
          margin: 0 auto 12px auto;
        }
        h1 {
          text-align: center;
          margin-bottom: 22px;
          font-size: 2rem;
        }
        form {
          display: grid;
          gap: 14px;
        }
        input {
          width: 100%;
          padding: 12px 14px;
          border-radius: 10px;
          border: 1px solid rgba(148, 163, 184, 0.35);
          background: rgba(15, 23, 42, 0.6);
          color: white;
          font-size: 16px;
        }
        input::placeholder {
          color: #cbd5e1;
        }
        button {
          padding: 12px 14px;
          border: none;
          border-radius: 10px;
          background: linear-gradient(135deg, #22c55e, #16a34a);
          color: white;
          font-size: 16px;
          font-weight: bold;
          cursor: pointer;
        }
        .error {
          background: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.4);
          color: #fecaca;
          border-radius: 10px;
          padding: 10px 12px;
          text-align: center;
        }
        .links {
          margin-top: 16px;
          display: flex;
          justify-content: space-between;
          gap: 12px;
          font-size: 0.9rem;
        }
        .links a {
          color: #bfdbfe;
          text-decoration: none;
        }
        .hint {
          margin-top: 16px;
          text-align: center;
          color: #dbeafe;
          font-size: 0.9rem;
        }
      </style>
    </head>
    <body>
      <div class="login-box">
        <div class="brand">
          <img src="{{ url_for('static', filename='cinnex_logo.svg') }}" alt="Cinnex logo">
        </div>
        <h1>Login</h1>

        {% if error %}
          <div class="error">{{ error }}</div>
        {% endif %}

        <form method="POST">
          <input type="text" name="username" placeholder="Username" required>
          <input type="password" name="password" placeholder="Password" required>
          <button type="submit">Sign In</button>
        </form>

        <div class="links">
          <a href="/register">Create account</a>
          {% if show_demo_preview %}<a href="{{ url_for('business.dashboard_preview') }}">Preview dashboard</a>{% endif %}
        </div>

      </div>
    </body>
    </html>
    ''', error=error, show_demo_preview=request.remote_addr in {"127.0.0.1", "::1"})


@app.route("/register", methods=["GET", "POST"])
def register_page():
    error = None
    success = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email_address = request.form.get("email", "").strip().lower()
        phone_number = request.form.get("phone_number", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email_address or not password.strip():
            error = "Please fill in all fields."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif len(username) > 80:
            error = "Username must be 80 characters or fewer."
        elif not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email_address):
            error = "Enter a valid email address."
        elif phone_number and not re.fullmatch(r"\+[1-9]\d{7,14}", phone_number):
          error = "Enter a mobile number in international format, such as +14155552671, or leave it blank."
        elif len(password) < 8:
            error = "Use a password with at least 8 characters."
        else:
            connection = None
            cursor = None
            try:
                email_code = generate_otp()
                now = datetime.now()
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute(
                      """INSERT INTO users
                        (username, password_hash, email, phone_number,
                        email_otp_hash, otp_expires_at, otp_sent_at, role)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        username,
                        generate_password_hash(password),
                        email_address,
                        phone_number or None,
                        generate_password_hash(email_code),
                        now + timedelta(minutes=10),
                        now,
                        app.config["AUTH_DEFAULT_ROLE"],
                    ),
                )
                user_id = cursor.lastrowid
                connection.commit()
                session.clear()
                session["pending_user_id"] = user_id
                try:
                    send_verification_code(email_address, email_code)
                except RuntimeError as exc:
                    session["otp_notice"] = str(exc)
                return redirect(url_for("verify_page"))
            except mysql.connector.IntegrityError:
                error = "That username, email, or mobile number is already registered."
            except (mysql.connector.Error, RuntimeError):
                error = "The database is unavailable. Check your MySQL settings and try again."
            finally:
                if cursor:
                    cursor.close()
                if connection and connection.is_connected():
                    connection.close()

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Register</title>
      <style>
        * { box-sizing: border-box; }
        body {
          margin: 0;
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: Arial, sans-serif;
          background: linear-gradient(135deg, #0f172a, #1d4ed8, #7c3aed);
          color: white;
        }
        .box {
          width: min(90%, 440px);
          background: rgba(15, 23, 42, 0.7);
          border-radius: 18px;
          padding: 30px 26px;
          box-shadow: 0 22px 60px rgba(0,0,0,0.35);
        }
        .brand img {
          width: 190px;
          display: block;
          margin: 0 auto 18px auto;
        }
        h1 {
          text-align: center;
          margin-bottom: 18px;
        }
        form {
          display: grid;
          gap: 12px;
        }
        input, button {
          width: 100%;
          padding: 12px 14px;
          border-radius: 10px;
          border: none;
          font-size: 16px;
        }
        input {
          background: rgba(15, 23, 42, 0.6);
          border: 1px solid rgba(148, 163, 184, 0.35);
          color: white;
        }
        input::placeholder { color: #cbd5e1; }
        button {
          background: linear-gradient(135deg, #3b82f6, #8b5cf6);
          color: white;
          font-weight: bold;
          cursor: pointer;
        }
        .message {
          margin-top: 12px;
          padding: 10px 12px;
          border-radius: 10px;
          text-align: center;
        }
        .error { background: rgba(239,68,68,0.14); color: #fecaca; }
        .success { background: rgba(34,197,94,0.16); color: #bbf7d0; }
        .link {
          margin-top: 14px;
          text-align: center;
        }
        .link a { color: #bfdbfe; text-decoration: none; }
      </style>
    </head>
    <body>
      <div class="box">
        <div class="brand">
          <img src="{{ url_for('static', filename='cinnex_logo.svg') }}" alt="Cinnex logo">
        </div>
        <h1>Create account</h1>

        {% if error %}
          <div class="message error">{{ error }}</div>
        {% elif success %}
          <div class="message success">{{ success }}</div>
        {% endif %}

        <form method="POST">
          <input type="text" name="username" placeholder="Username" required>
          <input type="email" name="email" placeholder="Email address" autocomplete="email" required>
          <input type="tel" name="phone_number" placeholder="Mobile number (optional), e.g. +14155552671" autocomplete="tel">
          <input type="password" name="password" placeholder="Password" required>
          <input type="password" name="confirm_password" placeholder="Confirm password" required>
          <button type="submit">Register</button>
        </form>

        <div class="link"><a href="/">Back to login</a></div>
      </div>
    </body>
    </html>
    ''', error=error, success=success)


@app.route("/verify", methods=["GET", "POST"])
def verify_page():
  user_id = session.get("pending_user_id")
  if not user_id:
    return redirect(url_for("register_page"))

  error = None
  notice = session.pop("otp_notice", None)
  connection = None
  cursor = None
  try:
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
                  """SELECT id, username, email_verified, role,
                    email_otp_hash, otp_expires_at, otp_attempts
         FROM users WHERE id = %s""",
      (user_id,),
    )
    user = cursor.fetchone()
    if not user:
      session.clear()
      return redirect(url_for("register_page"))

    if request.method == "POST":
      email_code = request.form.get("email_code", "").strip()
      if user["otp_attempts"] >= 5:
        error = "Too many incorrect attempts. Request new codes to try again."
      elif not user["otp_expires_at"] or datetime.now() > user["otp_expires_at"]:
        error = "Your code has expired. Request a new code."
      elif not valid_otp(email_code, user["email_otp_hash"]):
        cursor.execute(
          "UPDATE users SET otp_attempts = otp_attempts + 1 WHERE id = %s",
          (user_id,),
        )
        connection.commit()
        error = "The verification code is incorrect."
      else:
        cursor.execute(
              """UPDATE users SET email_verified = TRUE,
                email_otp_hash = NULL,
                otp_expires_at = NULL, otp_attempts = 0
             WHERE id = %s""",
          (user_id,),
        )
        connection.commit()
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        return redirect(url_for("dashboard"))
  except (mysql.connector.Error, RuntimeError):
    error = "The database is unavailable. Check your MySQL settings and try again."
  finally:
    if cursor:
      cursor.close()
    if connection and connection.is_connected():
      connection.close()

  return render_template_string('''
  <!doctype html>
  <html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Verify Email</title>
    <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 20px;
      font-family: Arial, sans-serif;
      background: linear-gradient(135deg, #0f172a, #1d4ed8, #7c3aed);
      color: white;
    }
    .box {
      width: min(100%, 440px);
      background: rgba(15, 23, 42, 0.82);
      border: 1px solid rgba(148, 163, 184, 0.25);
      border-radius: 16px;
      padding: 28px;
      box-shadow: 0 22px 60px rgba(0,0,0,0.35);
    }
    img { width: min(190px, 70%); display: block; margin: 0 auto 18px; }
    h1, p { text-align: center; }
    p { color: #dbeafe; line-height: 1.5; }
    form { display: grid; gap: 12px; margin-top: 18px; }
    input, button {
      width: 100%;
      padding: 12px;
      border-radius: 8px;
      font-size: 16px;
    }
    input {
      border: 1px solid rgba(148, 163, 184, 0.4);
      background: rgba(15, 23, 42, 0.7);
      color: white;
    }
    button { border: 0; background: #16a34a; color: white; font-weight: bold; cursor: pointer; }
    .error, .notice { padding: 10px; border-radius: 8px; text-align: center; }
    .error { background: rgba(239,68,68,0.18); color: #fecaca; }
    .notice { background: rgba(59,130,246,0.18); color: #dbeafe; }
    .resend { margin-top: 12px; }
    </style>
  </head>
  <body>
    <main class="box">
    <img src="{{ url_for('static', filename='cinnex_logo.svg') }}" alt="Cinnex logo">
    <h1>Verify your email</h1>
    <p>Enter the six-digit code sent to your email. It expires after 10 minutes.</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if notice %}<div class="notice">{{ notice }}</div>{% endif %}
    <form method="POST">
      <input name="email_code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" placeholder="Email code" autocomplete="one-time-code" required>
      <button type="submit">Verify and continue</button>
    </form>
    <form class="resend" method="POST" action="{{ url_for('resend_codes') }}">
      <button type="submit">Resend codes</button>
    </form>
    </main>
  </body>
  </html>
  ''', error=error, notice=notice)


@app.route("/resend-codes", methods=["POST"])
def resend_codes():
  user_id = session.get("pending_user_id")
  if not user_id:
    return redirect(url_for("register_page"))

  connection = None
  cursor = None
  try:
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
      "SELECT email, otp_sent_at FROM users WHERE id = %s",
      (user_id,),
    )
    user = cursor.fetchone()
    if not user:
      session.clear()
      return redirect(url_for("register_page"))

    now = datetime.now()
    if user["otp_sent_at"] and now - user["otp_sent_at"] < timedelta(seconds=60):
      session["otp_notice"] = "Please wait 60 seconds between code requests."
      return redirect(url_for("verify_page"))

    email_code = generate_otp()
    cursor.execute(
      """UPDATE users SET email_otp_hash = %s,
            otp_expires_at = %s, otp_sent_at = %s, otp_attempts = 0
         WHERE id = %s""",
      (
        generate_password_hash(email_code),
        now + timedelta(minutes=10),
        now,
        user_id,
      ),
    )
    connection.commit()
    try:
      send_verification_code(user["email"], email_code)
    except RuntimeError as exc:
      session["otp_notice"] = str(exc)
    else:
      session["otp_notice"] = "New verification codes sent."
  except (mysql.connector.Error, RuntimeError):
    session["otp_notice"] = "Could not request a new code. Check the database and email settings."
  finally:
    if cursor:
      cursor.close()
    if connection and connection.is_connected():
      connection.close()
  return redirect(url_for("verify_page"))


@app.route("/change-password", methods=["GET", "POST"])
def change_password_page():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    error = None
    success = None

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "")

        if not current_password or not new_password:
            error = "Please fill in all fields."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        elif len(new_password) < 8:
            error = "Use a password with at least 8 characters."
        else:
            connection = None
            cursor = None
            try:
                connection = get_db_connection()
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    "SELECT password_hash FROM users WHERE id = %s",
                    (session["user_id"],),
                )
                user = cursor.fetchone()
                if not user or not check_password_hash(user["password_hash"], current_password):
                    error = "Current password is incorrect."
                else:
                    cursor.execute(
                        "UPDATE users SET password_hash = %s WHERE id = %s",
                        (generate_password_hash(new_password), session["user_id"]),
                    )
                    connection.commit()
                    success = "Password updated successfully."
            except (mysql.connector.Error, RuntimeError):
                error = "The database is unavailable. Check your MySQL settings and try again."
            finally:
                if cursor:
                    cursor.close()
                if connection and connection.is_connected():
                    connection.close()

    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Change Password</title>
      <style>
        * { box-sizing: border-box; }
        body {
          margin: 0;
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: Arial, sans-serif;
          background: linear-gradient(135deg, #0f172a, #1d4ed8, #7c3aed);
          color: white;
        }
        .box {
          width: min(90%, 440px);
          background: rgba(15, 23, 42, 0.7);
          border-radius: 18px;
          padding: 30px 26px;
          box-shadow: 0 22px 60px rgba(0,0,0,0.35);
        }
        .brand img {
          width: 190px;
          display: block;
          margin: 0 auto 18px auto;
        }
        h1 {
          text-align: center;
          margin-bottom: 18px;
        }
        form {
          display: grid;
          gap: 12px;
        }
        input, button {
          width: 100%;
          padding: 12px 14px;
          border-radius: 10px;
          border: none;
          font-size: 16px;
        }
        input {
          background: rgba(15, 23, 42, 0.6);
          border: 1px solid rgba(148, 163, 184, 0.35);
          color: white;
        }
        input::placeholder { color: #cbd5e1; }
        button {
          background: linear-gradient(135deg, #f59e0b, #f97316);
          color: white;
          font-weight: bold;
          cursor: pointer;
        }
        .message {
          margin-top: 12px;
          padding: 10px 12px;
          border-radius: 10px;
          text-align: center;
        }
        .error { background: rgba(239,68,68,0.14); color: #fecaca; }
        .success { background: rgba(34,197,94,0.16); color: #bbf7d0; }
        .link {
          margin-top: 14px;
          text-align: center;
        }
        .link a { color: #bfdbfe; text-decoration: none; }
      </style>
    </head>
    <body>
      <div class="box">
        <div class="brand">
          <img src="{{ url_for('static', filename='cinnex_logo.svg') }}" alt="Cinnex logo">
        </div>
        <h1>Change password</h1>

        {% if error %}
          <div class="message error">{{ error }}</div>
        {% elif success %}
          <div class="message success">{{ success }}</div>
        {% endif %}

        <form method="POST">
          <input type="password" name="current_password" placeholder="Current password" required>
          <input type="password" name="new_password" placeholder="New password" required>
          <input type="password" name="confirm_password" placeholder="Confirm new password" required>
          <button type="submit">Update Password</button>
        </form>

        <div class="link"><a href="/dashboard">Back to dashboard</a></div>
      </div>
    </body>
    </html>
    ''', error=error, success=success)


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    return redirect(url_for("business.dashboard"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login_page"))


app.config["DB_CONNECT"] = get_db_connection
from business_portal import portal

app.register_blueprint(portal)


if __name__ == "__main__":
  app.run(host="127.0.0.1", port=5003, debug=False)
