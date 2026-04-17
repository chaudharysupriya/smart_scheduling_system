# Intelligent Appointment Scheduling System

A data-driven scheduling tool built with Python and Streamlit for solo service businesses such as home salons, mobile hairdressers, tutors, and repair services. The system analyses historical booking data to identify demand patterns across seasons and days of the week, then recommends optimised time slots for each month. It provides a complete owner dashboard for managing schedules, monitoring bookings, and reviewing performance metrics, alongside a public-facing customer booking interface where clients can view available slots and make appointments online.

---

## Features

- **Demand Analysis Dashboard** — interactive heatmap showing booking frequency by day and time slot, with cancellation rates and lead times on hover
- **Slot Quality Scoring Algorithm** — scores every day and time combination using a weighted formula covering demand frequency, customer diversity, cancellation reliability, and no-show rate
- **Schedule Recommendation Generator** — produces an intelligent weekly schedule template for any target month based on historical demand patterns
- **Fixed vs Behaviour-Based Schedule Comparison** — side-by-side performance comparison of a static always-open schedule against the intelligent demand-driven schedule
- **Simulation Engine** — runs synthetic booking requests through both scheduling models over configurable weeks and produces reproducible performance metrics
- **Customer Booking Portal** — public-facing page where customers can view available slots for the published month and book appointments
- **Email Confirmation** — sends HTML booking confirmation and cancellation emails to customers via SMTP with support for Gmail and Outlook
- **Owner Authentication** — secure login with SHA-256 hashed passwords, session-based access control, and a five-attempt lockout
- **Public Landing Page** — homepage displaying business information and a prominent booking link, accessible without login
- **Schedule Publishing Workflow** — owner reviews and adjusts the recommended schedule then publishes it, making those slots live for customers instantly
- **Dataset Update Mechanism** — owner can merge customer portal bookings into the main historical dataset to improve future recommendations over time

---

## Project Structure

```
scheduling_system/
│
├── app.py                          # Public homepage — entry point for the application
├── generate_data.py                # Standalone script to generate synthetic booking data
├── business_settings.json          # Saved business configuration and owner credentials (auto-created)
├── requirements.txt                # Python package dependencies
│
├── data/
│   ├── booking_data.csv            # Main historical booking dataset (1,919 records included)
│   ├── new_bookings.csv            # Customer portal bookings (auto-created on first booking)
│   └── published_schedule.json     # Owner-published monthly schedule (auto-created on publish)
│
├── pages/
│   ├── 01_dashboard.py             # Demand analysis dashboard — heatmaps, charts, slot deep dive
│   ├── 02_recommendations.py       # Schedule recommendation generator and publish workflow
│   ├── 03_comparison.py            # Fixed vs behaviour-based schedule comparison page
│   ├── 04_simulation.py            # Simulation engine — runs synthetic booking requests
│   ├── 05_customer_booking.py      # Public customer booking and cancellation portal
│   ├── 06_manage_bookings.py       # Owner booking management — today, upcoming, attendance
│   └── 07_settings.py             # Business settings, credentials, email config, data upload
│
├── modules/
│   ├── analysis_engine.py          # Data filtering, pivot calculations, slot deep dive logic
│   ├── booking_manager.py          # Booking creation, cancellation, attendance update functions
│   ├── data_loader.py              # CSV loading, upload validation, dataset merge functions
│   ├── scheduler.py                # Fixed and behaviour-based schedule generation logic
│   ├── scoring_engine.py           # Slot quality score calculation and classification
│   └── simulation.py               # Synthetic request generation and simulation runner
│
├── utils/
│   ├── auth.py                     # Authentication — login, logout, password hashing, session state
│   ├── charts.py                   # All Plotly chart and HTML table rendering functions
│   ├── email_sender.py             # SMTP email sending for confirmations and cancellations
│   └── helpers.py                  # Shared helper functions — month names, percentage formatting
│
└── .streamlit/
    └── config.toml                 # Streamlit theme configuration — enforces light mode
```

---

## Requirements

**Python 3.10 or higher** is required.

| Package    | Minimum Version |
|------------|-----------------|
| streamlit  | 1.35.0          |
| pandas     | 2.0.0           |
| numpy      | 1.26.0          |
| plotly     | 5.20.0          |

