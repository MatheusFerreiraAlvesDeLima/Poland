Based on the provided code and configuration files, here's a comprehensive setup guide and explanation of the system:

🔧 Environment Setup & Configuration
Environment Variables (.env):

ini
# Database
DB_HOST=localhost
DB_NAME=meu_banco
DB_USER=postgres
DB_PASSWORD=020404Ma
DB_PORT=5432

# Email (Gmail example)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password  # Use App Password
MAIL_DEFAULT_SENDER=your_email@gmail.com
MAIL_SENDER_NAME="Ayist Group"

# Security
SECRET_KEY=your_secret_key
ENCRYPTION_KEY=your_fernet_key  # Generate via: Fernet.generate_key()

# Stripe
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PUBLIC_KEY=your_stripe_public_key
STRIPE_WEBHOOK_SECRET=your_webhook_secret

# Gemini AI
GOOGLE_API_KEY=your_google_api_key

# App Config
APP_ENV=development
APP_DEBUG=True
APP_PORT=5000
Generate Encryption Key:

python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
📦 Critical Dependencies
Ensure these key packages are installed:

bash
pip install flask flask-mail stripe python-dotenv psycopg2-binary 
google-generativeai cryptography requests
🚀 Running the Application
bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

pip install -r requirements.txt
python app.py
🗄️ Database Initialization
Create PostgreSQL database from schema.sql

Run the init_db() function on first launch

🔄 Key Workflows
User Registration:

Email verification with token expiration

Password hashing with werkzeug.security

Company creation with Stripe customer

Subscription Flow:

Stripe Checkout integration

Webhook handling for payment events

Plan enforcement (user/project limits)

Financial Tracking:

Project-based income/expense tracking

Multi-currency support with exchange rates

Unified transaction views

Security Features:

Fernet encryption for sensitive data

Password complexity enforcement

Session management with expiration

Role-based access control

⚠️ Critical Configuration Notes
Email Setup:

Must enable "Less secure apps" in Gmail or use App Passwords

Test email functionality with send_verification_email()

Stripe Integration:

Create products/prices in Stripe Dashboard

Configure webhook endpoint with signing secret

Test webhooks using Stripe CLI

Encryption:

ENCRYPTION_KEY must be 32-byte URL-safe base64

Used for Stripe customer IDs and sensitive data

Gemini AI:

Requires Google API key with Generative AI access

Used for tender analysis feature

🔍 Debugging Tips
Log Location: logs/app.log

Common Issues:

Email not sending: Check TLS/SSL settings

Stripe errors: Verify price IDs and customer creation

DB connection: Validate PostgreSQL credentials

Encryption: Test encrypt/decrypt cycle at startup

🌐 Production Deployment
Recommended Stack:

Web Server: Gunicorn + Nginx

Process Manager: systemd

Database: Managed PostgreSQL (AWS RDS, etc.)

Production .env Changes:

ini
APP_ENV=production
APP_DEBUG=False
MAIL_USE_TLS=True
SESSION_COOKIE_SECURE=True
📋 Key Features Explained
Multi-Tenancy:

Companies as separate tenants

Plan-based resource allocation

Per-company data isolation

Financial Features:

Diagram
Code





Subscription Management:

Stripe subscription lifecycle

Plan upgrades/downgrades

Payment failure handling

Security Layers:

Password hashing (PBKDF2)

Encrypted database fields

Session validation

CSRF protection