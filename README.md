
🎥 **Watch the project overview video:**  
[![Watch the video](https://img.youtube.com/vi/nHWjreHSEQQ/0.jpg)](https://youtu.be/nHWjreHSEQQ)



Project Setup & Configuration Guide
🔧 Environment Setup & Configuration
Environment Variables (.env)
Configure the following environment variables to get started:

ini
Copiar
Editar
# Database Configuration
DB_HOST=localhost
DB_NAME=meu_banco
DB_USER=postgres
DB_PASSWORD=020404Ma
DB_PORT=5432

# Email Configuration (Gmail example)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password  # Use Gmail App Password
MAIL_DEFAULT_SENDER=your_email@gmail.com
MAIL_SENDER_NAME="Ayist Group"

# Security Settings
SECRET_KEY=your_secret_key
ENCRYPTION_KEY=your_fernet_key  # Generate with: Fernet.generate_key()

# Stripe Payment Gateway
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PUBLIC_KEY=your_stripe_public_key
STRIPE_WEBHOOK_SECRET=your_webhook_secret

# Gemini AI Integration
GOOGLE_API_KEY=your_google_api_key

# Application Settings
APP_ENV=development
APP_DEBUG=True
APP_PORT=5000
Generating the Encryption Key
To generate a secure encryption key for ENCRYPTION_KEY, run the following Python snippet:

python
Copiar
Editar
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
📦 Dependencies
Install all required Python packages with:

bash
Copiar
Editar
pip install flask flask-mail stripe python-dotenv psycopg2-binary google-generativeai cryptography requests
Alternatively, if you have a requirements.txt, use:

bash
Copiar
Editar
pip install -r requirements.txt
🚀 Running the Application
Create and activate a virtual environment:

bash
Copiar
Editar
python -m venv .venv
# Linux / macOS
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\activate
Install dependencies (if not done yet):

bash
Copiar
Editar
pip install -r requirements.txt
Start the Flask application:

bash
Copiar
Editar
python app.py
🗄️ Database Initialization
Create your PostgreSQL database using the provided schema.sql file.

On first run, call the init_db() function to set up all necessary tables.

🔄 Key Workflows
User Registration
Email verification with expiring tokens.

Secure password hashing using werkzeug.security.

Automatic company creation tied to a Stripe customer profile.

Subscription Management
Integration with Stripe Checkout for payment.

Webhook handlers to track payment events.

Plan enforcement to limit users/projects per subscription.

Financial Tracking
Track income and expenses by project.

Support for multiple currencies with live exchange rates.

Unified view for all financial transactions.

Security Features
Data encryption using Fernet symmetric encryption.

Password complexity enforcement.

Secure session management with automatic expiration.

Role-based access control (RBAC) for user permissions.

⚠️ Critical Configuration Notes
Email Setup
Gmail accounts must have App Passwords enabled (recommended) or allow "Less secure apps".

Use the send_verification_email() utility to verify email setup.

Stripe Integration
Create products and pricing plans in the Stripe Dashboard.

Configure your webhook endpoint URL and provide the webhook signing secret.

Use the Stripe CLI to test webhook events locally.

Encryption
The ENCRYPTION_KEY must be a 32-byte URL-safe base64 key.

This key encrypts sensitive data like Stripe customer IDs in your database.

Gemini AI
Requires a valid Google API key with Generative AI enabled.

Used for features like tender analysis and AI-powered insights.

🔍 Debugging Tips
Log files: Check logs/app.log for runtime errors and debugging information.

Email issues: Verify TLS/SSL configuration and credentials.

Stripe errors: Double-check product and price IDs, and webhook configuration.

Database connection: Confirm PostgreSQL credentials and network access.

Encryption validation: Test encrypt/decrypt at startup to ensure key correctness.

🌐 Production Deployment Recommendations
Use a production-grade web server like Gunicorn behind Nginx.

Manage the app process with systemd or a similar process manager.

Use a managed PostgreSQL instance (e.g., AWS RDS).

Adjust .env for production:

ini
Copiar
Editar
APP_ENV=production
APP_DEBUG=False
MAIL_USE_TLS=True
SESSION_COOKIE_SECURE=True
Ensure HTTPS is configured on your web server for secure cookies.

📋 Key Features Overview
Multi-Tenancy
Each company acts as an isolated tenant.

Subscription plans govern user and project limits.

Data separation per company ensures security and privacy.

Financial Management
Comprehensive project-based accounting.

Multi-currency support with real-time exchange rates.

Detailed transaction histories and reporting.

Subscription Lifecycle
Full Stripe subscription lifecycle support.

Easy upgrades, downgrades, and cancellations.

Handling of payment failures with appropriate user notifications.

Security Layers
Passwords hashed with industry-standard algorithms (PBKDF2).

Sensitive data encrypted at rest with Fernet.

Sessions validated and expired properly.

CSRF protection enforced on forms and API endpoints.