Install all dependencies with:

```bash
pip install -r requirements.txt
```

---

## Setup Instructions

### Step 1 — Get the project

Clone or download the project folder to your machine. The folder you want is `scheduling_system/`.

### Step 2 — Check your Python version

Open a terminal and run:

```bash
python --version
```

You need Python 3.10 or higher. If your version is lower, download the latest Python from [python.org](https://python.org).

### Step 3 — Navigate to the project folder

```bash
cd path/to/scheduling_system
```

### Step 4 — Create and activate a virtual environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**

```bash
python -m venv venv
source venv/bin/activate
```

You should see `(venv)` appear at the start of your terminal prompt once activated.

### Step 5 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 6 — Confirm the data file is in place

The file `booking_data.csv` must be inside the `data/` folder. It is already included in this project.

If for any reason the file is missing, run the data generator from the `scheduling_system/` folder:

```bash
python generate_data.py
```

Then move the output file into `data/booking_data.csv`.

### Step 7 — Run the application

```bash
streamlit run app.py
```

### Step 8 — Open the application in your browser

Streamlit will open the application automatically at:

```
http://localhost:8501
```

If the browser does not open automatically, copy and paste that address into your browser manually.

### Step 9 — Set up your owner credentials

On first run, navigate to **Settings** using the sidebar. Sign in with the default credentials:

- **Username:** `admin`
- **Password:** `admin123`

Go to the **Owner Account** section and change both the username and password immediately to something secure.

### Step 10 — Configure email notifications

In **Settings**, scroll to **Email Settings**. Enter your email address and App Password.

**For Gmail:**

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Search for **App Passwords** in the search bar at the top
3. If you cannot find it, go directly to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Select **Mail** as the app and your device, then click **Generate**
5. Copy the 16-character password shown and paste it into the **Sender Email Password** field in Settings
6. Use `smtp.gmail.com` as the SMTP server and `587` as the port

**For Outlook:**

- SMTP Server: `smtp.office365.com`
- Port: `587`
- Enter your full Outlook email address and account password

Click **Save Email Settings**, then use the **Send Test Email** button to verify the configuration works.

### Step 11 — Configure your business profile

In **Settings**, fill in:

- Business Name
- Business Type
- Working Days (tick the days you operate)
- Opening and Closing Hours
- Services Offered (one per line)
- Average Service Duration

Click **Save Settings**.

### Step 12 — Publish your first schedule

1. Go to **Schedule Recommendations** in the sidebar
2. Select the month you want to open for bookings
3. Click **Generate Recommended Schedule**
4. Review the suggested slots — adjust any using the manual override checkboxes
5. Click **Publish Schedule**

The customer booking page will immediately show the available slots for that month.

---

## How the System Works

The system uses **same-period historical comparison**, meaning when planning for March it only analyses past March data across all recorded years — not all months combined. This preserves seasonal patterns that would otherwise be diluted. Each day and time slot is scored using a weighted formula: `score = (demand frequency × 0.40) + (customer diversity × 0.25) + (reliability × 0.20) + (attendance × 0.15)`, where reliability penalises high cancellation rates and attendance penalises no-shows. Slots scoring above 0.65 are classified as recommended (green), 0.40 to 0.65 as marginal (amber), and below 0.40 as not recommended (red). Recency weighting gives the most recent year a weight of 0.6 and all earlier years a combined weight of 0.4, so newer customer behaviour has greater influence on recommendations than older data.

---

## Owner Workflow

Each month, the recommended owner workflow is:

1. **Upload or merge new data** — go to Settings and upload any new booking records, or use Manage Bookings to merge portal submissions into the main dataset
2. **Open the Dashboard** — select the target month and review the demand heatmap, year-over-year trends, and slot quality scores
3. **Review cancellation patterns** — check the cancellation rate table and identify any slots consistently above 25%
4. **Generate a schedule** — go to Schedule Recommendations, select the target month, and click Generate
5. **Adjust manually if needed** — use the override checkboxes to open or close any slots the algorithm got wrong
6. **Publish the schedule** — click Publish Schedule to make the selected slots live on the customer booking page
7. **Monitor incoming bookings** — check the Manage Bookings page daily to see today's appointments and upcoming bookings
8. **Record attendance** — after each appointment, mark the customer as Attended, Cancelled, or No-Show using the action buttons
9. **End of month** — go to Manage Bookings and click Update Dataset to merge confirmed portal bookings into the main historical dataset, improving future recommendations

---

## Customer Workflow

1. Visit the business website (the public homepage)
2. Click **Book an Appointment**
3. Select a week within the currently published month using the date picker
4. The booking grid shows available slots in green — click **Book** on the desired slot
5. Fill in your name, phone number, email address, and the service you require
6. Click **Confirm Booking**
7. A confirmation email is sent to your email address with your booking reference number
8. To cancel, return to the booking page, scroll to the cancellation section, enter your booking reference, and confirm — a cancellation email will be sent automatically

---

## Email Configuration

### Gmail Setup

Gmail requires an **App Password** rather than your regular account password. This is a 16-character code generated specifically for third-party applications.

1. Sign in to your Google account at [myaccount.google.com](https://myaccount.google.com)
2. Make sure **2-Step Verification** is enabled (App Passwords are not available without it)
3. Go directly to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Enter a name for the app (for example: `Scheduling System`)
5. Click **Create** — Google will display a 16-character password
6. Copy the password immediately — it will not be shown again
7. Paste it into the **Sender Email Password** field in Settings

Settings to use:

| Field         | Value            |
|---------------|------------------|
| SMTP Server   | smtp.gmail.com   |
| SMTP Port     | 587              |

### Outlook Setup

| Field         | Value                  |
|---------------|------------------------|
| SMTP Server   | smtp.office365.com     |
| SMTP Port     | 587                    |
| Password      | Your regular Outlook password |

### Important Note on Email Failures

The system is designed so that **a failed email never prevents a booking from being saved**. If the SMTP connection fails for any reason — wrong password, network issue, or provider block — the booking is recorded in `new_bookings.csv` and the customer sees a warning rather than an error. The booking reference is still shown on screen.

---

## Data Files

| File | Location | Purpose |
|------|----------|---------|
| `booking_data.csv` | `data/` | Main historical dataset used for all demand analysis and schedule generation. 1,919 records included. |
| `new_bookings.csv` | `data/` | All customer bookings submitted through the portal. Auto-created on the first booking. |
| `published_schedule.json` | `data/` | The owner-published monthly schedule. Stores which slots are open for each day. Auto-created when the owner publishes a schedule. |
| `business_settings.json` | project root | Stores all business configuration including name, working hours, services, SMTP settings, and the hashed owner password. Auto-created on first save in Settings. |

---

## Running the Data Generator

The file `booking_data.csv` with 1,919 records is already included in the `data/` folder and the system is ready to use immediately. You do not need to run the generator unless you want to regenerate the data or start fresh.

If you do want to regenerate, run this command from inside the `scheduling_system/` folder:

```bash
python generate_data.py
```

The generator creates two years of synthetic booking data from January 2024 to December 2025. The data includes realistic patterns for:

- **Seasonal demand variation** — busier months reflect typical service business trends
- **Day of week patterns** — weekends and Fridays show higher demand
- **Time of day demand** — morning and early afternoon slots are more popular
- **UK bank holidays** — reduced bookings on public holidays
- **Cancellation and no-show rates** — varying by slot and season
- **Repeat versus new customer behaviour** — a proportion of bookings come from returning customers
- **Year-over-year variation** — slight growth between 2024 and 2025

---

## Academic Context

This system was developed as part of an MSc Information Technology dissertation at the University of the West of Scotland. The research investigates whether behaviour-based scheduling outperforms fixed scheduling for solo service businesses using historical customer booking data.

---

## Known Limitations

- **CSV storage** is suitable for prototype and academic demonstration purposes only. A production deployment would require a relational database such as PostgreSQL to handle concurrent bookings safely and prevent race conditions when multiple customers book at the same time.
- The system currently supports a **single business profile**. Multi-tenant support would require a significant architectural change.
- **Gmail accounts that use passkeys as the primary sign-in method** may not display the App Passwords option in account settings. In that case, go directly to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) or switch to an Outlook account using the SMTP settings provided above.

---

## License

This project is developed for academic purposes only.
