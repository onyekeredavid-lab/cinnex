# Cinnex Project

Cinnex is a business workspace for room bookings, staff access, company policies, orders, and invoices.

This project is a starter web app with:
- a login page
- a registration page
- an authenticated password-change page
- a business dashboard with room booking, policies, user administration, orders, and invoices
- a branded Cinnex logo
- MySQL-backed accounts with hashed passwords

## Purpose
This app represents the foundation of a future business system for Cinnex, built to support:
- client access
- business operations
- digital services
- long-term income and retirement planning

## Run locally

```bash
cd "$HOME/Desktop/Cinnex Project"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start your MySQL server and run the setup helper. It requests your MySQL root password and a new app password through hidden terminal prompts; it does not save either password to disk:

```bash
python3 setup_database.py
```

The helper creates the database and restricted app user, initializes the business tables, verifies the live schema, and starts the web app.

## Preview the dashboard

To view the dashboard layout without Gmail or a database login, run the app locally:

```bash
python3 app.py
```

Open `http://127.0.0.1:5003` and choose **Preview dashboard**. This loopback-only preview uses sample data and does not create or modify records. Real business modules still require a verified account.

From the admin preview, choose **Open hotel POS demo** or visit `/business/preview/pos`. It includes cafe/minibar products, search, categories, quantity controls, room-charge/cash/card options, and a printable sample receipt. Checkout is simulated only: no payment is processed and no sale is saved.

The **Open stay marketplace demo** is available at `/business/stay/demo`. It demonstrates exact date/night totals, sample hotel acknowledgements, customer-approved change requests, and mismatch/dispute handling. Properties and bookings are fictional and held only in browser memory; there is no live inventory, guest-data storage, or escrow/payment processing.

The stay demo uses Leaflet with OpenStreetMap tiles. The map needs internet access; hotel pins are fictional sample locations. For production/commercial traffic, select a tile provider or hosting arrangement that meets its usage policy.

After registering and verifying your first account, promote it to administrator in MySQL. Replace `your_username` with the account you created:

```sql
USE cinnex;
UPDATE users SET role = 'admin'
WHERE username = 'your_username' AND email_verified = TRUE;
```

All roles use the same login page at `/`. After login, users open the shared workspace at `/business/`; administrators have a separate, database-backed control center at `/business/admin`. New registrations receive the `customer` role. Admins can assign `admin`, `manager`, `staff`, or `customer` access. Admins manage users; admins and managers manage policies, orders, and invoices; staff and customers can book rooms and read policies. The local sample-only dashboard remains at `/business/preview`.

Then open:
- http://127.0.0.1:5003

The app creates or updates its database tables on first business-app use. Registration requires an email address; a mobile number is optional and is not verified. New accounts cannot log in until they verify their email. Codes expire after 10 minutes, allow five guesses, and can be resent once per minute. Password changes require the current password and an authenticated session.

For Gmail, enable 2-Step Verification and create a Google App Password. Use the App Password, not your regular Google password. Start the app with the launcher; it prompts privately for your Gmail address, App Password, and Cinnex database password, tests both connections, and starts Gunicorn with four workers on port 8000. Credentials are not written to project files.

```bash
python3 run_cinnex.py
```

The default Gunicorn bind is `0.0.0.0:8000` for local-network demos. Set `CINNEX_BIND=127.0.0.1:8000` to keep it accessible only from this Mac.

For deployment over HTTPS, set `COOKIE_SECURE=1`.

The booking module prevents overlapping reservations for the same room. Orders and invoices are basic internal records, not payment processing or tax/accounting software.

The local dashboard preview includes a hotel-chain trend chart with sample occupancy and revenue for three example properties. These figures are illustrative; live hotel reporting requires hotel/property booking and revenue records in the database.

## Bluetooth receipt printers

The invoice list has a **Print** link with a 58 mm / 80 mm thermal layout. The local dashboard preview also has a sample test print. Pair the printer in macOS **System Settings → Bluetooth**, add it under **Printers & Scanners** with its manufacturer driver, then select it in the browser print dialog. Choose the same roll width in the receipt page and printer settings. Browser printing uses the macOS printer driver; direct Bluetooth/ESC-POS commands from the web app are not supported. Printer compatibility depends on the printer model and macOS driver. Unpaid invoices are labeled as not being payment receipts.
