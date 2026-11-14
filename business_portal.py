import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from ipaddress import ip_address
from pathlib import Path
import secrets
from uuid import uuid4

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template_string, request, session, url_for
from mysql.connector import Error as MySQLError

portal = Blueprint("business", __name__, url_prefix="/business")

POS_DEMO_PRODUCTS = {
    "espresso": ("Espresso", "Cafe", 350),
    "latte": ("Caffe latte", "Cafe", 500),
    "tea": ("Herbal tea", "Cafe", 400),
    "sandwich": ("Club sandwich", "Cafe", 1500),
    "salad": ("Seasonal salad", "Cafe", 1350),
    "water": ("Sparkling water", "Minibar", 400),
    "snack": ("Local snack box", "Minibar", 850),
    "soda": ("Soft drink", "Minibar", 450),
    "kit": ("Travel essentials kit", "Minibar", 1200),
    "spa": ("Spa day pass", "Wellness", 4500),
    "parking": ("Overnight parking", "Services", 2800),
    "late": ("Late checkout", "Services", 3500),
}
POS_DEMO_PROPERTIES = {
    "Cinnex City · Lobby Cafe",
    "Cinnex Coast · Pool Bar",
    "Cinnex Airport · Market",
}
POS_DEMO_CSV = Path(__file__).resolve().parent / "hotel_pos_demo_sales.csv"

SHELL = '''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} | Cinnex for Business</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #f3f6f4; color: #172321; font: 15px/1.5 Arial, sans-serif; }
    header { background: #173b34; color: white; padding: 16px max(20px, calc((100vw - 1120px) / 2)); }
    .brand { display: flex; align-items: center; gap: 14px; }
    .brand img { width: 148px; height: auto; }
    .brand span { color: #c5d8cf; }
    nav { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
    nav a, nav button { color: white; background: #25574d; border: 0; border-radius: 5px; padding: 8px 11px; text-decoration: none; font: inherit; cursor: pointer; }
    nav a:hover, nav button:hover { background: #347567; }
    nav form { margin: 0 0 0 auto; }
    main { max-width: 1120px; margin: 28px auto; padding: 0 20px 40px; }
    h1 { font-size: 28px; margin: 0 0 20px; }
    h2 { font-size: 18px; margin: 0 0 14px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin-bottom: 22px; }
    .panel, .stat { background: white; border: 1px solid #dce5e0; border-radius: 6px; padding: 18px; }
    .stat strong { display: block; font-size: 28px; color: #17624f; }
    .stat span, .muted { color: #5d6e67; }
    .panel { margin-bottom: 18px; overflow-x: auto; }
    form.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; align-items: end; }
    label { display: grid; gap: 5px; font-weight: 600; }
    input, select, textarea { width: 100%; border: 1px solid #bccbc3; border-radius: 4px; padding: 10px; background: white; color: #172321; font: inherit; }
    textarea { min-height: 110px; resize: vertical; }
    button.primary { border: 0; border-radius: 4px; background: #17624f; color: white; padding: 10px 14px; font: inherit; cursor: pointer; }
    button.primary:hover { background: #104b3c; }
    table { width: 100%; border-collapse: collapse; min-width: 650px; }
    th, td { text-align: left; vertical-align: top; border-bottom: 1px solid #e4ebe7; padding: 10px 9px; }
    th { color: #52645c; font-size: 13px; }
    td form { display: flex; align-items: center; gap: 6px; }
    td select { min-width: 105px; padding: 7px; }
    .message { padding: 10px 12px; margin-bottom: 14px; border-radius: 4px; background: #e6f4ee; color: #14523f; }
    .error { background: #fff0ed; color: #9b3023; }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; }
    .actions a { color: #17624f; }
    .chart-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; flex-wrap: wrap; }
    .chart-switch { display: inline-flex; gap: 4px; padding: 3px; background: #edf2ef; border-radius: 5px; }
    .chart-switch button { border: 0; border-radius: 3px; padding: 7px 10px; background: transparent; color: #34544a; font: inherit; cursor: pointer; }
    .chart-switch button[aria-pressed="true"] { background: #17624f; color: white; }
    .chart-wrap { width: 100%; height: 300px; }
    .chart-wrap canvas { display: block; width: 100%; height: 100%; }
    .chart-legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; color: #52645c; font-size: 13px; }
    .chart-legend span { display: inline-flex; align-items: center; gap: 6px; }
    .chart-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; }
    @media (max-width: 600px) {
      header { padding: 14px 16px; }
      nav form { margin-left: 0; }
      main { margin-top: 20px; padding: 0 14px 28px; }
      h1 { font-size: 24px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <img src="{{ url_for('static', filename='cinnex_logo.svg') }}" alt="Cinnex">
      <span>Business workspace</span>
    </div>
    <nav>
      <a href="{{ url_for('business.dashboard') }}">Overview</a>
            {% if role == 'admin' %}<a href="{{ url_for('business.admin_dashboard') }}">Admin</a>{% endif %}
      <a href="{{ url_for('business.bookings') }}">Room Booker</a>
      <a href="{{ url_for('business.policies') }}">Policies</a>
    {% if role in ('admin', 'manager') %}
    <a href="{{ url_for('business.orders') }}">Orders</a>
    <a href="{{ url_for('business.invoices') }}">Invoices</a>
    {% endif %}
    {% if role == 'admin' %}
      <a href="{{ url_for('business.users') }}">Users</a>
      {% endif %}
      <form method="POST" action="{{ url_for('logout') }}"><button type="submit">Sign out</button></form>
    </nav>
  </header>
  <main>
    <h1>{{ title }}</h1>
    {{ content|safe }}
  </main>
</body>
</html>
'''


