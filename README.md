# 🛒 Async Order Processing System

> A production-grade backend that handles orders asynchronously — with real payments, inventory locking, retry logic, and a live UI.

![Django](https://img.shields.io/badge/Django-6.0-green?style=flat-square&logo=django)
![Celery](https://img.shields.io/badge/Celery-5.x-brightgreen?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-blue?style=flat-square&logo=postgresql)
![Redis](https://img.shields.io/badge/Redis-Cloud-red?style=flat-square&logo=redis)
![Razorpay](https://img.shields.io/badge/Razorpay-Test%20Mode-blue?style=flat-square)

---

## 📺 What This System Does

When a user places an order, this system:

1. **Accepts the order instantly** — validates, saves, responds in < 200ms
2. **Processes it in the background** — payment + inventory handled by a Celery worker
3. **Retries on failure** — up to 3 times with exponential backoff (2s → 4s → 8s)
4. **Prevents duplicates** — idempotency key stops double-orders even on network retry
5. **Handles concurrency** — 10 people ordering the last burger? Only valid orders succeed
6. **Logs everything** — structured JSON logs for every state transition

### Live UI Features
- Place orders with Razorpay test payments
- Watch orders go `PENDING → PROCESSING → COMPLETED` in real time (auto-refreshes every 3s)
- Live inventory counter — turns red when stock is low
- Cancel pending orders with one click
- Filter orders by status

---

## 🏗 Architecture

```
Browser
   │
   │  POST /api/orders/razorpay/create/
   ▼
Django REST API  ────────────────────────────►  PostgreSQL (Supabase)
   │                                                    ▲
   │  .delay(order_id)  ← non-blocking                 │ read/write state
   ▼                                                    │
 Redis Queue  ──────────────►  Celery Worker  ──────────┘
(task broker)                 (background process)
                               ├── Payment step (Razorpay)
                               ├── Inventory step (SELECT FOR UPDATE)
                               ├── Retry on failure (max 3 times)
                               └── Update order status in DB
```
---
### 📁 Project Structure
ORDER_SYSTEM/
├── core/                     # Main Django project configuration
│   ├── __init__.py
│   ├── asgi.py              # ASGI config for async support
│   ├── celery.py            # Celery configuration
│   ├── settings.py          # Project settings
│   ├── urls.py              # Root URL routing
│   └── wsgi.py              # WSGI entry point
│
├── orders/                  # Orders app
│   ├── migrations/          # Database migrations
│   ├── templates/           # HTML templates
│   ├── __init__.py
│   ├── admin.py             # Admin panel config
│   ├── apps.py              # App configuration
│   ├── logger.py            # Custom logging logic
│   ├── models.py            # Database models
│   ├── serializers.py       # DRF serializers
│   ├── tasks.py             # Celery background tasks
│   ├── tests.py             # Unit tests
│   ├── urls.py              # App routes
│   └── views.py             # Business logic / API views
│
├── logs/
│   └── orders.log           # Application logs
│
├── venv/                    # Virtual environment (ignored in git)
├── .env                     # Environment variables
├── .gitignore               # Git ignore rules
├── db.sqlite3               # SQLite database
├── manage.py                # Django CLI entry point
└── requirements.txt         # Python dependencies
---

## 🚀 Full Setup Guide — From Zero to Running

Follow every step in order. This works even if you have never used Django before.

---

### Step 1 — Check Python Version

Open your terminal (PowerShell on Windows, Terminal on Mac/Linux) and run:
```bash
python --version
```
You need **Python 3.10 or higher**. If not installed, download from https://python.org/downloads

---

### Step 2 — Get the Code

```bash
git clone https://github.com/Harish-Huded-29/order-system.git
cd order-system
```

---

### Step 3 — Create a Virtual Environment

A virtual environment keeps this project's packages separate from everything else on your computer.

```bash
python -m venv venv
```

Now activate it:

```bash
# Windows:
venv\Scripts\activate

# Mac / Linux:
source venv/bin/activate
```

✅ You'll see `(venv)` at the start of your terminal line. That means it's active.

> ⚠️ Every time you open a new terminal window, you must activate the venv again before running commands.

---

### Step 4 — Install All Packages

```bash
pip install -r requirements.txt
```

Wait for it to finish. This installs Django, Celery, the Redis client, Razorpay SDK, and everything else needed.

---

### Step 5 — Get Your Supabase Database URL

Supabase gives you a free real PostgreSQL database. No credit card needed.

1. Go to **https://supabase.com** → click **Start for free**
2. Sign up with GitHub or Google
3. Click **New Project**
   - Name: `order-system`
   - Set a database password → **write it down, you'll need it**
   - Pick a region close to you → click **Create new project**
   - Wait about 2 minutes for it to set up
4. Once ready, click the green **Connect** button at the top right of the dashboard
5. In the popup, find the **Connection pooling** section
6. Copy the **URI** — it looks like this:
   ```
   postgresql://postgres.abcxyz:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
   ```
7. Replace `YOUR_PASSWORD` with the password you set in step 3

> ⚠️ Use the URL with port **6543** (connection pooler) — not 5432

---

### Step 6 — Get Your Redis URL

Redis holds task messages between Django and Celery.

1. Go to **https://redis.io/try-free** → sign up (free, no credit card)
2. Create a **Free** database — choose any region → click **Create**
3. Once created, click on your database name
4. Find **Public endpoint** — looks like:
   ```
   redis-12345.c1.us-east-1-2.ec2.cloud.redislabs.com:12345
   ```
5. Find **Password** — click the eye icon to reveal it
6. Your full Redis URL is:
   ```
   redis://:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT
   ```

---

### Step 7 — Get Your Razorpay Test Keys

1. Go to **https://razorpay.com** → sign up (free)
2. After logging in, look at the top of the dashboard — find the **Test Mode** toggle → make sure it is **ON** (blue)
3. Go to **Settings** (left sidebar) → **API Keys**
4. Click **Generate Test Key**
5. Copy both values:
   - **Key ID** — starts with `rzp_test_`
   - **Key Secret** — copy it immediately, it's shown only once

---

### Step 8 — Create Your `.env` File

In your project folder (the same folder as `manage.py`), create a new file called exactly `.env` (the dot at the start is important):

```bash
SECRET_KEY=django-insecure-replace-with-any-long-random-string-abc123xyz789
DEBUG=True
DATABASE_URL=postgresql://postgres.YOUR_PROJECT_ID:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
CELERY_BROKER_URL=redis://:YOUR_REDIS_PASSWORD@YOUR_REDIS_HOST:YOUR_REDIS_PORT
RAZORPAY_KEY_ID=rzp_test_YOUR_KEY_ID
RAZORPAY_KEY_SECRET=YOUR_KEY_SECRET
```

Replace every `YOUR_...` with your actual values from Steps 5, 6, and 7.

> ⚠️ Never share this file or upload it to GitHub. It is already listed in `.gitignore`.

---

### Step 9 — Create the Logs Folder in root directory of project where manage.py is found

```bash
mkdir logs
```

---

### Step 10 — Set Up the Database Tables

```bash
python manage.py migrate
```

You'll see Django creating tables. Go to your Supabase dashboard → **Table Editor** — you'll see the `orders` and `inventory` tables created there.

---

### Step 11 — Seed Inventory Data

The system needs items in stock to test with. Run this once:

```bash
python manage.py shell
```

When the `>>>` prompt appears, paste this and press Enter:

```python
from orders.models import Inventory
Inventory.objects.get_or_create(item_name='burger', defaults={'quantity': 5})
Inventory.objects.get_or_create(item_name='pizza',  defaults={'quantity': 3})
Inventory.objects.get_or_create(item_name='pasta',  defaults={'quantity': 10})
Inventory.objects.get_or_create(item_name='cake',   defaults={'quantity': 2})
print("Done!")
exit()
```

---

### Step 12 — Create an Admin User (Optional)

```bash
python manage.py createsuperuser
```

Follow the prompts. You can then visit `http://127.0.0.1:8000/admin/` to see all orders and inventory in a visual panel.

---

### Step 13 — Run the System

You need **two terminal windows** open at the same time. Make sure both have the venv activated.

**Terminal 1 — Start Django server:**
```bash
python manage.py runserver
```

**Terminal 2 — Start Celery worker:**
```bash
# Windows:
python -m celery -A core worker --loglevel=info --pool=solo

# Mac / Linux:
celery -A core worker --loglevel=info
```

Both must keep running while you use the app.

---

### Step 14 — Open the App

Go to: **http://127.0.0.1:8000/api/**

You'll see the live order management UI.

**Test card numbers** (Razorpay test mode — no real money moves):

| Card Number | Expiry | CVV | Result |
|---|---|---|---|
| `4111 1111 1111 1111` | Any future date | Any 3 digits | ✅ Payment succeeds |
| `4000 0000 0000 0002` | Any future date | Any 3 digits | ❌ Payment fails |

---

## 📡 API Endpoints

| Method | URL | Description |
|---|---|---|
| `GET` | `/api/` | Live web UI |
| `POST` | `/api/orders/` | Create order (no payment) |
| `GET` | `/api/orders/list/` | List all orders |
| `GET` | `/api/orders/list/?status=pending` | Filter orders by status |
| `GET` | `/api/orders/<uuid>/` | Get one order by ID |
| `POST` | `/api/orders/<uuid>/cancel/` | Cancel an order |
| `POST` | `/api/orders/razorpay/create/` | Create order with Razorpay |
| `POST` | `/api/orders/razorpay/verify/` | Verify payment + queue processing |
| `GET` | `/api/inventory/` | Current stock levels |
| `GET` | `/admin/` | Django admin panel |

---

## ⚙️ Order States

```
PENDING ──► PROCESSING ──► COMPLETED
               │
               └──────────► FAILED      (all retries exhausted)

PENDING ──────────────────► CANCELLED   (user cancelled)
PROCESSING ───────────────► CANCELLED   (user cancelled)
```

---

## 🔑 Key Design Decisions

| Decision | Why |
|---|---|
| Celery async processing | Client should never wait for slow payment/inventory steps |
| Retry counts stored in PostgreSQL | Celery's internal counter is lost on worker crash — DB survives |
| `SELECT FOR UPDATE` for inventory | Python locks don't work across processes — only DB locks do |
| Header-based idempotency key | Client controls the key, reuses on retries, DB enforces uniqueness |
| `CELERY_ACKS_LATE = True` | Task stays in Redis until done — re-delivered if worker crashes |
| Step checkpointing | Each step saves result before moving on — crash recovery without re-running |

---

## 📁 Project Structure

```
order_system/
├── core/                        # Django project config
│   ├── settings.py              # DB, Celery, Razorpay, Logging config
│   ├── urls.py                  # Top-level URL routing
│   ├── celery.py                # Celery app setup
│   └── __init__.py              # Auto-starts Celery with Django
│
├── orders/                      # The orders app
│   ├── models.py                # Order + Inventory models
│   ├── serializers.py           # Request validation + JSON conversion
│   ├── views.py                 # API endpoint handlers
│   ├── urls.py                  # URL routes
│   ├── tasks.py                 # Celery task — payment + inventory + retries
│   ├── logger.py                # Structured JSON logging helpers
│   ├── admin.py                 # Django admin config
│   └── templates/orders/
│       └── index.html           # Live web UI
│
├── logs/                        # JSON log files (gitignored)
├── .env                         # Your secrets (never commit this)
├── .gitignore
├── requirements.txt
├── DESIGN.md                    # System design document
└── manage.py
```

---

## 🧪 Test the Concurrency Feature

To prove that only 5 out of 10 simultaneous orders succeed when only 5 burgers are in stock:

**Windows PowerShell:**
```powershell
1..10 | ForEach-Object -Parallel {
    $key = "concurrent-test-" + $_
    Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/orders/" `
      -Method POST `
      -Headers @{"Content-Type"="application/json"; "Idempotency-Key"=$key} `
      -Body '{"items": [{"name": "burger", "quantity": 1, "price": 100}]}' `
      -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Content
} -ThrottleLimit 10
```

Expected: 5 orders → `completed` ✅ · 5 orders → `failed` (insufficient inventory) ❌

---

## 🔧 Troubleshooting

**`ModuleNotFoundError`**
→ Your venv is not active. Run `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)

**Connection timeout to Supabase**
→ You're using port 5432 (direct). Use the pooler URL with port **6543**

**Celery cannot connect to broker**
→ Check `CELERY_BROKER_URL` in `.env`. Verify Redis host, port, and password are correct

**`RAZORPAY_KEY_ID` not found**
→ Verify `.env` has the keys. Test: `python manage.py shell` → `from django.conf import settings; print(settings.RAZORPAY_KEY_ID)`

**Payment popup doesn't open**
→ Check browser console for errors. Make sure Razorpay **Test Mode** is ON in dashboard

**`psql` not found error**
→ This is fine — it's just a missing CLI tool. Your Python connection via psycopg2 works fine

---

## 📄 Documentation

See [`DESIGN.md`](./DESIGN.md) for the full system design document covering architecture, state transitions, retry strategy, concurrency approach, trade-offs, and known limitations.

---

## 📋 Assumptions

- All prices are in Indian Rupees (INR) — Razorpay is configured for INR
- Inventory items must be pre-seeded (Step 11 above)
- Single-region deployment — no cross-region consistency requirements
- Authentication and user management are out of scope for this submission
- The UI is for testing only, not a production frontend
