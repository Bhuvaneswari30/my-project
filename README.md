# Shopora — Flask E-commerce Demo

Shopora is a complete local e-commerce application built with Python, Flask, SQLite, SQLAlchemy, server-rendered HTML, CSS, and vanilla JavaScript. It has no paid services or API keys.

## Windows 10 setup

```powershell
cd ecommerce_project
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py app.py
```

Open http://127.0.0.1:5000

The SQLite database is created automatically on first run and is seeded with products and accounts:

- Admin: `admin@shopora.local` / `Admin123!`
- Demo customer: `demo@shopora.local` / `Demo123!`

Change these credentials before using the app beyond local testing. Password reset is intentionally local-only: submitting an email for an existing account displays a one-time reset link on the page instead of sending email. The checkout payment methods are Cash on Delivery and a mock online payment flow, ready to be replaced by Stripe or Razorpay.

## Folder structure

```text
ecommerce_project/
├── app.py
├── requirements.txt
├── README.md
├── shopora.db                 # created at runtime
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── products.html
│   ├── product_detail.html
│   ├── auth.html
│   ├── cart.html
│   ├── checkout.html
│   ├── wishlist.html
│   ├── profile.html
│   ├── orders.html
│   ├── order_detail.html
│   ├── info.html
│   └── admin/
│       ├── dashboard.html
│       ├── products.html
│       ├── product_form.html
│       ├── users.html
│       ├── orders.html
│       └── reviews.html
└── static/
    ├── css/style.css
    └── js/app.js
```

## Notes

The app uses an application-secret generated from `SHOPORA_SECRET_KEY` when supplied, or a development fallback. For production, set a strong secret in the environment and deploy behind HTTPS.