def db_connection():
    connection = current_app.config["DB_CONNECT"]()
    cursor = connection.cursor()
    try:
        cursor.execute("""CREATE TABLE IF NOT EXISTS rooms (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            capacity SMALLINT UNSIGNED NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS room_bookings (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            room_id BIGINT UNSIGNED NOT NULL,
            booked_by BIGINT UNSIGNED NOT NULL,
            title VARCHAR(160) NOT NULL,
            starts_at DATETIME NOT NULL,
            ends_at DATETIME NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'booked',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_bookings_room_time (room_id, starts_at, ends_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS business_policies (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(160) NOT NULL,
            body TEXT NOT NULL,
            updated_by BIGINT UNSIGNED NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS business_orders (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(160) NOT NULL,
            description TEXT NOT NULL,
            total DECIMAL(10,2) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            created_by BIGINT UNSIGNED NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS invoices (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
            order_id BIGINT UNSIGNED NOT NULL UNIQUE,
            invoice_number VARCHAR(40) NOT NULL UNIQUE,
            amount DECIMAL(10,2) NOT NULL,
            due_date DATE NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'unpaid',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        cursor.execute("SELECT COUNT(*) FROM rooms")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT INTO rooms (name, capacity) VALUES (%s, %s)",
                [("Meeting Room A", 6), ("Meeting Room B", 8), ("Conference Room", 16)],
            )
        connection.commit()
    finally:
        cursor.close()
    return connection


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        connection = None
        cursor = None
        try:
            connection = db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT role, is_active FROM users WHERE id = %s", (session["user_id"],))
            user = cursor.fetchone()
            if not user or not user["is_active"]:
                session.clear()
                return redirect(url_for("login_page"))
            session["role"] = user["role"]
        except Exception:
            abort(503)
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    return roles_required("admin")(view)


def roles_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in allowed_roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def render_page(title, content_template, **values):
    content = render_template_string(content_template, **values)
    return render_template_string(SHELL, title=title, content=content, role=session.get("role", "staff"))


def close_db(connection, cursor):
    if cursor:
        cursor.close()
    if connection and connection.is_connected():
        connection.close()


@portal.route("/admin")
@admin_required
def admin_dashboard():
        connection = db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
                cursor.execute("""SELECT COUNT(*) AS total_users,
                                                    COALESCE(SUM(is_active = TRUE), 0) AS active_users
                                                    FROM users""")
                user_counts = cursor.fetchone()
                cursor.execute("SELECT role, COUNT(*) AS total FROM users GROUP BY role ORDER BY role")
                role_counts = cursor.fetchall()
                cursor.execute("SELECT COUNT(*) AS total FROM rooms WHERE is_active = TRUE")
                active_rooms = cursor.fetchone()["total"]
                cursor.execute("SELECT COUNT(*) AS total FROM room_bookings WHERE status = 'booked' AND ends_at >= NOW()")
                upcoming_bookings = cursor.fetchone()["total"]
                cursor.execute("SELECT COUNT(*) AS total FROM business_orders WHERE status = 'open'")
                open_orders = cursor.fetchone()["total"]
                cursor.execute("SELECT COUNT(*) AS total FROM invoices WHERE status = 'unpaid'")
                unpaid_invoices = cursor.fetchone()["total"]
                cursor.execute("SELECT id, username, role, is_active, created_at FROM users ORDER BY created_at DESC LIMIT 8")
                recent_users = cursor.fetchall()
        finally:
                close_db(connection, cursor)

        return render_page("Admin Dashboard", '''
            <div class="grid">
                <div class="stat"><strong>{{ total_users }}</strong><span>Registered users</span></div>
                <div class="stat"><strong>{{ active_users }}</strong><span>Active accounts</span></div>
                <div class="stat"><strong>{{ active_rooms }}</strong><span>Active rooms</span></div>
                <div class="stat"><strong>{{ upcoming_bookings }}</strong><span>Upcoming bookings</span></div>
                <div class="stat"><strong>{{ open_orders }}</strong><span>Open orders</span></div>
                <div class="stat"><strong>{{ unpaid_invoices }}</strong><span>Unpaid invoices</span></div>
            </div>
            <section class="panel"><h2>Administration</h2><div class="actions">
                <a href="{{ url_for('business.users') }}">Manage users</a>
                <a href="{{ url_for('business.policies') }}">Manage policies</a>
                <a href="{{ url_for('business.orders') }}">Manage orders</a>
                <a href="{{ url_for('business.invoices') }}">Manage invoices</a>
            </div></section>
            <section class="panel"><h2>Accounts by role</h2><table><thead><tr><th>Role</th><th>Users</th></tr></thead><tbody>
                {% for row in role_counts %}<tr><td>{{ row.role|capitalize }}</td><td>{{ row.total }}</td></tr>{% else %}<tr><td colspan="2">No users.</td></tr>{% endfor %}
            </tbody></table></section>
            <section class="panel"><h2>Recently added users</h2><table><thead><tr><th>Username</th><th>Role</th><th>Account status</th><th>Joined</th></tr></thead><tbody>
                {% for row in recent_users %}<tr><td>{{ row.username }}</td><td>{{ row.role|capitalize }}</td><td>{{ 'Active' if row.is_active else 'Disabled' }}</td><td>{{ row.created_at }}</td></tr>{% else %}<tr><td colspan="4">No users yet.</td></tr>{% endfor %}
            </tbody></table></section>
        ''', total_users=user_counts["total_users"], active_users=user_counts["active_users"],
             active_rooms=active_rooms, upcoming_bookings=upcoming_bookings, open_orders=open_orders,
             unpaid_invoices=unpaid_invoices, role_counts=role_counts, recent_users=recent_users)


@portal.route("/")
@login_required
def dashboard():
    connection = db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM room_bookings WHERE status = 'booked' AND ends_at >= NOW()")
        bookings = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM business_orders WHERE status = 'open'")
        orders = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM invoices WHERE status = 'unpaid'")
        invoices = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM business_policies WHERE is_active = TRUE")
        policies = cursor.fetchone()[0]
    finally:
        close_db(connection, cursor)
    return render_page("Overview", '''
      <div class="grid">
        <div class="stat"><strong>{{ bookings }}</strong><span>Upcoming room bookings</span></div>
        {% if role in ('admin', 'manager') %}
        <div class="stat"><strong>{{ orders }}</strong><span>Open orders</span></div>
        <div class="stat"><strong>{{ invoices }}</strong><span>Unpaid invoices</span></div>
        {% endif %}
        <div class="stat"><strong>{{ policies }}</strong><span>Active policies</span></div>
      </div>
      <section class="panel"><h2>Business workspace</h2>
        <p>Welcome, {{ username }}. Use the navigation to manage bookings, company policies, and business records.</p>
        <div class="actions"><a href="{{ url_for('business.bookings') }}">Book a room</a><a href="{{ url_for('business.policies') }}">View policies</a></div>
      </section>
    ''', bookings=bookings, orders=orders, invoices=invoices, policies=policies,
       username=session.get("username"), role=session.get("role"))


@portal.route("/bookings", methods=["GET", "POST"])
@login_required
def bookings():
    error = None
    connection = db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if request.method == "POST":
            try:
                room_id = int(request.form.get("room_id", ""))
                title = request.form.get("title", "").strip()
                starts_at = datetime.strptime(request.form.get("starts_at", ""), "%Y-%m-%dT%H:%M")
                ends_at = datetime.strptime(request.form.get("ends_at", ""), "%Y-%m-%dT%H:%M")
                if not title or len(title) > 160 or starts_at >= ends_at or starts_at < datetime.now():
                    raise ValueError
                cursor.execute(
                    """SELECT COUNT(*) AS total FROM room_bookings
                       WHERE room_id = %s AND status = 'booked'
                       AND starts_at < %s AND ends_at > %s""",
                    (room_id, ends_at, starts_at),
                )
                if cursor.fetchone()["total"]:
                    error = "That room is already booked for part of this time."
                else:
                    cursor.execute(
                        """INSERT INTO room_bookings (room_id, booked_by, title, starts_at, ends_at)
                           SELECT id, %s, %s, %s, %s FROM rooms WHERE id = %s AND is_active = TRUE""",
                        (session["user_id"], title, starts_at, ends_at, room_id),
                    )
                    if cursor.rowcount:
                        connection.commit()
                        return redirect(url_for("business.bookings"))
                    error = "Select an active room."
            except (TypeError, ValueError):
                error = "Enter a title and a valid future start and end time."
        cursor.execute("SELECT id, name, capacity FROM rooms WHERE is_active = TRUE ORDER BY name")
        rooms = cursor.fetchall()
        cursor.execute("""SELECT b.id, b.title, b.starts_at, b.ends_at, b.status,
                          r.name AS room_name, u.username
                          FROM room_bookings b JOIN rooms r ON r.id = b.room_id
                          JOIN users u ON u.id = b.booked_by
                          WHERE b.status = 'booked' AND b.ends_at >= NOW()
                          ORDER BY b.starts_at LIMIT 100""")
        rows = cursor.fetchall()
    finally:
        close_db(connection, cursor)
    return render_page("Room Booker", '''
      {% if error %}<div class="message error">{{ error }}</div>{% endif %}
      <section class="panel"><h2>Reserve a room</h2>
        <form class="fields" method="POST">
          <label>Room<select name="room_id" required>{% for room in rooms %}<option value="{{ room.id }}">{{ room.name }} ({{ room.capacity }} seats)</option>{% endfor %}</select></label>
          <label>Meeting title<input name="title" maxlength="160" required></label>
          <label>Starts<input type="datetime-local" name="starts_at" required></label>
          <label>Ends<input type="datetime-local" name="ends_at" required></label>
          <button class="primary" type="submit">Book room</button>
        </form>
      </section>
      <section class="panel"><h2>Upcoming bookings</h2><table><thead><tr><th>Room</th><th>Meeting</th><th>Booked by</th><th>Starts</th><th>Ends</th></tr></thead><tbody>
      {% for row in rows %}<tr><td>{{ row.room_name }}</td><td>{{ row.title }}</td><td>{{ row.username }}</td><td>{{ row.starts_at }}</td><td>{{ row.ends_at }}</td></tr>{% else %}<tr><td colspan="5">No upcoming bookings.</td></tr>{% endfor %}
      </tbody></table></section>
    ''', rooms=rooms, rows=rows, error=error)


@portal.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    error = None
    connection = db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if request.method == "POST":
            try:
                target_id = int(request.form.get("user_id", ""))
                role = request.form.get("role", "")
                is_active = request.form.get("is_active") == "1"
                if role not in current_app.config["AUTH_ROLES"]:
                    raise ValueError
                if target_id == session["user_id"] and (role != "admin" or not is_active):
                    error = "You cannot remove your own administrator access."
                else:
                    cursor.execute("UPDATE users SET role = %s, is_active = %s WHERE id = %s", (role, is_active, target_id))
                    connection.commit()
            except (TypeError, ValueError):
                error = "Invalid user update."
        cursor.execute("SELECT id, username, email, phone_number, role, is_active, created_at FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
    finally:
        close_db(connection, cursor)
    return render_page("User Management", '''
      {% if error %}<div class="message error">{{ error }}</div>{% endif %}
      <section class="panel"><table><thead><tr><th>User</th><th>Email</th><th>Mobile</th><th>Access</th><th>Status</th><th>Save</th></tr></thead><tbody>
            {% for row in rows %}<tr><td>{{ row.username }}</td><td>{{ row.email or 'Not set' }}</td><td>{{ row.phone_number or 'Not set' }}</td><td>
                <form method="POST"><input type="hidden" name="user_id" value="{{ row.id }}"><select name="role">{% for choice in role_choices %}<option value="{{ choice }}" {% if row.role == choice %}selected{% endif %}>{{ choice|capitalize }}</option>{% endfor %}</select><label><input type="checkbox" name="is_active" value="1" {% if row.is_active %}checked{% endif %}> Active</label><button class="primary" type="submit">Save</button></form></td></tr>
      {% endfor %}</tbody></table></section>
    ''', rows=rows, error=error, role_choices=current_app.config["AUTH_ROLES"])


@portal.route("/policies", methods=["GET", "POST"])
@login_required
def policies():
    error = None
    connection = db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if request.method == "POST":
            if session.get("role") not in {"admin", "manager"}:
                abort(403)
            title = request.form.get("title", "").strip()
            body = request.form.get("body", "").strip()
            if not title or not body or len(title) > 160:
                error = "Enter a policy title and details."
            else:
                cursor.execute(
                    "INSERT INTO business_policies (title, body, updated_by) VALUES (%s, %s, %s)",
                    (title, body, session["user_id"]),
                )
                connection.commit()
                return redirect(url_for("business.policies"))
        cursor.execute("""SELECT p.title, p.body, p.updated_at, u.username
                          FROM business_policies p JOIN users u ON u.id = p.updated_by
                          WHERE p.is_active = TRUE ORDER BY p.updated_at DESC""")
        rows = cursor.fetchall()
    finally:
        close_db(connection, cursor)
    return render_page("Company Policies", '''
      {% if error %}<div class="message error">{{ error }}</div>{% endif %}
    {% if role in ('admin', 'manager') %}<section class="panel"><h2>Publish a policy</h2><form class="fields" method="POST"><label>Title<input name="title" maxlength="160" required></label><label style="grid-column:1/-1">Policy<textarea name="body" required></textarea></label><button class="primary" type="submit">Publish</button></form></section>{% endif %}
      {% for row in rows %}<article class="panel"><h2>{{ row.title }}</h2><p>{{ row.body }}</p><p class="muted">Updated {{ row.updated_at }} by {{ row.username }}</p></article>{% else %}<section class="panel"><p>No policies have been published.</p></section>{% endfor %}
    ''', rows=rows, error=error, role=session.get("role"))


@portal.route("/orders", methods=["GET", "POST"])
@roles_required("admin", "manager")
def orders():
    error = None
    connection = db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if request.method == "POST":
            customer = request.form.get("customer_name", "").strip()
            description = request.form.get("description", "").strip()
            try:
                amount = Decimal(request.form.get("total", ""))
                if amount <= 0 or amount > Decimal("99999999.99"):
                    raise InvalidOperation
                if not customer or not description:
                    error = "Enter a customer and order description."
                else:
                    cursor.execute(
                        "INSERT INTO business_orders (customer_name, description, total, created_by) VALUES (%s, %s, %s, %s)",
                        (customer, description, amount, session["user_id"]),
                    )
                    connection.commit()
                    return redirect(url_for("business.orders"))
            except (InvalidOperation, ValueError):
                error = "Enter a valid positive order amount."
        cursor.execute("""SELECT o.id, o.customer_name, o.description, o.total, o.status, o.created_at,
                          i.invoice_number FROM business_orders o LEFT JOIN invoices i ON i.order_id = o.id
                          ORDER BY o.created_at DESC LIMIT 100""")
        rows = cursor.fetchall()
    finally:
        close_db(connection, cursor)
    return render_page("Orders", '''
      {% if error %}<div class="message error">{{ error }}</div>{% endif %}
      <section class="panel"><h2>Create order</h2><form class="fields" method="POST"><label>Customer<input name="customer_name" maxlength="160" required></label><label>Description<input name="description" required></label><label>Total<input name="total" type="number" min="0.01" step="0.01" required></label><button class="primary" type="submit">Create order</button></form></section>
      <section class="panel"><table><thead><tr><th>Order</th><th>Customer</th><th>Description</th><th>Total</th><th>Status</th><th>Invoice</th></tr></thead><tbody>{% for row in rows %}<tr><td>#{{ row.id }}</td><td>{{ row.customer_name }}</td><td>{{ row.description }}</td><td>{{ row.total }}</td><td>{{ row.status }}</td><td>{{ row.invoice_number or 'Not invoiced' }}</td></tr>{% else %}<tr><td colspan="6">No orders yet.</td></tr>{% endfor %}</tbody></table></section>
    ''', rows=rows, error=error)


@portal.route("/invoices", methods=["GET", "POST"])
@roles_required("admin", "manager")
def invoices():
    error = None
    connection = db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if request.method == "POST":
            try:
                order_id = int(request.form.get("order_id", ""))
                due_date = datetime.strptime(request.form.get("due_date", ""), "%Y-%m-%d").date()
                cursor.execute("SELECT id, total FROM business_orders WHERE id = %s", (order_id,))
                order = cursor.fetchone()
                if not order:
                    error = "Select a valid order."
                else:
                    invoice_number = f"CIN-{datetime.now():%Y%m%d}-{secrets.token_hex(3).upper()}"
                    cursor.execute(
                        "INSERT INTO invoices (order_id, invoice_number, amount, due_date) VALUES (%s, %s, %s, %s)",
                        (order_id, invoice_number, order["total"], due_date),
                    )
                    connection.commit()
                    return redirect(url_for("business.invoices"))
            except (TypeError, ValueError, MySQLError):
                error = "Choose an order without an invoice and a valid due date."
        cursor.execute("SELECT id, customer_name FROM business_orders WHERE id NOT IN (SELECT order_id FROM invoices) ORDER BY created_at DESC")
        available_orders = cursor.fetchall()
        cursor.execute("""SELECT i.id, i.invoice_number, i.amount, i.due_date, i.status,
                          o.customer_name, o.description FROM invoices i
                          JOIN business_orders o ON o.id = i.order_id ORDER BY i.created_at DESC LIMIT 100""")
        rows = cursor.fetchall()
    finally:
        close_db(connection, cursor)
    return render_page("Invoices", '''
      {% if error %}<div class="message error">{{ error }}</div>{% endif %}
      <section class="panel"><h2>Issue invoice</h2><form class="fields" method="POST"><label>Order<select name="order_id" required>{% for order in available_orders %}<option value="{{ order.id }}">#{{ order.id }} · {{ order.customer_name }}</option>{% endfor %}</select></label><label>Due date<input name="due_date" type="date" required></label><button class="primary" type="submit">Create invoice</button></form></section>
            <section class="panel"><table><thead><tr><th>Invoice</th><th>Customer</th><th>Order details</th><th>Amount</th><th>Due</th><th>Status</th><th>Print</th></tr></thead><tbody>{% for row in rows %}<tr><td>{{ row.invoice_number }}</td><td>{{ row.customer_name }}</td><td>{{ row.description }}</td><td>{{ row.amount }}</td><td>{{ row.due_date }}</td><td>{{ row.status }}</td><td><a href="{{ url_for('business.print_invoice', invoice_id=row.id) }}">Print</a></td></tr>{% else %}<tr><td colspan="7">No invoices yet.</td></tr>{% endfor %}</tbody></table></section>
    ''', available_orders=available_orders, rows=rows, error=error)


@portal.route("/invoices/<int:invoice_id>/print")
@roles_required("admin", "manager")
def print_invoice(invoice_id):
        connection = db_connection()
        cursor = connection.cursor(dictionary=True)
        try:
                cursor.execute("""SELECT i.invoice_number, i.amount, i.due_date, i.status, i.created_at,
                                                    o.customer_name, o.description
                                                    FROM invoices i JOIN business_orders o ON o.id = i.order_id
                                                    WHERE i.id = %s""", (invoice_id,))
                invoice = cursor.fetchone()
        finally:
                close_db(connection, cursor)
        if not invoice:
                abort(404)

        return render_template_string('''
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>{{ invoice.invoice_number }} | Cinnex</title>
            <style>
                * { box-sizing: border-box; }
                body { margin: 0; padding: 24px; background: #edf1ef; color: #111; font: 14px/1.4 Arial, sans-serif; }
                .toolbar { display: flex; justify-content: center; align-items: center; gap: 12px; margin-bottom: 18px; }
                .toolbar label { display: flex; align-items: center; gap: 7px; }
                .toolbar select, .toolbar button { padding: 8px 10px; font: inherit; }
                .toolbar button { border: 0; background: #17624f; color: white; border-radius: 4px; cursor: pointer; }
                .receipt { --paper-width: 72mm; width: var(--paper-width); margin: 0 auto; padding: 5mm; background: white; }
                .receipt.paper-58 { --paper-width: 52mm; }
                .receipt.paper-80 { --paper-width: 72mm; }
                header { text-align: center; border-bottom: 1px dashed #111; padding-bottom: 10px; }
                header img { width: 42mm; max-width: 100%; height: auto; }
                h1 { font-size: 16px; margin: 8px 0 2px; }
                .status { margin: 8px 0; font-size: 12px; font-weight: bold; text-align: center; text-transform: uppercase; }
                .line { display: flex; justify-content: space-between; gap: 8px; margin: 6px 0; }
                .description { overflow-wrap: anywhere; margin: 10px 0; }
                .total { border-top: 1px dashed #111; margin-top: 10px; padding-top: 9px; font-size: 16px; font-weight: bold; }
                .footer { border-top: 1px dashed #111; margin-top: 12px; padding-top: 9px; text-align: center; font-size: 11px; }
                @page { margin: 3mm; }
                @media print {
                    body { padding: 0; background: white; }
                    .toolbar { display: none; }
                    .receipt { margin: 0; width: var(--paper-width); padding: 0; }
                }
            </style>
        </head>
        <body>
            <div class="toolbar">
                <label>Paper width
                    <select id="paper-size" aria-label="Thermal paper width">
                        <option value="80">80 mm</option>
                        <option value="58">58 mm</option>
                    </select>
                </label>
                <button type="button" onclick="window.print()">Print</button>
            </div>
            <main class="receipt paper-80" id="receipt">
                <header>
                    <img src="{{ url_for('static', filename='cinnex_logo.svg') }}" alt="Cinnex">
                    <h1>{% if invoice.status == 'paid' %}PAYMENT RECEIPT{% else %}INVOICE{% endif %}</h1>
                    <div>{{ invoice.invoice_number }}</div>
                </header>
                <div class="status">{{ invoice.status }}{% if invoice.status != 'paid' %} · NOT A PAYMENT RECEIPT{% endif %}</div>
                <div class="line"><span>Issued</span><span>{{ invoice.created_at }}</span></div>
                <div class="line"><span>Due</span><span>{{ invoice.due_date }}</span></div>
                <div class="description"><strong>Customer</strong><br>{{ invoice.customer_name }}</div>
                <div class="description"><strong>Order</strong><br>{{ invoice.description }}</div>
                <div class="line total"><span>Total</span><span>${{ '%.2f'|format(invoice.amount) }}</span></div>
                <div class="footer">Thank you for your business.<br>Cinnex for Business</div>
            </main>
            <script>
                const paperSize = document.querySelector('#paper-size');
                const receipt = document.querySelector('#receipt');
                paperSize.addEventListener('change', () => {
                    receipt.classList.toggle('paper-58', paperSize.value === '58');
                    receipt.classList.toggle('paper-80', paperSize.value === '80');
                });
            </script>
        </body>
        </html>
        ''', invoice=invoice)


@portal.route("/preview")
def dashboard_preview():
        try:
                if not ip_address(request.remote_addr).is_loopback:
                        abort(404)
        except ValueError:
                abort(404)

        content = render_template_string('''
            <div class="message">Admin demo preview · Sample data only · No login or database changes</div>
            <div class="grid">
                <div class="stat"><strong>3</strong><span>Hotel properties</span></div>
                <div class="stat"><strong>84%</strong><span>Average occupancy</span></div>
                <div class="stat"><strong>$246k</strong><span>June revenue</span></div>
                <div class="stat"><strong>24</strong><span>Active team members</span></div>
                <div class="stat"><strong>6</strong><span>Upcoming room bookings</span></div>
                <div class="stat"><strong>12</strong><span>Open orders</span></div>
                <div class="stat"><strong>$2,480</strong><span>Unpaid invoices</span></div>
                <div class="stat"><strong>8</strong><span>Active policies</span></div>
            </div>
            <section class="panel">
                <div class="chart-heading">
                    <div><h2>Hotel performance</h2><div class="muted">Sample data · January–June 2026</div></div>
                    <div class="chart-switch" role="group" aria-label="Hotel metric">
                        <button type="button" data-metric="occupancy" aria-pressed="true">Occupancy</button>
                        <button type="button" data-metric="revenue" aria-pressed="false">Revenue</button>
                    </div>
                </div>
                <div class="chart-wrap"><canvas id="hotel-performance-chart" role="img" aria-label="Sample occupancy trends for three Cinnex hotels"></canvas></div>
                <div class="chart-legend">
                    <span><i style="background:#17624f"></i>Cinnex City</span>
                    <span><i style="background:#cc6b43"></i>Cinnex Coast</span>
                    <span><i style="background:#3a6e9e"></i>Cinnex Airport</span>
                </div>
                <table><thead><tr><th>Property</th><th>June occupancy</th><th>June revenue</th></tr></thead><tbody>
                    <tr><td>Cinnex City</td><td>83%</td><td>$87k</td></tr>
                    <tr><td>Cinnex Coast</td><td>84%</td><td>$79k</td></tr>
                    <tr><td>Cinnex Airport</td><td>86%</td><td>$80k</td></tr>
                </tbody></table>
            </section>
            <section class="panel"><h2>Property and team overview</h2>
                <table><thead><tr><th>Property</th><th>Location</th><th>Rooms</th><th>Team</th><th>Operating status</th></tr></thead><tbody>
                    <tr><td>Cinnex City</td><td>New York</td><td>82</td><td>11</td><td>Open</td></tr>
                    <tr><td>Cinnex Coast</td><td>Monterey</td><td>64</td><td>8</td><td>Open</td></tr>
                    <tr><td>Cinnex Airport</td><td>Denver</td><td>96</td><td>5</td><td>Open</td></tr>
                </tbody></table>
            </section>
            <script>
                (() => {
                    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
                    const hotels = [
                        { name: 'Cinnex City', color: '#17624f', occupancy: [65, 68, 72, 76, 80, 83], revenue: [62, 65, 71, 78, 82, 87] },
                        { name: 'Cinnex Coast', color: '#cc6b43', occupancy: [58, 64, 70, 74, 79, 84], revenue: [48, 51, 57, 66, 73, 79] },
                        { name: 'Cinnex Airport', color: '#3a6e9e', occupancy: [72, 70, 75, 78, 82, 86], revenue: [54, 56, 60, 69, 74, 80] }
                    ];
                    const chart = document.querySelector('#hotel-performance-chart');
                    const drawingContext = chart.getContext('2d');
                    let selectedMetric = 'occupancy';

                    function drawChart() {
                        const bounds = chart.getBoundingClientRect();
                        if (!bounds.width) return;
                        const pixelRatio = window.devicePixelRatio || 1;
                        chart.width = Math.round(bounds.width * pixelRatio);
                        chart.height = Math.round(bounds.height * pixelRatio);
                        drawingContext.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
                        drawingContext.clearRect(0, 0, bounds.width, bounds.height);

                        const plot = { left: 46, right: bounds.width - 14, top: 18, bottom: bounds.height - 38 };
                        const maxValue = selectedMetric === 'occupancy' ? 100 : 100;
                        const ticks = selectedMetric === 'occupancy' ? [0, 25, 50, 75, 100] : [0, 25, 50, 75, 100];
                        drawingContext.font = '12px Arial';
                        drawingContext.textAlign = 'right';
                        drawingContext.textBaseline = 'middle';
                        ticks.forEach((tick) => {
                            const y = plot.bottom - tick / maxValue * (plot.bottom - plot.top);
                            drawingContext.strokeStyle = '#e5ebe7';
                            drawingContext.beginPath();
                            drawingContext.moveTo(plot.left, y);
                            drawingContext.lineTo(plot.right, y);
                            drawingContext.stroke();
                            drawingContext.fillStyle = '#61716a';
                            drawingContext.fillText(selectedMetric === 'occupancy' ? `${tick}%` : `$${tick}k`, plot.left - 8, y);
                        });

                        months.forEach((month, index) => {
                            const x = plot.left + index / (months.length - 1) * (plot.right - plot.left);
                            drawingContext.fillStyle = '#61716a';
                            drawingContext.textAlign = 'center';
                            drawingContext.textBaseline = 'top';
                            drawingContext.fillText(month, x, plot.bottom + 10);
                        });

                        hotels.forEach((hotel) => {
                            const values = hotel[selectedMetric];
                            drawingContext.strokeStyle = hotel.color;
                            drawingContext.lineWidth = 2.5;
                            drawingContext.beginPath();
                            values.forEach((value, index) => {
                                const x = plot.left + index / (values.length - 1) * (plot.right - plot.left);
                                const y = plot.bottom - value / maxValue * (plot.bottom - plot.top);
                                if (index === 0) drawingContext.moveTo(x, y);
                                else drawingContext.lineTo(x, y);
                            });
                            drawingContext.stroke();
                            values.forEach((value, index) => {
                                const x = plot.left + index / (values.length - 1) * (plot.right - plot.left);
                                const y = plot.bottom - value / maxValue * (plot.bottom - plot.top);
                                drawingContext.fillStyle = hotel.color;
                                drawingContext.beginPath();
                                drawingContext.arc(x, y, 3.5, 0, Math.PI * 2);
                                drawingContext.fill();
                            });
                        });
                    }

                    document.querySelectorAll('[data-metric]').forEach((button) => {
                        button.addEventListener('click', () => {
                            selectedMetric = button.dataset.metric;
                            document.querySelectorAll('[data-metric]').forEach((option) => {
                                option.setAttribute('aria-pressed', String(option === button));
                            });
                            chart.setAttribute('aria-label', `Sample ${selectedMetric} trends for three Cinnex hotels`);
                            drawChart();
                        });
                    });
                    window.addEventListener('resize', drawChart);
                    drawChart();
                })();
            </script>
            <section class="panel"><h2>Today's room schedule</h2>
                <table><thead><tr><th>Time</th><th>Room</th><th>Meeting</th><th>Booked by</th></tr></thead><tbody>
                <tr><td>09:00</td><td>Meeting Room A</td><td>Weekly planning</td><td>Jamie Morgan</td></tr>
                <tr><td>11:30</td><td>Conference Room</td><td>Client introduction</td><td>Alex Rivera</td></tr>
                <tr><td>14:00</td><td>Meeting Room B</td><td>Project review</td><td>Sam Taylor</td></tr>
                </tbody></table>
            </section>
            <section class="panel"><h2>Recent business activity</h2>
                <table><thead><tr><th>Record</th><th>Customer</th><th>Status</th><th>Amount</th></tr></thead><tbody>
                <tr><td>Order #1048</td><td>Northstar Studio</td><td>Open</td><td>$840.00</td></tr>
                <tr><td>Invoice CIN-1043</td><td>Harbor Works</td><td>Due in 7 days</td><td>$1,250.00</td></tr>
                <tr><td>Order #1042</td><td>Greenfield Group</td><td>In progress</td><td>$390.00</td></tr>
                </tbody></table>
            </section>
            <section class="panel"><h2>Hotel tools</h2><div class="actions"><a href="{{ url_for('business.stay_marketplace_demo') }}">Open stay marketplace demo</a><a href="{{ url_for('business.pos_preview') }}">Open hotel POS demo</a><a href="{{ url_for('business.preview_receipt') }}">Print sample receipt</a></div></section>
        ''')
        return render_template_string(SHELL, title="Admin Dashboard", content=content, role="admin")


@portal.route("/stay/demo")
def stay_marketplace_demo():
        try:
                if not ip_address(request.remote_addr).is_loopback:
                        abort(404)
        except ValueError:
                abort(404)

        return render_template_string('''
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Find a Stay | Cinnex</title>
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
            <style>
                * { box-sizing: border-box; }
                body { margin: 0; background: #f5f7f6; color: #1a2925; font: 15px/1.5 Arial, sans-serif; }
                .topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 13px max(18px, calc((100vw - 1160px) / 2)); background: #173b34; color: white; }
                .topbar img { width: 134px; height: auto; }
                .topbar a { color: white; }
                .demo-tag { padding: 5px 9px; border-radius: 4px; background: #f3c969; color: #3a2b0e; font-size: 12px; font-weight: 700; }
                main { max-width: 1160px; margin: 22px auto; padding: 0 18px 40px; }
                .intro { display: flex; align-items: end; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-bottom: 17px; }
                h1 { margin: 0; font-size: 27px; }
                h2 { margin: 0; font-size: 19px; }
                .muted { color: #63736d; }
                .search-bar { display: grid; grid-template-columns: 1.5fr 1fr 1fr .7fr auto; gap: 10px; align-items: end; padding: 15px; background: white; border: 1px solid #dce5e0; border-radius: 6px; }
                label { display: grid; gap: 5px; color: #465951; font-size: 13px; font-weight: 600; }
                input, select, button { min-width: 0; border: 1px solid #c5d1cb; border-radius: 4px; padding: 10px; background: white; color: #1a2925; font: inherit; }
                button { cursor: pointer; }
                .primary { border-color: #17624f; background: #17624f; color: white; font-weight: 700; }
                .notice { margin: 14px 0; padding: 10px 12px; border-radius: 4px; background: #e5f1eb; color: #245640; }
                .results-layout { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(300px, .85fr); gap: 16px; align-items: start; margin-top: 16px; }
                .hotel-list { display: grid; gap: 11px; }
                .hotel { display: grid; grid-template-columns: 145px minmax(0, 1fr) auto; gap: 14px; align-items: center; padding: 13px; background: white; border: 1px solid #dce5e0; border-radius: 6px; }
                .hotel-image { width: 145px; height: 112px; border-radius: 4px; object-fit: cover; background: #d8e4de; }
                .hotel h2 { margin-bottom: 3px; }
                .hotel-meta { color: #596b63; font-size: 13px; }
                .hotel-price { text-align: right; white-space: nowrap; }
                .hotel-price strong { display: block; color: #17624f; font-size: 20px; }
                .map-panel { margin-bottom: 12px; overflow: hidden; border: 1px solid #dce5e0; border-radius: 5px; background: #e7eeea; }
                #hotel-map { width: 100%; height: 320px; background: #e7eeea; }
                #map-status { padding: 8px 11px; color: #63736d; font-size: 12px; }
                .map-hotel-popup { min-width: 165px; }
                .map-hotel-popup button { margin-top: 7px; border: 0; border-radius: 3px; padding: 6px 9px; background: #17624f; color: white; cursor: pointer; }
                .booking-card, .confirmation { padding: 16px; background: white; border: 1px solid #dce5e0; border-radius: 6px; }
                .booking-card { position: sticky; top: 12px; }
                .booking-card form { display: grid; gap: 10px; margin-top: 12px; }
                .terms { padding: 12px; border: 1px solid #dce5e0; background: #f7faf8; }
                .terms strong { display: block; font-size: 19px; }
                .confirmation { display: none; margin-top: 12px; }
                .confirmation.visible { display: block; }
                .confirm-status { padding: 8px; margin: 10px 0; background: #fff4d8; color: #664b00; font-weight: 700; }
                .confirm-status.confirmed { background: #e5f1eb; color: #245640; }
                .receipt-row { display: flex; justify-content: space-between; gap: 10px; margin: 6px 0; }
                .proposal { display: none; margin-top: 10px; padding: 11px; border: 1px solid #e6c978; background: #fff8e6; }
                .proposal.visible { display: block; }
                .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
                .small-button { padding: 8px 10px; }
                [hidden] { display: none !important; }
                .demo-foot { margin-top: 20px; color: #64736d; font-size: 12px; }
                @media (max-width: 850px) { .search-bar { grid-template-columns: repeat(2, minmax(0, 1fr)); } .results-layout { grid-template-columns: 1fr; } .booking-card { position: static; } }
                @media (max-width: 560px) { .topbar { padding: 11px 13px; } .topbar img { width: 108px; } main { padding: 0 11px 28px; } h1 { font-size: 22px; } .search-bar { grid-template-columns: 1fr 1fr; padding: 11px; } .hotel { grid-template-columns: 94px minmax(0, 1fr); gap: 10px; } .hotel-image { width: 94px; height: 95px; grid-row: span 2; } .hotel-price { grid-column: 2; text-align: left; } .hotel-price strong { display: inline; margin-right: 4px; } #hotel-map { height: 260px; } }
            </style>
        </head>
        <body>
            <header class="topbar"><img src="{{ url_for('static', filename='cinnex_logo.svg') }}" alt="Cinnex"><div class="actions"><span class="demo-tag">LOCAL DEMO</span><a href="{{ url_for('business.dashboard_preview') }}">Hotel admin preview</a></div></header>
            <main>
                <div class="intro"><div><h1>Find a Cinnex stay</h1><div class="muted">Compare sample hotels and confirm the full stay before booking.</div></div><span class="muted">Demo inventory · Not real hotel availability</span></div>
                <form class="search-bar" id="search-form">
                    <label>Destination<input id="destination" value="New York" placeholder="City or area"></label>
                    <label>Check-in<input id="check-in" type="date" required></label>
                    <label>Check-out<input id="check-out" type="date" required></label>
                    <label>Guests<select id="guests"><option>1</option><option selected>2</option><option>3</option><option>4</option></select></label>
                    <button class="primary" type="submit">Search stays</button>
                </form>
                <div class="notice">Booking safety: the full dates, night count, and total are shown before confirmation. A hotel acknowledgement is required, and any change to a confirmed stay requires customer approval.</div>
                <div class="results-layout">
                    <section><div class="intro"><h2 id="results-heading">Sample stays</h2><span class="muted" id="result-count"></span></div><div class="map-panel"><div id="hotel-map" role="region" aria-label="Map of sample Cinnex hotels"></div><div id="map-status">Sample hotel locations · © OpenStreetMap contributors</div></div><div class="hotel-list" id="hotel-list"></div></section>
                    <aside>
                        <section class="booking-card"><h2>Booking details</h2><p class="muted" id="selection-prompt">Choose a hotel to see the exact dates and total.</p>
                            <div class="terms" id="quote" hidden></div>
                            <p class="notice" id="booking-error" hidden></p>
                            <form id="guest-form" hidden>
                                <label>Guest name<input id="guest-name" required placeholder="Full name"></label>
                                <label>Guest email<input id="guest-email" type="email" required placeholder="name@example.com"></label>
                                <button class="primary" type="submit">Request hotel confirmation</button>
                            </form>
                            <p class="demo-foot">No payment is collected in this demo. Real reservations require verified hotel partners and a payment provider.</p>
                        </section>
                        <section class="confirmation" id="confirmation" aria-live="polite"></section>
                    </aside>
                </div>
                <p class="demo-foot">Sample hotels and prices are fictional. This prototype does not send bookings, store guest details, or connect to real hotel inventory.</p>
            </main>
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
            <script>
                (() => {
                    const hotels = [
                        { id: 'city', name: 'Cinnex City Hotel', city: 'New York', area: 'Midtown · 0.4 km to transit', stars: '4-star sample', rate: 220, feeRate: .12, maxNights: 30, image: 'https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=480&q=80' },
                        { id: 'harbor', name: 'Harborlight Hotel', city: 'New York', area: 'Waterfront · Breakfast option', stars: '4-star sample', rate: 185, feeRate: .12, maxNights: 21, image: 'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=480&q=80' },
                        { id: 'north', name: 'Northwood Lodge', city: 'New York', area: 'Upper West · Family rooms', stars: '3-star sample', rate: 142, feeRate: .12, maxNights: 17, image: 'https://images.unsplash.com/photo-1564501049412-61c2a3083791?auto=format&fit=crop&w=480&q=80' },
                        { id: 'coast', name: 'Cinnex Coast House', city: 'Monterey', area: 'Ocean district · Parking', stars: '4-star sample', rate: 205, feeRate: .12, maxNights: 30, image: 'https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=480&q=80' }
                    ];
                    const hotelCoordinates = {
                        city: [40.7549, -73.9840],
                        harbor: [40.7064, -74.0132],
                        north: [40.7870, -73.9754],
                        coast: [36.6002, -121.8947]
                    };
                    const hotelList = document.querySelector('#hotel-list');
                    const guestForm = document.querySelector('#guest-form');
                    const quote = document.querySelector('#quote');
                    const selectionPrompt = document.querySelector('#selection-prompt');
                    const confirmation = document.querySelector('#confirmation');
                    const mapStatus = document.querySelector('#map-status');
                    let selectedHotel = null;
                    let currentBooking = null;
                    let checkIn = '';
                    let checkOut = '';
                    let guestCount = 2;
                    let hotelMap = null;
                    let hotelMarkers = null;
                    const money = (amount) => `$${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                    const dateLabel = (value) => new Date(`${value}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                    const nightCount = () => Math.round((Date.parse(`${checkOut}T00:00:00Z`) - Date.parse(`${checkIn}T00:00:00Z`)) / 86400000);

                    function renderMap(results) {
                        if (!window.L) {
                            mapStatus.textContent = 'Map unavailable right now; use the sample hotel list below.';
                            return;
                        }
                        if (!hotelMap) {
                            hotelMap = L.map('hotel-map', { scrollWheelZoom: false }).setView(hotelCoordinates.city, 12);
                            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                                maxZoom: 19,
                                attribution: '&copy; OpenStreetMap contributors'
                            }).addTo(hotelMap);
                            hotelMarkers = L.layerGroup().addTo(hotelMap);
                        }
                        hotelMarkers.clearLayers();
                        const bounds = [];
                        results.forEach((hotel) => {
                            const coordinates = hotelCoordinates[hotel.id];
                            if (!coordinates) return;
                            bounds.push(coordinates);
                            const marker = L.marker(coordinates).addTo(hotelMarkers);
                            marker.bindPopup(`<div class="map-hotel-popup"><strong>${hotel.name}</strong><br>${hotel.city}<br>${money(hotel.rate)} / night<br>Sample listing<br><button type="button" data-hotel-id="${hotel.id}">View stay</button></div>`);
                            marker.on('popupopen', (event) => {
                                event.popup.getElement().querySelector('[data-hotel-id]')?.addEventListener('click', () => selectHotel(hotel));
                            });
                        });
                        if (bounds.length > 1) hotelMap.fitBounds(bounds, { padding: [24, 24], maxZoom: 12 });
                        else if (bounds.length === 1) hotelMap.setView(bounds[0], 14);
                        else hotelMap.setView(hotelCoordinates.city, 11);
                        mapStatus.textContent = 'Sample hotel locations · © OpenStreetMap contributors';
                        requestAnimationFrame(() => hotelMap.invalidateSize());
                    }

                    function renderHotels() {
                        const search = document.querySelector('#destination').value.trim().toLowerCase();
                        const results = hotels.filter((hotel) => !search || hotel.city.toLowerCase().includes(search) || hotel.name.toLowerCase().includes(search) || hotel.area.toLowerCase().includes(search));
                        document.querySelector('#result-count').textContent = `${results.length} sample ${results.length === 1 ? 'hotel' : 'hotels'}`;
                        renderMap(results);
                        hotelList.replaceChildren(...results.map((hotel) => {
                            const card = document.createElement('article');
                            card.className = 'hotel';
                            const image = document.createElement('img');
                            image.className = 'hotel-image';
                            image.src = hotel.image;
                            image.alt = `Sample property: ${hotel.name}`;
                            const details = document.createElement('div');
                            const title = document.createElement('h2');
                            title.textContent = hotel.name;
                            const rating = document.createElement('div');
                            rating.className = 'hotel-meta';
                            rating.textContent = `${hotel.stars} · Sample-verified listing · ${hotel.city}`;
                            const area = document.createElement('div');
                            area.className = 'hotel-meta';
                            area.textContent = `${hotel.area} · Max stay ${hotel.maxNights} nights`;
                            details.append(title, rating, area);
                            const price = document.createElement('div');
                            price.className = 'hotel-price';
                            const amount = document.createElement('strong');
                            amount.textContent = money(hotel.rate);
                            const perNight = document.createElement('span');
                            perNight.className = 'muted';
                            perNight.textContent = '/ night';
                            const select = document.createElement('button');
                            select.className = 'small-button';
                            select.type = 'button';
                            select.textContent = 'Select';
                            select.addEventListener('click', () => selectHotel(hotel));
                            price.append(amount, perNight, document.createElement('br'), select);
                            card.append(image, details, price);
                            return card;
                        }));
                    }

                    function selectHotel(hotel) {
                        selectedHotel = hotel;
                        const nights = nightCount();
                        const bookingError = document.querySelector('#booking-error');
                        bookingError.hidden = nights <= hotel.maxNights;
                        bookingError.textContent = nights > hotel.maxNights ? `This sample hotel allows at most ${hotel.maxNights} nights.` : '';
                        const subtotal = hotel.rate * nights;
                        const taxes = Math.round(subtotal * hotel.feeRate * 100) / 100;
                        const total = subtotal + taxes;
                        quote.hidden = false;
                        selectionPrompt.hidden = true;
                        guestForm.hidden = false;
                        quote.innerHTML = `<strong>${hotel.name}</strong><div class="receipt-row"><span>Check-in</span><span>${dateLabel(checkIn)}</span></div><div class="receipt-row"><span>Check-out</span><span>${dateLabel(checkOut)}</span></div><div class="receipt-row"><span>Length of stay</span><strong>${nights} nights</strong></div><div class="receipt-row"><span>Maximum stay</span><span>${hotel.maxNights} nights</span></div><div class="receipt-row"><span>Guests</span><span>${guestCount}</span></div><div class="receipt-row"><span>Room subtotal</span><span>${money(subtotal)}</span></div><div class="receipt-row"><span>Estimated taxes</span><span>${money(taxes)}</span></div><div class="receipt-row"><strong>Total for ${nights} nights</strong><strong>${money(total)}</strong></div>`;
                    }

                    function addBookingAudit(message) {
                        currentBooking.audit.push(`${new Date().toLocaleString()} · ${message}`);
                    }

                    function updateBookingPrice() {
                        currentBooking.nights = Math.round((Date.parse(`${currentBooking.checkOut}T00:00:00Z`) - Date.parse(`${currentBooking.checkIn}T00:00:00Z`)) / 86400000);
                        currentBooking.subtotal = currentBooking.hotel.rate * currentBooking.nights;
                        currentBooking.taxes = Math.round(currentBooking.subtotal * currentBooking.hotel.feeRate * 100) / 100;
                        currentBooking.total = currentBooking.subtotal + currentBooking.taxes;
                    }

                    function showConfirmation() {
                        updateBookingPrice();
                        confirmation.classList.add('visible');
                        const nightWord = currentBooking.nights === 1 ? 'night' : 'nights';
                        const copy = `<div class="receipt-row"><span>Booking ID</span><strong>${currentBooking.id}</strong></div><div class="receipt-row"><span>Hotel</span><span>${currentBooking.hotel.name}</span></div><div class="receipt-row"><span>Guest</span><span>${currentBooking.name}</span></div><div class="receipt-row"><span>Check-in</span><span>${dateLabel(currentBooking.checkIn)}</span></div><div class="receipt-row"><span>Check-out</span><span>${dateLabel(currentBooking.checkOut)}</span></div><div class="receipt-row"><span>Exact stay</span><strong>${currentBooking.nights} ${nightWord}</strong></div><div class="receipt-row"><span>Guests</span><span>${currentBooking.guests}</span></div><div class="receipt-row"><span>Total</span><strong>${money(currentBooking.total)}</strong></div>`;
                        const changePanel = currentBooking.changeRequest
                            ? `<div class="proposal visible"><strong>Hotel change request · ${currentBooking.changeRequest.proposedNights} nights</strong><p>Original: ${currentBooking.nights} ${nightWord} · Current status: ${currentBooking.changeRequest.status}</p>${currentBooking.changeRequest.status === 'Awaiting customer approval' ? '<div class="actions"><button class="primary small-button" type="button" id="approve-change">Approve updated terms</button><button class="small-button" type="button" id="reject-change">Reject · keep original</button></div>' : ''}</div>`
                            : (currentBooking.nights > 4 ? '<div class="actions"><button class="small-button" type="button" id="propose-change">Hotel proposes a 4-night stay</button></div>' : '');
                        confirmation.innerHTML = `<h2>Verified reservation ${currentBooking.id}</h2><div class="confirm-status ${currentBooking.hotelAcknowledged ? 'confirmed' : ''}">${currentBooking.status}</div><div class="grid"><article class="panel"><strong>Customer confirmation</strong>${copy}</article><article class="panel"><strong>Hotel / front-desk copy</strong>${copy}<p class="muted">Hotel acknowledgement: ${currentBooking.hotelAcknowledged ? 'confirmed' : 'pending'}</p></article></div><p class="muted">Demo only · No payment or escrow is collected.</p>${!currentBooking.hotelAcknowledged ? '<button class="primary small-button" type="button" id="hotel-ack">Simulate hotel acknowledgement</button>' : ''}${changePanel}<section class="panel"><h3>Check-in verification (demo QR scan)</h3><p>Compare the hotel-reported nights to this confirmed reservation.</p><label>Hotel-reported nights<input id="hotel-reported-nights" type="number" min="1" value="${currentBooking.nights}"></label><button class="small-button" type="button" id="verify-checkin">Verify check-in</button><div class="confirm-status" id="checkin-result">Not checked in</div></section><section class="panel"><h3>Booking audit trail</h3><ol>${currentBooking.audit.map((entry) => `<li>${entry}</li>`).join('')}</ol></section>`;

                        document.querySelector('#hotel-ack')?.addEventListener('click', () => {
                            currentBooking.hotelAcknowledged = true;
                            currentBooking.status = currentBooking.changeRequest?.status.includes('hotel re-acknowledgement') ? 'Updated booking confirmed by hotel' : 'Confirmed by hotel';
                            addBookingAudit('Hotel acknowledged the exact dates, nights, guest count, and price.');
                            showConfirmation();
                        });
                        document.querySelector('#propose-change')?.addEventListener('click', () => {
                            currentBooking.changeRequest = { proposedNights: 4, status: 'Awaiting customer approval' };
                            addBookingAudit('Hotel proposed shortening the stay to 4 nights; original booking remains unchanged pending customer consent.');
                            showConfirmation();
                        });
                        document.querySelector('#reject-change')?.addEventListener('click', () => {
                            currentBooking.changeRequest.status = 'Rejected by customer · original booking retained';
                            currentBooking.status = 'Confirmed · original dates unchanged';
                            addBookingAudit('Customer rejected the change; original confirmed dates and total remain in force.');
                            showConfirmation();
                        });
                        document.querySelector('#approve-change')?.addEventListener('click', () => {
                            currentBooking.checkOut = new Date(Date.parse(`${currentBooking.checkIn}T00:00:00Z`) + currentBooking.changeRequest.proposedNights * 86400000).toISOString().slice(0, 10);
                            currentBooking.changeRequest.status = 'Approved by customer · awaiting hotel re-acknowledgement';
                            currentBooking.hotelAcknowledged = false;
                            currentBooking.status = 'Amended booking pending hotel confirmation';
                            updateBookingPrice();
                            addBookingAudit(`Customer approved ${currentBooking.nights} nights and the recalculated total ${money(currentBooking.total)}.`);
                            showConfirmation();
                        });
                        document.querySelector('#verify-checkin').addEventListener('click', () => {
                            if (!currentBooking.hotelAcknowledged) {
                                document.querySelector('#checkin-result').textContent = 'Discrepancy: hotel has not acknowledged this reservation.';
                                document.querySelector('#checkin-result').classList.remove('confirmed');
                                currentBooking.status = 'Dispute opened · awaiting hotel acknowledgement';
                                addBookingAudit('Check-in blocked because hotel acknowledgement is missing; dispute opened.');
                                showConfirmation();
                                return;
                            }
                            const reportedNights = Number(document.querySelector('#hotel-reported-nights').value);
                            if (reportedNights !== currentBooking.nights) {
                                currentBooking.status = 'Dispute opened · stay length mismatch';
                                addBookingAudit(`Check-in discrepancy: hotel reported ${reportedNights} nights; confirmation requires ${currentBooking.nights}.`);
                                showConfirmation();
                                const result = document.querySelector('#checkin-result');
                                result.textContent = `Discrepancy flagged: ${reportedNights} reported vs ${currentBooking.nights} confirmed nights. Demo dispute opened.`;
                                result.classList.remove('confirmed');
                            } else {
                                currentBooking.status = 'Check-in verified';
                                addBookingAudit(`Check-in verified for ${currentBooking.nights} nights.`);
                                showConfirmation();
                                document.querySelector('#checkin-result').textContent = 'Check-in verified · dates match the hotel confirmation.';
                                document.querySelector('#checkin-result').classList.add('confirmed');
                            }
                        });
                    }

                    document.querySelector('#search-form').addEventListener('submit', (event) => {
                        event.preventDefault();
                        checkIn = document.querySelector('#check-in').value;
                        checkOut = document.querySelector('#check-out').value;
                        guestCount = Number(document.querySelector('#guests').value);
                        if (!checkIn || !checkOut || nightCount() < 1) { alert('Choose a valid check-out date after check-in.'); return; }
                        document.querySelector('#results-heading').textContent = `${nightCount()}-night stays in ${document.querySelector('#destination').value || 'all locations'}`;
                        renderHotels();
                        if (selectedHotel) selectHotel(selectedHotel);
                    });
                    guestForm.addEventListener('submit', (event) => {
                        event.preventDefault();
                        const name = document.querySelector('#guest-name').value.trim();
                        const email = document.querySelector('#guest-email').value.trim();
                        if (!selectedHotel || !name || !email) return;
                        const nights = nightCount();
                        if (nights > selectedHotel.maxNights) {
                            const bookingError = document.querySelector('#booking-error');
                            bookingError.hidden = false;
                            bookingError.textContent = `This sample hotel allows at most ${selectedHotel.maxNights} nights.`;
                            return;
                        }
                        currentBooking = {
                            id: `CNX-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
                            name,
                            email,
                            hotel: selectedHotel,
                            checkIn,
                            checkOut,
                            guests: guestCount,
                            hotelAcknowledged: false,
                            changeRequest: null,
                            audit: [],
                            status: 'Awaiting hotel acknowledgement'
                        };
                        updateBookingPrice();
                        addBookingAudit(`Customer requested ${currentBooking.nights} nights from ${dateLabel(checkIn)} through ${dateLabel(checkOut)} for ${money(currentBooking.total)}.`);
                        showConfirmation();
                    });

                    const today = new Date();
                    const tomorrow = new Date(today.getTime() + 86400000);
                    const nextDay = new Date(today.getTime() + 2 * 86400000);
                    document.querySelector('#check-in').value = today.toISOString().slice(0, 10);
                    document.querySelector('#check-out').value = nextDay.toISOString().slice(0, 10);
                    document.querySelector('#check-in').min = today.toISOString().slice(0, 10);
                    document.querySelector('#check-out').min = tomorrow.toISOString().slice(0, 10);
                    checkIn = document.querySelector('#check-in').value;
                    checkOut = document.querySelector('#check-out').value;
                    renderHotels();
                })();
            </script>
        </body>
        </html>
        ''')


@portal.route("/preview/pos")
def pos_preview():
                try:
                                if not ip_address(request.remote_addr).is_loopback:
                                                abort(404)
                except ValueError:
                                abort(404)
                return render_template_string('''
                <!doctype html>
                <html lang="en">
                <head>
                    <meta charset="utf-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>Hotel POS Demo | Cinnex</title>
                    <style>
                        * { box-sizing: border-box; }
                        body { margin: 0; background: #f1f5f2; color: #172321; font: 14px/1.45 Arial, sans-serif; }
                        button, input, select { font: inherit; }
                        button { cursor: pointer; }
                        .topbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 12px 22px; background: #173b34; color: white; }
                        .brand { display: flex; align-items: center; gap: 12px; }
                        .brand img { width: 132px; height: auto; }
                        .brand-label { color: #c6d9d0; }
                        .top-actions { display: flex; align-items: center; gap: 12px; }
                        .top-actions a { color: white; }
                        .demo-flag { padding: 5px 9px; border-radius: 4px; background: #f3c969; color: #3a2b0e; font-size: 12px; font-weight: 700; }
                        .pos-layout { display: grid; grid-template-columns: minmax(0, 1fr) 370px; gap: 18px; max-width: 1440px; margin: 18px auto; padding: 0 18px; align-items: start; }
                        .catalog, .cart { background: white; border: 1px solid #dce5e0; border-radius: 6px; }
                        .catalog { padding: 18px; }
                        .catalog-head { display: flex; justify-content: space-between; gap: 16px; align-items: center; flex-wrap: wrap; }
                        h1 { margin: 0; font-size: 22px; }
                        .subhead { color: #64736d; }
                        .location-select { width: auto; min-width: 180px; }
                        .toolbar { display: flex; gap: 10px; margin: 16px 0 12px; }
                        .search { flex: 1; min-width: 0; }
                        .categories { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 15px; }
                        .category { border: 1px solid #cbd8d1; border-radius: 4px; padding: 7px 11px; color: #31564a; background: white; }
                        .category[aria-pressed="true"] { background: #17624f; border-color: #17624f; color: white; }
                        .product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
                        .product { min-height: 124px; display: flex; flex-direction: column; justify-content: space-between; text-align: left; border: 1px solid #dce5e0; border-radius: 5px; padding: 12px; background: white; color: #172321; }
                        .product:hover { border-color: #17624f; background: #f7fbf8; }
                        .product-name { font-weight: 700; }
                        .product-category { color: #64736d; font-size: 12px; margin-top: 4px; }
                        .product-price { color: #17624f; font-size: 16px; font-weight: 700; margin-top: 12px; }
                        .cart { position: sticky; top: 12px; overflow: hidden; }
                        .cart-head { padding: 15px 16px; display: flex; justify-content: space-between; border-bottom: 1px solid #e2e9e5; }
                        .cart-head h2 { margin: 0; font-size: 17px; }
                        .cart-lines { padding: 4px 16px; max-height: 42vh; overflow: auto; }
                        .empty { padding: 30px 10px; text-align: center; color: #64736d; }
                        .cart-line { display: grid; grid-template-columns: 1fr auto; gap: 8px; padding: 12px 0; border-bottom: 1px solid #edf1ef; }
                        .line-title { font-weight: 600; }
                        .line-price { color: #52645c; font-size: 13px; }
                        .qty-controls { display: flex; align-items: center; gap: 8px; }
                        .qty-controls button { width: 28px; height: 28px; border: 1px solid #cbd8d1; border-radius: 4px; background: white; }
                        .checkout { padding: 15px 16px; border-top: 1px solid #e2e9e5; }
                        .checkout label { display: grid; gap: 5px; margin-bottom: 10px; font-weight: 600; }
                        .totals { display: grid; gap: 6px; margin: 13px 0; }
                        .total-row { display: flex; justify-content: space-between; }
                        .grand-total { padding-top: 9px; border-top: 1px solid #dce5e0; font-size: 17px; font-weight: 700; }
                        .charge { width: 100%; border: 0; border-radius: 4px; padding: 12px; background: #17624f; color: white; font-weight: 700; }
                        .charge:disabled { cursor: not-allowed; background: #aab8b1; }
                        .notice { min-height: 20px; margin-top: 9px; color: #9b3023; }
                        #receipt { display: none; }
                        #receipt.visible { display: block; margin: 18px auto; width: min(100% - 36px, 520px); }
                        .receipt-box { background: white; border: 1px dashed #75847d; padding: 18px; }
                        .receipt-box h2, .receipt-box p { text-align: center; }
                        .receipt-row { display: flex; justify-content: space-between; gap: 10px; margin: 7px 0; }
                        .receipt-actions { display: flex; justify-content: center; gap: 10px; margin-top: 12px; }
                        .receipt-actions button { border: 1px solid #b9c8c0; border-radius: 4px; padding: 8px 12px; background: white; }
                        @media (max-width: 850px) { .pos-layout { grid-template-columns: 1fr; } .cart { position: static; } .cart-lines { max-height: none; } }
                        @media (max-width: 520px) { .topbar { align-items: flex-start; padding: 11px 14px; } .brand img { width: 105px; } .brand-label { font-size: 12px; } .pos-layout { padding: 0 10px; margin: 10px auto; gap: 10px; } .catalog { padding: 12px; } .product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .toolbar { flex-direction: column; } }
                        @media print { body { background: white; } .topbar, .pos-layout, .receipt-actions { display: none !important; } #receipt { display: block !important; width: 72mm; margin: 0; } .receipt-box { border: 0; padding: 0; } }
                    </style>
                </head>
                <body>
                    <header class="topbar">
                        <div class="brand"><img src="{{ url_for('static', filename='cinnex_logo.svg') }}" alt="Cinnex"><span class="brand-label">Hotel point of sale</span></div>
                        <div class="top-actions"><span class="demo-flag">DEMO · NO PAYMENT</span><a href="{{ url_for('business.dashboard_preview') }}">Admin dashboard</a></div>
                    </header>
                    <main class="pos-layout">
                        <section class="catalog">
                            <div class="catalog-head"><div><h1>New sale</h1><div class="subhead">Cafe, minibar and guest services</div></div><select class="location-select" id="location"><option>Cinnex City · Lobby Cafe</option><option>Cinnex Coast · Pool Bar</option><option>Cinnex Airport · Market</option></select></div>
                            <div class="toolbar"><input class="search" id="search" type="search" placeholder="Search items" aria-label="Search products"></div>
                            <nav class="categories" id="categories" aria-label="Product categories"></nav>
                            <div class="product-grid" id="products"></div>
                        </section>
                        <aside class="cart" aria-label="Current sale">
                            <div class="cart-head"><h2>Current sale</h2><span id="item-count">0 items</span></div>
                            <div class="cart-lines" id="cart-lines"><div class="empty">Select an item to begin.</div></div>
                            <div class="checkout">
                                <label>Payment method<select id="payment-method"><option>Room charge</option><option>Cash · demo</option><option>Card · demo only</option></select></label>
                                <label id="room-field">Guest room<input id="room-number" inputmode="numeric" placeholder="Room number"></label>
                                <div class="totals"><div class="total-row"><span>Subtotal</span><span id="subtotal">$0.00</span></div><div class="total-row"><span>Tax estimate (8.25%)</span><span id="tax">$0.00</span></div><div class="total-row grand-total"><span>Total</span><span id="total">$0.00</span></div></div>
                                <button class="charge" id="checkout" type="button" disabled>Complete demo sale</button>
                                <div class="notice" id="notice" role="status" aria-live="polite"></div>
                            </div>
                        </aside>
                    </main>
                    <section id="receipt" aria-live="polite"></section>
                    <script>
                        (() => {
                            const products = [
                                { id: 'espresso', name: 'Espresso', category: 'Cafe', price: 3.50 },
                                { id: 'latte', name: 'Caffe latte', category: 'Cafe', price: 5.00 },
                                { id: 'tea', name: 'Herbal tea', category: 'Cafe', price: 4.00 },
                                { id: 'sandwich', name: 'Club sandwich', category: 'Cafe', price: 15.00 },
                                { id: 'salad', name: 'Seasonal salad', category: 'Cafe', price: 13.50 },
                                { id: 'water', name: 'Sparkling water', category: 'Minibar', price: 4.00 },
                                { id: 'snack', name: 'Local snack box', category: 'Minibar', price: 8.50 },
                                { id: 'soda', name: 'Soft drink', category: 'Minibar', price: 4.50 },
                                { id: 'kit', name: 'Travel essentials kit', category: 'Minibar', price: 12.00 },
                                { id: 'spa', name: 'Spa day pass', category: 'Wellness', price: 45.00 },
                                { id: 'parking', name: 'Overnight parking', category: 'Services', price: 28.00 },
                                { id: 'late', name: 'Late checkout', category: 'Services', price: 35.00 }
                            ];
                            const cart = new Map();
                            let activeCategory = 'All items';
                            const productGrid = document.querySelector('#products');
                            const cartLines = document.querySelector('#cart-lines');
                            const notice = document.querySelector('#notice');

                            function money(cents) { return `$${(cents / 100).toFixed(2)}`; }
                            function renderCategories() {
                                const names = ['All items', ...new Set(products.map((product) => product.category))];
                                const container = document.querySelector('#categories');
                                container.replaceChildren(...names.map((name) => {
                                    const button = document.createElement('button');
                                    button.type = 'button';
                                    button.className = 'category';
                                    button.textContent = name;
                                    button.setAttribute('aria-pressed', String(name === activeCategory));
                                    button.addEventListener('click', () => { activeCategory = name; renderCategories(); renderProducts(); });
                                    return button;
                                }));
                            }
                            function renderProducts() {
                                const query = document.querySelector('#search').value.trim().toLowerCase();
                                const visible = products.filter((product) => (activeCategory === 'All items' || product.category === activeCategory) && product.name.toLowerCase().includes(query));
                                productGrid.replaceChildren(...visible.map((product) => {
                                    const button = document.createElement('button');
                                    button.type = 'button';
                                    button.className = 'product';
                                    const name = document.createElement('span');
                                    name.className = 'product-name';
                                    name.textContent = product.name;
                                    const category = document.createElement('span');
                                    category.className = 'product-category';
                                    category.textContent = product.category;
                                    const price = document.createElement('span');
                                    price.className = 'product-price';
                                    price.textContent = money(Math.round(product.price * 100));
                                    button.append(name, category, price);
                                    button.addEventListener('click', () => { cart.set(product.id, (cart.get(product.id) || 0) + 1); notice.textContent = ''; renderCart(); });
                                    return button;
                                }));
                            }
                            function renderCart() {
                                const lines = [...cart.entries()].map(([id, quantity]) => ({ product: products.find((item) => item.id === id), quantity }));
                                const count = lines.reduce((sum, line) => sum + line.quantity, 0);
                                document.querySelector('#item-count').textContent = `${count} ${count === 1 ? 'item' : 'items'}`;
                                if (!lines.length) cartLines.innerHTML = '<div class="empty">Select an item to begin.</div>';
                                else {
                                    cartLines.replaceChildren(...lines.map(({ product, quantity }) => {
                                        const row = document.createElement('div');
                                        row.className = 'cart-line';
                                        const details = document.createElement('div');
                                        const title = document.createElement('div');
                                        title.className = 'line-title';
                                        title.textContent = product.name;
                                        const price = document.createElement('div');
                                        price.className = 'line-price';
                                        price.textContent = `${quantity} × ${money(Math.round(product.price * 100))}`;
                                        details.append(title, price);
                                        const controls = document.createElement('div');
                                        controls.className = 'qty-controls';
                                        for (const [label, change] of [['−', -1], ['+', 1]]) {
                                            const button = document.createElement('button');
                                            button.type = 'button';
                                            button.textContent = label;
                                            button.setAttribute('aria-label', `${change < 0 ? 'Remove one' : 'Add one'} ${product.name}`);
                                            button.addEventListener('click', () => {
                                                const next = (cart.get(product.id) || 0) + change;
                                                if (next < 1) cart.delete(product.id); else cart.set(product.id, next);
                                                renderCart();
                                            });
                                            controls.append(button);
                                        }
                                        row.append(details, controls);
                                        return row;
                                    }));
                                }
                                const subtotalCents = lines.reduce((sum, line) => sum + Math.round(line.product.price * 100) * line.quantity, 0);
                                const taxCents = Math.round(subtotalCents * 0.0825);
                                document.querySelector('#subtotal').textContent = money(subtotalCents);
                                document.querySelector('#tax').textContent = money(taxCents);
                                document.querySelector('#total').textContent = money(subtotalCents + taxCents);
                                document.querySelector('#checkout').disabled = count === 0;
                            }
                            document.querySelector('#search').addEventListener('input', renderProducts);
                            document.querySelector('#payment-method').addEventListener('change', (event) => {
                                document.querySelector('#room-field').hidden = event.target.value !== 'Room charge';
                            });
                            document.querySelector('#checkout').addEventListener('click', async () => {
                                const lines = [...cart.entries()].map(([id, quantity]) => ({ product: products.find((item) => item.id === id), quantity }));
                                if (!lines.length) return;
                                const payment = document.querySelector('#payment-method').value;
                                const room = document.querySelector('#room-number').value.trim();
                                if (payment === 'Room charge' && !room) { notice.textContent = 'Enter a guest room number for room charge.'; return; }
                                const subtotalCents = lines.reduce((sum, line) => sum + Math.round(line.product.price * 100) * line.quantity, 0);
                                const taxCents = Math.round(subtotalCents * 0.0825);
                                const checkoutButton = document.querySelector('#checkout');
                                checkoutButton.disabled = true;
                                let savedSale;
                                try {
                                    const response = await fetch('{{ url_for("business.save_pos_demo_sale") }}', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({
                                            property: document.querySelector('#location').value,
                                            room_number: room,
                                            payment_method: payment,
                                            items: lines.map(({ product, quantity }) => ({ product_id: product.id, quantity }))
                                        })
                                    });
                                    const result = await response.json();
                                    if (!response.ok) throw new Error(result.error || 'The demo sale could not be saved.');
                                    savedSale = result;
                                } catch (error) {
                                    notice.textContent = error.message || 'The demo sale could not be saved.';
                                    checkoutButton.disabled = false;
                                    return;
                                }
                                const rows = lines.map(({ product, quantity }) => `<div class="receipt-row"><span>${quantity} × ${product.name}</span><span>${money(Math.round(product.price * 100) * quantity)}</span></div>`).join('');
                                const receipt = document.querySelector('#receipt');
                                receipt.className = 'visible';
                                receipt.innerHTML = `<div class="receipt-box"><h2>CINNEX · DEMO RECEIPT</h2><p>TEST SALE · NO PAYMENT PROCESSED</p><div class="receipt-row"><span>Sale ID</span><span>${savedSale.sale_id}</span></div><div class="receipt-row"><span>Property</span><span>${document.querySelector('#location').value.split(' · ')[0]}</span></div>${room ? `<div class="receipt-row"><span>Room</span><span>${room}</span></div>` : ''}<hr>${rows}<hr><div class="receipt-row"><span>Subtotal</span><span>${money(subtotalCents)}</span></div><div class="receipt-row"><span>Tax estimate</span><span>${money(taxCents)}</span></div><div class="receipt-row"><strong>Total</strong><strong>${money(subtotalCents + taxCents)}</strong></div><p>Payment method: ${payment}</p><div class="receipt-actions"><button type="button" onclick="window.print()">Print receipt</button></div></div>`;
                                cart.clear();
                                renderCart();
                                notice.textContent = `Demo sale ${savedSale.sale_id} saved to ${savedSale.csv_file}. No payment was processed.`;
                                receipt.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            });
                            renderCategories();
                            renderProducts();
                            renderCart();
                        })();
                    </script>
                </body>
                </html>
                ''')


@portal.route("/preview/pos/save-sale", methods=["POST"])
def save_pos_demo_sale():
    try:
        if not ip_address(request.remote_addr).is_loopback:
            abort(404)
    except ValueError:
        abort(404)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid sale request."), 400

    property_name = data.get("property")
    payment_method = data.get("payment_method")
    room_number = str(data.get("room_number", "")).strip()
    items = data.get("items")
    allowed_methods = {"Room charge", "Cash · demo", "Card · demo only"}
    if property_name not in POS_DEMO_PROPERTIES or payment_method not in allowed_methods:
        return jsonify(error="Choose a valid demo property and payment method."), 400
    if payment_method == "Room charge" and not room_number.isdigit():
        return jsonify(error="Enter a numeric guest room number."), 400
    if not isinstance(items, list) or not items or len(items) > 30:
        return jsonify(error="Add between 1 and 30 product lines."), 400

    quantities = {}
    for item in items:
        if not isinstance(item, dict):
            return jsonify(error="Invalid sale item."), 400
        product_id = item.get("product_id")
        quantity = item.get("quantity")
        if product_id not in POS_DEMO_PRODUCTS or type(quantity) is not int or not 1 <= quantity <= 99:
            return jsonify(error="A product or quantity is invalid."), 400
        quantities[product_id] = quantities.get(product_id, 0) + quantity
        if quantities[product_id] > 99:
            return jsonify(error="Maximum quantity per product is 99."), 400

    subtotal_cents = sum(POS_DEMO_PRODUCTS[product_id][2] * quantity for product_id, quantity in quantities.items())
    tax_cents = round(subtotal_cents * 0.0825)
    total_cents = subtotal_cents + tax_cents
    sale_id = f"CNX-DEMO-{uuid4().hex[:10].upper()}"
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    fields = [
        "sale_id", "created_at", "property", "room_number", "payment_method",
        "product_id", "product_name", "category", "quantity", "unit_price",
        "line_subtotal", "tax_rate", "sale_subtotal", "tax_amount", "sale_total", "is_demo",
    ]
    try:
        needs_header = not POS_DEMO_CSV.exists() or POS_DEMO_CSV.stat().st_size == 0
        with POS_DEMO_CSV.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fields)
            if needs_header:
                writer.writeheader()
            for product_id, quantity in quantities.items():
                name, category, unit_price_cents = POS_DEMO_PRODUCTS[product_id]
                line_subtotal_cents = unit_price_cents * quantity
                writer.writerow({
                    "sale_id": sale_id,
                    "created_at": created_at,
                    "property": property_name,
                    "room_number": room_number,
                    "payment_method": payment_method,
                    "product_id": product_id,
                    "product_name": name,
                    "category": category,
                    "quantity": quantity,
                    "unit_price": f"{unit_price_cents / 100:.2f}",
                    "line_subtotal": f"{line_subtotal_cents / 100:.2f}",
                    "tax_rate": "0.0825",
                    "sale_subtotal": f"{subtotal_cents / 100:.2f}",
                    "tax_amount": f"{tax_cents / 100:.2f}",
                    "sale_total": f"{total_cents / 100:.2f}",
                    "is_demo": "TRUE",
                })
    except OSError:
        return jsonify(error="Could not write the POS demo CSV file."), 500

    return jsonify(
        sale_id=sale_id,
        subtotal=f"{subtotal_cents / 100:.2f}",
        tax=f"{tax_cents / 100:.2f}",
        total=f"{total_cents / 100:.2f}",
        csv_file=POS_DEMO_CSV.name,
        is_demo=True,
    ), 201


@portal.route("/preview/receipt")
def preview_receipt():
        try:
                if not ip_address(request.remote_addr).is_loopback:
                        abort(404)
        except ValueError:
                abort(404)
        return render_template_string('''
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Sample Thermal Receipt | Cinnex</title>
            <style>
                * { box-sizing: border-box; }
                body { margin: 0; padding: 20px; background: #edf1ef; color: #111; font: 14px/1.4 Arial, sans-serif; }
                .toolbar { display: flex; justify-content: center; gap: 10px; margin-bottom: 16px; }
                .toolbar select, .toolbar button { padding: 9px; font: inherit; }
                .toolbar button { border: 0; border-radius: 4px; background: #17624f; color: #fff; }
                .receipt { --paper-width: 72mm; width: var(--paper-width); margin: auto; padding: 5mm; background: white; }
                .receipt.paper-58 { --paper-width: 52mm; }
                .receipt.paper-80 { --paper-width: 72mm; }
                header, .footer { text-align: center; }
                header { border-bottom: 1px dashed; padding-bottom: 9px; }
                header img { width: 40mm; max-width: 100%; }
                h1 { margin: 8px 0 2px; font-size: 16px; }
                .line { display: flex; justify-content: space-between; gap: 8px; margin: 8px 0; }
                .total { border-top: 1px dashed; padding-top: 8px; font-size: 16px; font-weight: bold; }
                .footer { border-top: 1px dashed; margin-top: 12px; padding-top: 9px; font-size: 11px; }
                @page { margin: 3mm; }
                @media print { body { padding: 0; background: #fff; } .toolbar { display: none; } .receipt { margin: 0; padding: 0; width: var(--paper-width); } }
            </style>
        </head>
        <body>
            <div class="toolbar"><label>Paper width <select id="paper-size"><option value="80">80 mm</option><option value="58">58 mm</option></select></label><button onclick="window.print()">Print sample</button></div>
            <main class="receipt paper-80" id="receipt">
                <header><img src="{{ url_for('static', filename='cinnex_logo.svg') }}" alt="Cinnex"><h1>SAMPLE RECEIPT</h1><div>DEMO-0001</div></header>
                <div class="line"><span>Date</span><span>2026-10-25</span></div>
                <div class="line"><span>Customer</span><span>Sample Customer</span></div>
                <p>Room booking deposit</p>
                <div class="line total"><span>DEMO TOTAL</span><span>$25.00</span></div>
                <p class="footer">TEST PRINT ONLY<br>No payment was processed</p>
            </main>
            <script>
                const paperSize = document.querySelector('#paper-size');
                const receipt = document.querySelector('#receipt');
                paperSize.addEventListener('change', () => {
                    receipt.classList.toggle('paper-58', paperSize.value === '58');
                    receipt.classList.toggle('paper-80', paperSize.value === '80');
                });
            </script>
        </body>
        </html>
        ''')