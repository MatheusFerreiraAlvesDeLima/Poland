import os
import secrets
import stripe
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
from functools import wraps
import requests
import functools
import google.generativeai as genai
import re
import logging
from logging.handlers import RotatingFileHandler
from stripe.error import StripeError
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from cryptography.fernet import Fernet
import json
import uuid

# ===== LOAD ENVIRONMENT VARIABLES =====
load_dotenv()

# ===== CRITICAL ENVIRONMENT VERIFICATION =====
# Configure basic logging for pre-initialization
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('init')

# Verify ENCRYPTION_KEY
if not os.getenv('ENCRYPTION_KEY'):
    logger.error(" CRITICAL ERROR: ENCRYPTION_KEY not defined!")
    raise ValueError("ENCRYPTION_KEY is required for secure operation")
else:
    logger.info(" Encryption key loaded successfully")
    
    # Practical encryption test
    try:
        cipher_suite = Fernet(os.getenv('ENCRYPTION_KEY'))
        
        test_data = "test_data_ayist"
        encrypted = cipher_suite.encrypt(test_data.encode()).decode()
        decrypted = cipher_suite.decrypt(encrypted.encode()).decode()
        
        if test_data == decrypted:
            logger.info(" Encryption/decryption test successful")
        else:
            logger.error(f"❌ Encryption failure! Original: '{test_data}' | Decrypted: '{decrypted}'")
            raise ValueError("Encryption process failed")
            
    except Exception as e:
        logger.error(f"❌ ERROR in encryption test: {str(e)}")
        raise

# ===== CREATE FLASK APP =====
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# ===== STRIPE CONFIGURATION =====
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe_webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
stripe_public_key = os.getenv('STRIPE_PUBLIC_KEY')

# ===== LOGGING CONFIGURATION =====
log_dir = os.getenv('LOG_DIR', 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configura o arquivo de log
log_file = os.path.join(log_dir, 'app.log')
handler = RotatingFileHandler(log_file, maxBytes=10000, backupCount=3)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
app.logger.addHandler(handler)

# ===== GEMINI CONFIGURATION =====
if os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel('gemini-pro')
    app.logger.info(" Gemini API configured successfully")
else:
    app.logger.warning("⚠️ GOOGLE_API_KEY not defined. Gemini features disabled")

def gemini_request(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        app.logger.error(f"Gemini API error: {str(e)}")
        return "There was an error processing your request."

# ===== EMAIL CONFIGURATION =====
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False') == 'True'  # Corrigido
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = (os.getenv('MAIL_SENDER_NAME', 'Ayist Group'), 
                                     os.getenv('MAIL_DEFAULT_SENDER'))
app.config['MAIL_DEBUG'] = os.getenv('FLASK_DEBUG', 'False') == 'True'
app.config['MAIL_SUPPRESS_SEND'] = os.getenv('MAIL_SUPPRESS_SEND', 'False') == 'True'

if app.config['MAIL_USE_TLS'] and app.config['MAIL_USE_SSL']:
    app.config['MAIL_USE_SSL'] = False
    app.logger.warning("MAIL_USE_SSL desativado devido a conflito com MAIL_USE_TLS")

mail = Mail(app)

# ===== ENCRYPTION FUNCTIONS =====
def encrypt_data(data):
    cipher_suite = Fernet(os.getenv('ENCRYPTION_KEY'))
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data):
    cipher_suite = Fernet(os.getenv('ENCRYPTION_KEY'))
    return cipher_suite.decrypt(encrypted_data.encode()).decode()

# Professional email sending function
def send_verification_email(email, token, name):
    """Envia e-mail de verificação com HTML profissional"""
    try:
        if not all([
            app.config['MAIL_SERVER'],
            app.config['MAIL_USERNAME'],
            app.config['MAIL_PASSWORD']
        ]):
            app.logger.error("Credenciais de e-mail incompletas!")
            return False

        verification_url = url_for('verify_email', token=token, _external=True)
        app.logger.debug(f"Preparando e-mail para: {email}")
        app.logger.debug(f"URL de verificação: {verification_url}")

        # Template HTML (mesmo do send_test_email.py)
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Verificação de E-mail</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; }}
                .header {{ text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eee; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #0046b5; }}
                .content {{ padding: 20px 0; }}
                .button {{
                    display: inline-block;
                    padding: 12px 24px;
                    background-color: #0046b5;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                .footer {{ 
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    text-align: center; 
                    color: #777;
                    font-size: 0.9rem;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">Ayist Group</div>
                </div>
                
                <div class="content">
                    <p>Olá {name},</p>
                    <p>Obrigado por se registrar em nossa plataforma! Para ativar sua conta, clique no botão abaixo:</p>
                    
                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{verification_url}" class="button">Verificar E-mail</a>
                    </p>
                    
                    <p>Se você não criou uma conta em nossa plataforma, por favor ignore este e-mail.</p>
                    
                    <p><strong>Atenção:</strong> Este link expira em 24 horas.</p>
                </div>
                
                <div class="footer">
                    © {datetime.now().year} Ayist Group. Todos os direitos reservados.
                </div>
            </div>
        </body>
        </html>
        """
        
        # Versão em texto simples
        text_body = f"""Olá {name},
        
Obrigado por se registrar na Ayist Group! Para verificar seu e-mail e ativar sua conta, clique no link abaixo:

{verification_url}

Este link expira em 24 horas.

Se você não criou esta conta, por favor ignore este e-mail.
        """
        
        msg = Message(
            'Verifique seu e-mail - Ayist Group', 
            recipients=[email],
            body=text_body,
            html=html_body
        )
        
        mail.send(msg)
        
        app.logger.info(f"✅ E-mail de verificação enviado para {email}")
        return True
        
    except Exception as e:
        app.logger.error(f"❌ ERRO ao enviar e-mail de verificação: {str(e)}", exc_info=True)
        
        app.logger.debug(f"Configuração de e-mail: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
        app.logger.debug(f"Usando TLS: {app.config['MAIL_USE_TLS']}, SSL: {app.config['MAIL_USE_SSL']}")
        app.logger.debug(f"Autenticação: {app.config['MAIL_USERNAME']}")
        
        return False

# Function to send password reset email
def send_reset_email(email, token, name):
    """Send password reset email"""
    try:
        reset_url = url_for('reset_password', token=token, _external=True)
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Password Reset</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; }}
                .header {{ text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eee; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #0046b5; }}
                .content {{ padding: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #0046b5; 
                          color: white; text-decoration: none; border-radius: 4px; font-weight: bold; }}
                .footer {{ padding-top: 20px; border-top: 1px solid #eee; text-align: center; 
                         color: #777; font-size: 0.9rem; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">Ayist Group</div>
                </div>
                
                <div class="content">
                    <p>Hello {name},</p>
                    <p>We received a request to reset your password. Click the button below to continue:</p>
                    
                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" class="button">Reset Password</a>
                    </p>
                    
                    <p>If you didn't request this reset, please ignore this email.</p>
                    
                    <p><strong>Note:</strong> This link expires in 1 hour.</p>
                    <p>If the button doesn't work, copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background-color: #f5f5f5; padding: 10px; border-radius: 4px;">
                        {reset_url}
                    </p>
                </div>
                
                <div class="footer">
                    © {datetime.now().year} Ayist Group. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message('Password Reset - Ayist Group', 
                      recipients=[email])
        msg.html = html_body
        
        mail.send(msg)
        app.logger.info(f"Password reset email sent to {email}")
        return True
    except Exception as e:
        app.logger.error(f"Error sending reset email: {str(e)}")
        return False

# Function to send payment failure email
def send_payment_failed_email(email, name, invoice_url):
    """Send payment failure notification email"""
    try:
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Payment Failed</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; }}
                .header {{ text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eee; }}
                .logo {{ font-size: 24px; font-weight: bold; color: #0046b5; }}
                .content {{ padding: 20px 0; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #d9534f; 
                          color: white; text-decoration: none; border-radius: 4px; font-weight: bold; }}
                .footer {{ padding-top: 20px; border-top: 1px solid #eee; text-align: center; 
                         color: #777; font-size: 0.9rem; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">Ayist Group</div>
                </div>
                
                <div class="content">
                    <p>Hello {name},</p>
                    <p>Your subscription payment failed. Please update your payment information.</p>
                    
                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{invoice_url}" class="button">Update Payment</a>
                    </p>
                    
                    <p>If you don't update, your access may be suspended.</p>
                </div>
                
                <div class="footer">
                    © {datetime.now().year} Ayist Group. All rights reserved.
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message('Payment Failed - Ayist Group', 
                      recipients=[email])
        msg.html = html_body
        mail.send(msg)
        app.logger.info(f"Payment failure email sent to {email}")
        return True
    except Exception as e:
        app.logger.error(f"Error sending payment failure email: {str(e)}")
        return False

# Exchange rate cache
exchange_rate_cache = {}

@functools.lru_cache(maxsize=32)
def get_exchange_rate_cached(from_currency, to_currency='PLN'):
    """Get exchange rate with cache to reduce API calls"""
    cache_key = f"{from_currency}_{to_currency}"
    
    if cache_key in exchange_rate_cache:
        cached_time, rate = exchange_rate_cache[cache_key]
        if datetime.now() - cached_time < timedelta(days=1):
            app.logger.info(f"Using cached exchange rate for {cache_key}")
            return rate
    
    try:
        if from_currency == to_currency:
            rate = 1.0
        else:
            app.logger.info(f"Fetching new exchange rate for {cache_key}")
            response = requests.get(
                f'https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}', 
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            rate = data['rates'][to_currency]
        
        exchange_rate_cache[cache_key] = (datetime.now(), rate)
        return rate
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching exchange rate: {str(e)}")
        if cache_key in exchange_rate_cache:
            return exchange_rate_cache[cache_key][1]
        return 1.0  # Safe fallback

def convert_to_pln(amount, currency):
    """Convert any value to PLN using exchange rate"""
    try:
        return float(amount) * get_exchange_rate_cached(currency)
    except Exception as e:
        app.logger.error(f"Currency conversion error: {str(e)}")
        return float(amount)  # Fallback without conversion

# CNPJ validation
def validate_cnpj(cnpj):
    """Validate Brazilian CNPJ"""
    cnpj = ''.join(filter(str.isdigit, cnpj))
    
    if len(cnpj) != 14:
        return False
        
    # Verify check digits
    def calculate_digit(cnpj, index):
        weight = [5,4,3,2,9,8,7,6,5,4,3,2] if index == 0 else [6,5,4,3,2,9,8,7,6,5,4,3,2]
        total = 0
        for i in range(len(weight)):
            total += int(cnpj[i]) * weight[i]
        digit = 11 - (total % 11)
        return digit if digit < 10 else 0
        
    # Verify first digit
    if int(cnpj[12]) != calculate_digit(cnpj, 0):
        return False
        
    # Verify second digit
    if int(cnpj[13]) != calculate_digit(cnpj, 1):
        return False
        
    return True

# PostgreSQL database connection
def get_db_connection():
    """Establish connection to PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', 5432)
        )
        app.logger.info("Database connection established successfully")
        return conn
    except Exception as e:
        app.logger.error(f"Error connecting to database: {str(e)}")
        raise

# Authentication decorators
def login_required(f):
    """Decorator to verify user is logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to verify user is admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('login'))
        
        if not session.get('is_admin', False):
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

# Password validation
def is_password_valid(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    return True, ""
    

# Company limit checks
def check_company_limits(company_id, resource):
    """Check if company can add new resource based on plan"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get company plan
        cur.execute("""
            SELECT p.features 
            FROM companies c
            JOIN plans p ON c.plan_id = p.id
            WHERE c.id = %s
        """, (company_id,))
        plan = cur.fetchone()
        
        if not plan or not plan[0]:
            return False, "Plan not found"
        
        features = json.loads(plan[0])
        
        # Verify specific resource
        if resource == 'project':
            cur.execute("SELECT COUNT(*) FROM projects WHERE company_id = %s", (company_id,))
            current_count = cur.fetchone()[0]
            max_projects = features.get('max_projects', 0)
            if max_projects == 'unlimited':
                return True, ""
            if current_count >= int(max_projects):
                return False, f"Project limit ({max_projects}) exceeded. Upgrade your plan."
        
        elif resource == 'user':
            cur.execute("SELECT COUNT(*) FROM users WHERE company_id = %s", (company_id,))
            current_count = cur.fetchone()[0]
            max_users = features.get('max_users', 0)
            if max_users == 'unlimited':
                return True, ""
            if current_count >= int(max_users):
                return False, f"User limit ({max_users}) exceeded. Upgrade your plan."
        
        # Add other resources as needed
        
        return True, ""
    except Exception as e:
        app.logger.error(f"Error checking limits: {str(e)}")
        return False, "Internal error"
    finally:
        cur.close()
        conn.close()

# Function to log audit events
def log_audit_event(user_id, action, details):
    """Log audit event in database"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO audit_log (user_id, action, details)
            VALUES (%s, %s, %s)
        """, (user_id, action, json.dumps(details)))
        conn.commit()
    except Exception as e:
        app.logger.error(f"Error logging audit event: {str(e)}")
    finally:
        conn.close()

# Function to check user limit
def check_user_limit(company_id):
    """Check if company can add more users"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM users WHERE company_id = %s", (company_id,))
        current_users = cur.fetchone()[0]
        
        cur.execute("""
            SELECT features->>'max_users' 
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.id
            WHERE s.company_id = %s
        """, (company_id,))
        max_users = cur.fetchone()[0]
        
        if max_users != 'unlimited' and current_users >= int(max_users):
            return False
        return True
    except Exception as e:
        app.logger.error(f"Error checking user limit: {str(e)}")
        return False
    finally:
        cur.close()
        conn.close()

# Public plans route
@app.route('/plans-public')
def public_plans():
    """Public plans page for registration"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, description, price, features FROM plans WHERE is_active = TRUE")
        plans = cur.fetchall()
        
        # Debug log
        app.logger.info(f"Plans found: {len(plans)}")
        
        return render_template('plans_public.html', plans=plans)
    except Exception as e:
        app.logger.error(f"Error loading public plans: {str(e)}", exc_info=True)
        flash('Error loading plans. Please try again later.', 'danger')
        return redirect(url_for('home'))
    finally:
        cur.close()
        conn.close()



@app.route('/checkout/<int:plan_id>')
@login_required
def checkout(plan_id):
    """Redireciona para o Stripe Checkout com o plano selecionado"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Buscar plano e verificar existência
        cur.execute("""
            SELECT id, stripe_price_id 
            FROM plans 
            WHERE id = %s AND is_active = TRUE
        """, (plan_id,))
        plan = cur.fetchone()
        
        if not plan:
            flash('Plano não encontrado ou inativo', 'danger')
            return redirect(url_for('public_plans'))
        
        stripe_price_id = result[0]

        # Buscar stripe_customer_id da empresa
        cur.execute("SELECT stripe_customer_id FROM companies WHERE id = %s", (session['company_id'],))
        company_result = cur.fetchone()
        if not company_result or not company_result[0]:
            flash('Empresa sem cliente Stripe', 'danger')
            return redirect(url_for('dashboard'))
        
        # Decriptografar customer ID
        stripe_customer_id = decrypt_data(company_result[0])

        # Criar sessão do Stripe
        session_stripe = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': stripe_price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('subscription_success', _external=True),
            cancel_url=url_for('public_plans', _external=True),
        )

        return redirect(session_stripe.url, code=303)

    except Exception as e:
        app.logger.error(f"Erro ao criar sessão de checkout: {str(e)}")
        flash('Erro ao redirecionar para o pagamento.', 'danger')
        return redirect(url_for('public_plans'))
    finally:
        cur.close()
        conn.close()
# Registration route

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Coletar dados do formulário CORRETAMENTE
            company_name = request.form.get('company_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            country = request.form.get('country', '').strip()
            industry = request.form.get('industry', '').strip()
            full_name = request.form.get('full_name', '').strip()  # Nome completo
            
            # VALIDAÇÃO REVISTA
            if not all([company_name, email, password, confirm_password, country, industry, full_name]):
                flash('All fields are required', 'danger')
                return render_template('register.html')
            
            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return render_template('register.html')
            
            # Validação de força de senha (adicionar esta função se não existir)
            is_valid, error_msg = is_password_valid(password)
            if not is_valid:
                flash(error_msg, 'danger')
                return render_template('register.html')
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Verificar email existente
            cur.execute("SELECT id FROM companies WHERE email = %s", (email,))
            if cur.fetchone():
                flash('This email is already registered', 'danger')
                return render_template('register.html')
            
            # Inserir empresa
            cur.execute(
                "INSERT INTO companies (name, email, country, industry, date_registered) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (company_name, email, country, industry, datetime.now())
            )
            company_id = cur.fetchone()[0]
            
            # Dividir nome completo (primeiro nome e sobrenome)
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Criar token de verificação
            verification_token = secrets.token_urlsafe(32)
            verification_token_expiry = datetime.now() + timedelta(hours=24)
            hashed_password = generate_password_hash(password)
            
            # Inserir usuário admin
            cur.execute(
                "INSERT INTO users (first_name, last_name, email, password, "
                "company_id, is_admin, verification_token, verification_token_expiry) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (first_name, last_name, email, hashed_password, company_id, True, verification_token, verification_token_expiry)
            )
            
            # COMMIT ESSENCIAL
            conn.commit()
            
            # Armazenar dados para possível reenvio
            session['pending_email'] = email
            session['pending_token'] = verification_token
            session['pending_name'] = first_name
            
            # Enviar email de verificação
            if send_verification_email(email, verification_token, first_name):
                flash('Verification email sent! Please check your inbox.', 'success')
            else:
                flash('Failed to send verification email. Please contact support.', 'warning')
            
            return redirect(url_for('verify_email_waiting'))
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Registration error: {str(e)}")
            flash(f'Registration error: {str(e)}', 'danger')
            return render_template('register.html')
        finally:
            if 'cur' in locals(): cur.close()
            if 'conn' in locals(): conn.close()
    
    # GET: Mostrar formulário
    return render_template('register.html')


@app.route('/verify-email-waiting')
def verify_email_waiting():
    """Email verification waiting page"""
    return render_template('verify_email_waiting.html')

# Rota para reenviar verificação
@app.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email"""
    try:
        # Tentar usar dados da sessão primeiro
        email = session.get('pending_email')
        token = session.get('pending_token')
        name = session.get('pending_name')
        
        # Se não estiver na sessão, verificar no banco de dados
        if not email or not token:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT email, verification_token, first_name
                FROM users
                WHERE email = %s AND email_verified = FALSE
            """, (session.get('user_email'),))
            user_data = cur.fetchone()
            
            if user_data:
                email, token, name = user_data
            else:
                flash('No pending verification found', 'danger')
                return redirect(url_for('verify_email_waiting'))
        
        # Tentar reenviar
        if send_verification_email(email, token, name):
            flash('New verification email sent successfully!', 'success')
        else:
            flash('Failed to resend email. Please try again later.', 'danger')
        
        return redirect(url_for('verify_email_waiting'))
    
    except Exception as e:
        app.logger.error(f"Error resending verification: {str(e)}")
        flash('Error resending verification email', 'danger')
        return redirect(url_for('verify_email_waiting'))

# API endpoint for company registration
@app.route('/api/register-company', methods=['POST'])
def api_register_company():
    """Endpoint for company registration via API"""
    try:
        app.logger.info("Receiving company registration request via API")
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        company_data = data.get('company', {})
        admin_data = data.get('admin', {})
        
        # Validate required data
        required_company = ['name', 'email', 'country', 'industry', 'cnpj']
        required_admin = ['name', 'email', 'password']
        
        if not all(key in company_data for key in required_company) or \
           not all(key in admin_data for key in required_admin):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Validate CNPJ for Brazilian companies
        if company_data['country'].upper() == 'BR' and not validate_cnpj(company_data['cnpj']):
            return jsonify({'error': 'Invalid CNPJ'}), 400
        
        # Split admin name
        name_parts = admin_data['name'].split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Validate password
        is_valid, error_msg = is_password_valid(admin_data['password'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400
        
        # Connect to database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if email exists
        cur.execute("SELECT id FROM companies WHERE email = %s", (company_data['email'],))
        if cur.fetchone():
            return jsonify({'error': 'Email already registered'}), 409
        
        # Insert company
        cur.execute(
            "INSERT INTO companies (name, email, country, industry, date_registered, is_active, cnpj) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                company_data['name'], 
                company_data['email'], 
                company_data['country'], 
                company_data['industry'],
                datetime.now(),
                False,
                company_data.get('cnpj', '')
            )
        )
        company_id = cur.fetchone()[0]
        
        # Create Stripe customer
        try:
            customer = stripe.Customer.create(
                email=company_data['email'],
                name=company_data['name'],
                metadata={
                    'company_id': company_id,
                    'country': company_data['country'],
                    'industry': company_data['industry']
                }
            )
            # Encrypt and store customer ID
            encrypted_customer_id = encrypt_data(customer.id)
            cur.execute(
                "UPDATE companies SET stripe_customer_id = %s WHERE id = %s",
                (encrypted_customer_id, company_id)
            )
            app.logger.info(f"Stripe customer created and encrypted: {customer.id}")
        except stripe.error.StripeError as e:
            app.logger.error(f"Error creating Stripe customer: {str(e)}")
            # Don't fail registration, just log error
        
        # Insert admin user
        verification_token = secrets.token_urlsafe(32)
        hashed_password = generate_password_hash(admin_data['password'])
        verification_token_expiry = datetime.now() + timedelta(hours=24)
        
        cur.execute(
            "INSERT INTO users (first_name, last_name, email, password, "
            "company_id, is_admin, email_verified, verification_token, verification_token_expiry) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                first_name, 
                last_name, 
                admin_data['email'], 
                hashed_password, 
                company_id, 
                True,
                False,
                verification_token,
                verification_token_expiry
            )
        )
        admin_id = cur.fetchone()[0]
        
        conn.commit()
        
        # Send verification email
        send_verification_email(admin_data['email'], verification_token, first_name)
        
        return jsonify({
            'company_id': company_id,
            'admin_id': admin_id,
            'stripe_customer_id': customer.id,
            'verification_token': verification_token
        }), 201
        
    except Exception as e:
        app.logger.error(f"API registration error: {str(e)}", exc_info=True)
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# Endpoint for company status
@app.route('/api/companies/<int:company_id>/status', methods=['GET'])
def api_company_status(company_id):
    """Endpoint to check company status"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Consulta melhorada com ordenação e limite
        cur.execute("""
            SELECT 
                c.id AS project_id,
                c.name,
                c.description,
                c.start_date,
                c.end_date,
                COALESCE(SUM(i.amount), 0) AS income,
                COALESCE(SUM(e.amount), 0) AS expenses,
                (COALESCE(SUM(i.amount), 0) - COALESCE(SUM(e.amount), 0)) AS profit,
                -- Task data for completion calculation
                (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) AS total_tasks,
                (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'Completed') AS completed_tasks
            FROM projects p
            LEFT JOIN income i ON p.id = i.project_id
            LEFT JOIN expenses e ON p.id = e.project_id
            WHERE p.company_id = %s
            GROUP BY p.id
        """, (company_id,))
        
        projects = []
        current_date = datetime.now().date()
        for row in cur.fetchall():
            # Calculate status based on dates
            status = "Not Started"
            if row[4]:  # end_date
                if current_date > row[4]:
                    status = "Completed"
                elif row[3] and current_date >= row[3]:  # start_date
                    status = "In Progress"
            elif row[3] and current_date >= row[3]:
                status = "In Progress"
            
            # Calculate completion percentage
            total_tasks = row[8] or 0
            completed_tasks = row[9] or 0
            completion = 0
            if total_tasks > 0:
                completion = int((completed_tasks / total_tasks) * 100)
            
            projects.append({
                'project_id': row[0],
                'name': row[1],
                'description': row[2],
                'start_date': row[3].strftime('%Y-%m-%d') if row[3] else None,
                'end_date': row[4].strftime('%Y-%m-%d') if row[4] else None,
                'income': float(row[5]),
                'expenses': float(row[6]),
                'profit': float(row[7]),
                'status': status,
                'completion': completion
            })
        
        return jsonify(projects)
        
    except Exception as e:
        app.logger.error(f"Error fetching dashboard data: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
        
@app.route('/verify-email/<token>')
def verify_email(token):
    """Route for email verification"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, company_id FROM users WHERE verification_token = %s "
            "AND verification_token_expiry > %s",
            (token, datetime.now())
        )
        user = cur.fetchone()
        
        if user:
            # Update user as verified
            cur.execute(
                "UPDATE users SET email_verified = TRUE, "
                "verification_token = NULL, verification_token_expiry = NULL "
                "WHERE id = %s", (user[0],)
            )
            
            # Don't activate company yet - wait for plan selection
            conn.commit()
            flash('Email verified successfully! You can now log in.', 'success')
            # FLUXO CORRIGIDO: Redireciona para login após verificação
            return redirect(url_for('login'))
        else:
            flash('Invalid or expired token', 'danger')
            # FLUXO CORRIGIDO: Redireciona para registro se token inválido
            return redirect(url_for('register'))
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Email verification error: {str(e)}")
        flash('Verification error', 'danger')
        return redirect(url_for('register'))
    finally:
        conn.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route"""
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT u.id, u.password, u.company_id, u.email_verified, u.is_admin, 
                       c.is_active, c.stripe_customer_id, u.first_name
                FROM users u
                JOIN companies c ON u.company_id = c.id
                WHERE u.email = %s
            """, (email,))
            user = cur.fetchone()
            
            if user and check_password_hash(user[1], password):
                if not user[3]:  # email_verified
                    # FLUXO CORRIGIDO: Redireciona para tela de espera se não verificado
                    return redirect(url_for('verify_email_waiting'))
                else:
                    # Set session
                    session['user_id'] = user[0]
                    session['company_id'] = user[2]
                    session['is_admin'] = user[4]
                    session['user_email'] = email
                    session['user_name'] = user[7]
                    
                    # Verify if company has active plan
                    if not user[5]:  # is_active
                        return redirect(url_for('plans'))  # Redirect to plan selection
                    
                    # Update last login
                    cur.execute(
                        "UPDATE users SET last_login = %s WHERE id = %s",
                        (datetime.now(), user[0]))
                    conn.commit()
                    
                    app.logger.info(f"User {email} logged in successfully")
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
            else:
                app.logger.warning(f"Failed login attempt for {email}")
                flash('Invalid email or password', 'danger')
        except Exception as e:
            app.logger.error(f"Login error: {str(e)}")
            flash('Login error', 'danger')
        finally:
            conn.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout route"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

# Password recovery routes
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Route to request password reset"""
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, first_name FROM users WHERE email = %s AND email_verified = TRUE",
                (email,)
            )
            user = cur.fetchone()
            
            if user:
                reset_token = secrets.token_urlsafe(32)
                reset_expiry = datetime.now() + timedelta(hours=1)
                
                cur.execute(
                    "UPDATE users SET reset_token = %s, "
                    "reset_token_expiry = %s WHERE id = %s",
                    (reset_token, reset_expiry, user[0])
                )
                conn.commit()
                
                send_reset_email(email, reset_token, user[1])
                flash('Reset link sent to your email', 'success')
            else:
                flash('Email not found or not verified', 'danger')
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error processing password reset: {str(e)}")
            flash('Error processing request', 'danger')
        finally:
            conn.close()
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Route to reset password"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM users WHERE reset_token = %s "
            "AND reset_token_expiry > %s",
            (token, datetime.now())
        )
        user = cur.fetchone()
        
        if not user:
            flash('Invalid or expired token', 'danger')
            return redirect(url_for('forgot_password'))
        
        if request.method == 'POST':
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            
            # Password validation
            is_valid, error_msg = is_password_valid(new_password)
            if not is_valid:
                flash(error_msg, 'danger')
                return redirect(url_for('reset_password', token=token))
            
            if new_password != confirm_password:
                flash('Passwords do not match', 'danger')
                return redirect(url_for('reset_password', token=token))
            else:
                hashed_password = generate_password_hash(new_password)
                cur.execute(
                    "UPDATE users SET password = %s, reset_token = NULL, "
                    "reset_token_expiry = NULL WHERE id = %s",
                    (hashed_password, user[0])
                )
                conn.commit()
                flash('Password updated successfully', 'success')
                return redirect(url_for('login'))
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error resetting password: {str(e)}")
        flash('Error resetting password', 'danger')
    finally:
        conn.close()
    
    return render_template('reset_password.html', token=token)

# Main routes
@app.route('/')
def home():
    """Home page"""
    return render_template('home.html')

# Endpoint for dashboard data
@app.route('/api/project-dashboard-data')
@login_required
def project_dashboard_data():
    """Endpoint for dashboard data"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Fetch company projects with financial data
        cur.execute('''
            SELECT 
                p.id AS project_id,
                p.name,
                p.description,
                p.start_date,
                p.end_date,
                COALESCE(SUM(i.amount), 0) AS income,
                COALESCE(SUM(e.amount), 0) AS expenses,
                (COALESCE(SUM(i.amount), 0) - COALESCE(SUM(e.amount), 0)) AS profit,
                -- Task data for completion calculation
                (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) AS total_tasks,
                (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'Completed') AS completed_tasks
            FROM projects p
            LEFT JOIN income i ON p.id = i.project_id
            LEFT JOIN expenses e ON p.id = e.project_id
            WHERE p.company_id = %s
            GROUP BY p.id
        ''', (session['company_id'],))
        
        projects = []
        current_date = datetime.now().date()
        for row in cur.fetchall():
            # Calculate status based on dates
            status = "Not Started"
            if row[4]:  # end_date
                if current_date > row[4]:
                    status = "Completed"
                elif row[3] and current_date >= row[3]:  # start_date
                    status = "In Progress"
            elif row[3] and current_date >= row[3]:
                status = "In Progress"
            
            # Calculate completion percentage
            total_tasks = row[8] or 0
            completed_tasks = row[9] or 0
            completion = 0
            if total_tasks > 0:
                completion = int((completed_tasks / total_tasks) * 100)
            
            projects.append({
                'project_id': row[0],
                'name': row[1],
                'description': row[2],
                'start_date': row[3].strftime('%Y-%m-%d') if row[3] else None,
                'end_date': row[4].strftime('%Y-%m-%d') if row[4] else None,
                'income': float(row[5]),
                'expenses': float(row[6]),
                'profit': float(row[7]),
                'status': status,
                'completion': completion
            })
        
        return jsonify(projects)
        
    except Exception as e:
        app.logger.error(f"Error fetching dashboard data: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()
        
@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard after login"""
    conn = get_db_connection()
    cur = None
    try:
        app.logger.info(f"Loading dashboard for user {session['user_id']}")
        cur = conn.cursor()
        
        # User and company data
        cur.execute("""
            SELECT u.first_name, u.last_name, u.email, u.is_admin,
                   c.name as company_name, c.email as company_email, 
                   c.country, c.industry, c.is_active,
                   s.status, s.current_period_end,
                   p.name as plan_name, p.features
            FROM users u
            JOIN companies c ON u.company_id = c.id
            LEFT JOIN subscriptions s ON c.id = s.company_id
            LEFT JOIN plans p ON s.plan_id = p.id
            WHERE u.id = %s
        """, (session['user_id'],))
        user_data = cur.fetchone()
        
        # Available plans
        cur.execute("SELECT id, name, description, price, features FROM plans WHERE is_active = TRUE")
        plans = cur.fetchall()
        
        # Company projects
        cur.execute('SELECT * FROM projects WHERE company_id = %s', (session['company_id'],))
        projects = cur.fetchall()
        
        # Prepare dashboard data
        dashboard_data = []
        total_income = 0
        total_expenses = 0
        monthly_data = {}
        upcoming_payments = []
        
        for project in projects:
            # Project income
            cur.execute('SELECT SUM(amount) as total FROM income WHERE project_id = %s', 
                       (project[0],))  # project[0] is id
            incomes = cur.fetchone()
            total_income_val = incomes[0] if incomes[0] else 0
            
            # Project expenses
            cur.execute('SELECT SUM(amount) as total FROM expenses WHERE project_id = %s', 
                       (project[0],))
            expenses = cur.fetchone()
            total_expenses_val = expenses[0] if expenses[0] else 0
            
            # Project tasks
            cur.execute('SELECT COUNT(*) as total, SUM(CASE WHEN status = \'Completed\' THEN 1 ELSE 0 END) as completed FROM tasks WHERE project_id = %s',
                        (project[0],))
            tasks = cur.fetchone()
            
            # Calculate completion percentage
            completion_percentage = 0
            if tasks[0] and tasks[0] > 0:
                completion_percentage = round((tasks[1] / tasks[0]) * 100)
            
            # Determine status
            status = "Not Started"
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            if completion_percentage == 100:
                status = "Completed"
            elif current_date >= str(project[3]):  # project[3] is start_date
                status = "In Progress"
            
            # Convert to PLN
            income_pln = float(total_income_val) * get_exchange_rate_cached('USD')
            expenses_pln = float(total_expenses_val) * get_exchange_rate_cached('USD')
            
            dashboard_data.append({
                'project_id': project[0],
                'name': project[1],
                'description': project[2],
                'start_date': project[3],
                'end_date': project[4],
                'status': status,
                'income': income_pln,
                'expenses': expenses_pln,
                'profit': income_pln - expenses_pln,
                'completion': completion_percentage
            })
            
            # Details for monthly charts
            cur.execute('SELECT * FROM income WHERE project_id = %s', (project[0],))
            incomes = cur.fetchall()
            for income in incomes:
                amount_pln = convert_to_pln(income[4], income[5])  # amount and currency
                total_income += amount_pln
                month_key = datetime.strptime(str(income[3]), '%Y-%m-%d').strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = {'income': 0, 'expenses': 0}
                monthly_data[month_key]['income'] += amount_pln
                upcoming_payments.append({
                    'type': 'income',
                    'project_name': project[1],
                    'date': income[3],
                    'amount': amount_pln,
                    'currency': 'PLN'
                })

            # Detailed expenses
            cur.execute('SELECT * FROM expenses WHERE project_id = %s', (project[0],))
            expenses = cur.fetchall()
            for expense in expenses:
                amount_pln = convert_to_pln(expense[4], expense[5])  # amount and currency
                total_expenses += amount_pln
                month_key = datetime.strptime(str(expense[3]), '%Y-%m-%d').strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = {'income': 0, 'expenses': 0}
                monthly_data[month_key]['expenses'] += amount_pln
                upcoming_payments.append({
                    'type': 'expense',
                    'project_name': project[1],
                    'date': expense[3],
                    'amount': amount_pln,
                    'currency': 'PLN'
                })

        # Format monthly data for charts
        monthly_chart_data = [
            {
                'month': k,
                'income': round(v['income'], 2),
                'expenses': round(v['expenses'], 2),
                'profit': round(v['income'] - v['expenses'], 2)
            }
            for k, v in sorted(monthly_data.items())
        ]
        
        # Sort upcoming payments by date
        upcoming_payments.sort(key=lambda x: datetime.strptime(str(x['date']), '%Y-%m-%d'), reverse=True)

        app.logger.info(f"Dashboard loaded with {len(dashboard_data)} projects")
        return render_template('dashboard.html', 
                             user=user_data, 
                             plans=plans,
                             projects=dashboard_data,
                             monthly_data=monthly_chart_data,
                             upcoming_payments=upcoming_payments,
                             total_income=round(total_income, 2),
                             total_expenses=round(total_expenses, 2),
                             profit_loss=round(total_income - total_expenses, 2))
        
    except Exception as e:
        app.logger.error(f"Dashboard error: {str(e)}", exc_info=True)
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return redirect(url_for('home'))
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# Project management routes
@app.route('/projects')
@login_required
def projects():
    """List all company projects"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT * FROM projects WHERE company_id = %s ORDER BY start_date DESC', 
                   (session['company_id'],))
        projects = cur.fetchall()
        return render_template('projects.html', projects=projects)
    except Exception as e:
        app.logger.error(f"Error listing projects: {str(e)}")
        flash('Error loading projects', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cur.close()
        conn.close()



@app.route('/project/<int:project_id>')
@login_required
def project(project_id):
    """Detailed project page"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Verify project belongs to company
        cur.execute('SELECT * FROM projects WHERE id = %s AND company_id = %s', 
                    (project_id, session['company_id']))
        project = cur.fetchone()
        
        if not project:
            flash('Project not found', 'danger')
            return redirect(url_for('projects'))
        
        # Get income and expenses
        cur.execute('SELECT * FROM income WHERE project_id = %s ORDER BY date DESC', (project_id,))
        incomes = cur.fetchall()
        
        cur.execute('SELECT * FROM expenses WHERE project_id = %s ORDER BY date DESC', (project_id,))
        expenses = cur.fetchall()
        
        # Get tasks
        cur.execute('SELECT * FROM tasks WHERE project_id = %s ORDER BY due_date', (project_id,))
        tasks = cur.fetchall()
        
        # Calculate totals
        total_income = sum(convert_to_pln(i[4], i[5]) for i in incomes)  # amount and currency
        total_expenses = sum(convert_to_pln(e[4], e[5]) for e in expenses)  # amount and currency
        
        return render_template('project.html',
                             project=project,
                             incomes=incomes,
                             expenses=expenses,
                             tasks=tasks,
                             total_income=total_income,
                             total_expenses=total_expenses,
                             profit_loss=total_income - total_expenses)
    except Exception as e:
        app.logger.error(f"Error loading project: {str(e)}")
        flash('Error loading project', 'danger')
        return redirect(url_for('projects'))
    finally:
        cur.close()
        conn.close()

@app.route('/add_project', methods=['GET', 'POST'])
@login_required
def add_project():
    """Add new project"""
    if request.method == 'POST':
        name = request.form['name'].strip()
        description = request.form['description'].strip()
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        
        if not name or not start_date or not end_date:
            flash('Name and dates are required', 'danger')
            return redirect(url_for('add_project'))
        
        # Check project limit
        allowed, error_msg = check_company_limits(session['company_id'], 'project')
        if not allowed:
            flash(error_msg, 'danger')
            return redirect(url_for('add_project'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO projects 
                (name, description, start_date, end_date, company_id)
                VALUES (%s, %s, %s, %s, %s)
            ''', (name, description, start_date, end_date, session['company_id']))
            conn.commit()
            flash('Project added successfully!', 'success')
            return redirect(url_for('projects'))
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error adding project: {str(e)}")
            flash('Error adding project', 'danger')
            return redirect(url_for('add_project'))
        finally:
            cur.close()
            conn.close()
    
    return render_template('add_project.html')

@app.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    """Delete a project"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Verify project belongs to company
        cur.execute('SELECT id FROM projects WHERE id = %s AND company_id = %s', 
                   (project_id, session['company_id']))
        if not cur.fetchone():
            flash('Project not found or access denied', 'danger')
            return redirect(url_for('projects'))
        
        cur.execute('DELETE FROM projects WHERE id = %s', (project_id,))
        conn.commit()
        flash('Project deleted successfully', 'success')
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error deleting project: {str(e)}")
        flash('Error deleting project', 'danger')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('projects'))

# Income and expense routes
@app.route('/project/<int:project_id>/add_income', methods=['GET', 'POST'])
@login_required
def add_income(project_id):
    """Add income to a project"""
    if request.method == 'POST':
        type_ = request.form['type'].strip()
        date = request.form['date']
        amount = request.form['amount']
        currency = request.form['currency']
        invoice_link = request.form.get('invoice_link', '').strip()
        description = request.form.get('description', '').strip()
        
        # Basic validations
        if not type_ or not date or not amount or not currency:
            flash('All required fields must be filled', 'danger')
            return redirect(url_for('add_income', project_id=project_id))
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Verify project belongs to company
            cur.execute('SELECT id FROM projects WHERE id = %s AND company_id = %s', 
                       (project_id, session['company_id']))
            if not cur.fetchone():
                flash('Project not found or access denied', 'danger')
                return redirect(url_for('projects'))
            
            # Generate invoice ID
            today = date.replace("-", "")
            cur.execute(
                'SELECT COUNT(*) FROM income WHERE date = %s AND project_id = %s',
                (date, project_id)
            )
            invoice_count = cur.fetchone()[0] + 1
            invoice_id = f"{today}_{project_id}_{invoice_count}"

            # Insert income
            cur.execute('''
                INSERT INTO income 
                (project_id, type, date, amount, currency, invoice_id, invoice_link, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (project_id, type_, date, amount, currency, invoice_id, invoice_link, description))
            conn.commit()
            
            flash('Income added successfully!', 'success')
            return redirect(url_for('project', project_id=project_id))
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error adding income: {str(e)}")
            flash('Error adding income', 'danger')
            return redirect(url_for('add_income', project_id=project_id))
        finally:
            cur.close()
            conn.close()
    
    return render_template('add_income.html', project_id=project_id)

@app.route('/project/<int:project_id>/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense(project_id):
    """Add expense to a project"""
    if request.method == 'POST':
        type_ = request.form['type'].strip()
        date = request.form['date']
        amount = request.form['amount']
        currency = request.form['currency']
        invoice_link = request.form.get('invoice_link', '').strip()
        description = request.form.get('description', '').strip()
        
        # Basic validations
        if not type_ or not date or not amount or not currency:
            flash('All required fields must be filled', 'danger')
            return redirect(url_for('add_expense', project_id=project_id))
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Verify project belongs to company
            cur.execute('SELECT id FROM projects WHERE id = %s AND company_id = %s', 
                       (project_id, session['company_id']))
            if not cur.fetchone():
                flash('Project not found or access denied', 'danger')
                return redirect(url_for('projects'))
            
            # Generate invoice ID
            today = date.replace("-", "")
            cur.execute(
                'SELECT COUNT(*) FROM expenses WHERE date = %s AND project_id = %s',
                (date, project_id)
            )
            invoice_count = cur.fetchone()[0] + 1
            invoice_id = f"{today}_{project_id}_{invoice_count}"

            # Insert expense
            cur.execute('''
                INSERT INTO expenses 
                (project_id, type, date, amount, currency, invoice_id, invoice_link, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (project_id, type_, date, amount, currency, invoice_id, invoice_link, description))
            conn.commit()
            
            flash('Expense added successfully!', 'success')
            return redirect(url_for('project', project_id=project_id))
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error adding expense: {str(e)}")
            flash('Error adding expense', 'danger')
            return redirect(url_for('add_expense', project_id=project_id))
        finally:
            cur.close()
            conn.close()
    
    return render_template('add_expense.html', project_id=project_id)

# General expenses routes
@app.route('/general_expenses')
@login_required
def general_expenses():
    """List expenses not linked to projects"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT * FROM general_expenses 
            WHERE company_id = %s
            ORDER BY date DESC
        ''', (session['company_id'],))
        expenses = cur.fetchall()
        
        total_expenses = sum(convert_to_pln(expense[4], expense[5]) for expense in expenses)
        
        return render_template('general_expenses.html', 
                             expenses=expenses,
                             total_expenses=total_expenses)
    except Exception as e:
        app.logger.error(f"Error loading general expenses: {str(e)}")
        flash('Error loading expenses', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cur.close()
        conn.close()

@app.route('/add_general_expense', methods=['GET', 'POST'])
@login_required
def add_general_expense():
    """Add general expense"""
    if request.method == 'POST':
        type_ = request.form['type'].strip()
        date = request.form['date']
        amount = request.form['amount']
        currency = request.form['currency']
        description = request.form.get('description', '').strip()
        
        if not type_ or not date or not amount or not currency:
            flash('All required fields must be filled', 'danger')
            return redirect(url_for('add_general_expense'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO general_expenses 
                (company_id, type, date, amount, currency, description)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (session['company_id'], type_, date, amount, currency, description))
            conn.commit()
            
            flash('General expense added successfully!', 'success')
            return redirect(url_for('general_expenses'))
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error adding general expense: {str(e)}")
            flash('Error adding expense', 'danger')
            return redirect(url_for('add_general_expense'))
        finally:
            cur.close()
            conn.close()
    
    return render_template('add_general_expense.html')

# Task routes
@app.route('/project/<int:project_id>/add_task', methods=['POST'])
@login_required
def add_task(project_id):
    """Add task to a project"""
    title = request.form['title'].strip()
    description = request.form.get('description', '').strip()
    due_date = request.form['due_date']
    assigned_user = request.form.get('assigned_user', '').strip()
    
    if not title or not due_date:
        flash('Title and due date are required', 'danger')
        return redirect(url_for('project', project_id=project_id))
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Verify project belongs to company
        cur.execute('SELECT id FROM projects WHERE id = %s AND company_id = %s', 
                   (project_id, session['company_id']))
        if not cur.fetchone():
            flash('Project not found or access denied', 'danger')
            return redirect(url_for('projects'))
        
        # Insert task
        cur.execute('''
            INSERT INTO tasks 
            (project_id, title, description, due_date, assigned_user, status)
            VALUES (%s, %s, %s, %s, %s, 'Pending')
        ''', (project_id, title, description, due_date, assigned_user))
        conn.commit()
        
        flash('Task added successfully!', 'success')
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error adding task: {str(e)}")
        flash('Error adding task', 'danger')
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('project', project_id=project_id))

@app.route('/task/<int:task_id>/update_status', methods=['POST'])
@login_required
def update_task_status(task_id):
    """Update task status"""
    new_status = request.form['status']
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Verify task belongs to company
        cur.execute('''
            SELECT t.id FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE t.id = %s AND p.company_id = %s
        ''', (task_id, session['company_id']))
        if not cur.fetchone():
            flash('Task not found or access denied', 'danger')
            return redirect(url_for('dashboard'))
        
        # Update status
        cur.execute('''
            UPDATE tasks SET status = %s 
            WHERE id = %s
        ''', (new_status, task_id))
        conn.commit()
        
        flash('Task status updated!', 'success')
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error updating task: {str(e)}")
        flash('Error updating task', 'danger')
    finally:
        cur.close()
        conn.close()
    
    # Redirect back to project
    cur = conn.cursor()
    cur.execute('SELECT project_id FROM tasks WHERE id = %s', (task_id,))
    project_id = cur.fetchone()[0]
    cur.close()
    return redirect(url_for('project', project_id=project_id))

# Reporting routes
@app.route('/reporting')
@login_required
def reporting():
    """Reporting page"""
    return render_template('reporting.html')

@app.route('/api/report-data')
@login_required
def report_data():
    """API for report data"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Income data
        cur.execute('''
            SELECT i.date, i.amount, i.currency, p.name as project_name
            FROM income i
            JOIN projects p ON i.project_id = p.id
            WHERE p.company_id = %s
            ORDER BY i.date
        ''', (session['company_id'],))
        incomes = cur.fetchall()
        
        # Project expenses data
        cur.execute('''
            SELECT e.date, e.amount, e.currency, p.name as project_name
            FROM expenses e
            JOIN projects p ON e.project_id = p.id
            WHERE p.company_id = %s
            ORDER BY e.date
        ''', (session['company_id'],))
        project_expenses = cur.fetchall()
        
        # General expenses data
        cur.execute('''
            SELECT id, 'General Expense' as project_name, type, date, 
                   amount, currency, 'general_expense' as transaction_type,
                   description, '' as invoice_link
            FROM general_expenses
            WHERE company_id = %s
            ORDER BY date DESC
        ''', (session['company_id'],))
        general_expenses = cur.fetchall()
        
        # Process data for reports
        monthly_data = {}
        yearly_data = {}
        project_data = {}
        
        # Process income
        for income in incomes:
            date = income[0]
            amount = convert_to_pln(income[1], income[2])
            project = income[3]
            
            # By month
            month_key = date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {'income': 0, 'expenses': 0, 'profit': 0}
            monthly_data[month_key]['income'] += amount
            monthly_data[month_key]['profit'] += amount
            
            # By year
            year_key = date.strftime('%Y')
            if year_key not in yearly_data:
                yearly_data[year_key] = {'income': 0, 'expenses': 0, 'profit': 0}
            yearly_data[year_key]['income'] += amount
            yearly_data[year_key]['profit'] += amount
            
            # By project
            if project not in project_data:
                project_data[project] = {'income': 0, 'expenses': 0, 'profit': 0}
            project_data[project]['income'] += amount
            project_data[project]['profit'] += amount
        
        # Process project expenses
        for expense in project_expenses:
            date = expense[0]
            amount = convert_to_pln(expense[1], expense[2])
            project = expense[3]
            
            # By month
            month_key = date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {'income': 0, 'expenses': 0, 'profit': 0}
            monthly_data[month_key]['expenses'] += amount
            monthly_data[month_key]['profit'] -= amount
            
            # By year
            year_key = date.strftime('%Y')
            if year_key not in yearly_data:
                yearly_data[year_key] = {'income': 0, 'expenses': 0, 'profit': 0}
            yearly_data[year_key]['expenses'] += amount
            yearly_data[year_key]['profit'] -= amount
            
            # By project
            if project not in project_data:
                project_data[project] = {'income': 0, 'expenses': 0, 'profit': 0}
            project_data[project]['expenses'] += amount
            project_data[project]['profit'] -= amount
        
        # Process general expenses
        for expense in general_expenses:
            date = expense[0]
            amount = convert_to_pln(expense[4], expense[5])
            
            # By month
            month_key = date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {'income': 0, 'expenses': 0, 'profit': 0}
            monthly_data[month_key]['expenses'] += amount
            monthly_data[month_key]['profit'] -= amount
            
            # By year
            year_key = date.strftime('%Y')
            if year_key not in yearly_data:
                yearly_data[year_key] = {'income': 0, 'expenses': 0, 'profit': 0}
            yearly_data[year_key]['expenses'] += amount
            yearly_data[year_key]['profit'] -= amount
        
        # Format data for response
        monthly_report = [{
            'month': k,
            'income': round(v['income'], 2),
            'expenses': round(v['expenses'], 2),
            'profit': round(v['profit'], 2)
        } for k, v in sorted(monthly_data.items())]
        
        yearly_report = [{
            'year': k,
            'income': round(v['income'], 2),
            'expenses': round(v['expenses'], 2),
            'profit': round(v['profit'], 2)
        } for k, v in sorted(yearly_data.items())]
        
        project_report = [{
            'project': k,
            'income': round(v['income'], 2),
            'expenses': round(v['expenses'], 2),
            'profit': round(v['profit'], 2)
        } for k, v in project_data.items()]
        
        return jsonify({
            'monthly': monthly_report,
            'yearly': yearly_report,
            'projects': project_report
        })
    except Exception as e:
        app.logger.error(f"Error generating reports: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

# Unified view routes
@app.route('/unified')
@login_required
def unified_view():
    """Unified view of all transactions"""
    return render_template('unified_view.html')

@app.route('/api/unified-transactions')
@login_required
def unified_transactions():
    """API for unified transactions"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        transactions = []
        
        # Income
        cur.execute('''
            SELECT i.id, p.name as project, i.type, i.date, 
                   i.amount, i.currency, 'income' as transaction_type,
                   i.description, i.invoice_link
            FROM income i
            JOIN projects p ON i.project_id = p.id
            WHERE p.company_id = %s
            ORDER BY i.date DESC
        ''', (session['company_id'],))
        for row in cur.fetchall():
            transactions.append({
                'id': row[0],
                'project': row[1],
                'type': row[2],
                'date': row[3],
                'amount': convert_to_pln(row[4], row[5]),
                'original_amount': row[4],
                'original_currency': row[5],
                'transaction_type': row[6],
                'description': row[7],
                'invoice_link': row[8]
            })
        
        # Project expenses
        cur.execute('''
            SELECT e.id, p.name as project, e.type, e.date, 
                   e.amount, e.currency, 'expense' as transaction_type,
                   e.description, e.invoice_link
            FROM expenses e
            JOIN projects p ON e.project_id = p.id
            WHERE p.company_id = %s
            ORDER BY e.date DESC
        ''', (session['company_id'],))
        for row in cur.fetchall():
            transactions.append({
                'id': row[0],
                'project': row[1],
                'type': row[2],
                'date': row[3],
                'amount': convert_to_pln(row[4], row[5]),
                'original_amount': row[4],
                'original_currency': row[5],
                'transaction_type': row[6],
                'description': row[7],
                'invoice_link': row[8]
            })
        
        # General expenses
        cur.execute('''
            SELECT id, 'General Expense' as project, type, date, 
                   amount, currency, 'general_expense' as transaction_type,
                   description, '' as invoice_link
            FROM general_expenses
            WHERE company_id = %s
            ORDER BY date DESC
        ''', (session['company_id'],))
        for row in cur.fetchall():
            transactions.append({
                'id': row[0],
                'project': row[1],
                'type': row[2],
                'date': row[3],
                'amount': convert_to_pln(row[4], row[5]),
                'original_amount': row[4],
                'original_currency': row[5],
                'transaction_type': row[6],
                'description': row[7],
                'invoice_link': row[8]
            })
        
        # Sort by date (newest first)
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify(transactions)
    except Exception as e:
        app.logger.error(f"Error fetching unified transactions: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

# User management routes
@app.route('/users')
@admin_required
def user_management():
    """Company user management"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            SELECT id, first_name, last_name, email, last_login, is_admin
            FROM users
            WHERE company_id = %s
            ORDER BY first_name
        ''', (session['company_id'],))
        users = cur.fetchall()
        
        # Get user limit from plan
        cur.execute('''
            SELECT features->>'max_users' 
            FROM companies c
            JOIN plans p ON c.plan_id = p.id
            WHERE c.id = %s
        ''', (session['company_id'],))
        max_users = cur.fetchone()[0]
        
        # Calculate user usage
        current_users = len(users)
        user_limit = int(max_users) if max_users != 'unlimited' else float('inf')
        
        return render_template('users.html', 
                             users=users, 
                             current_users=current_users,
                             max_users=user_limit)
    except Exception as e:
        app.logger.error(f"Error listing users: {str(e)}")
        flash('Error loading users', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cur.close()
        conn.close()

@app.route('/add-user', methods=['GET', 'POST'])
@admin_required
def add_user():
    """Add new user to company"""
    if request.method == 'POST':
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        is_admin = 'is_admin' in request.form
        
        # Basic validations
        if not all([first_name, email, password, confirm_password]):
            flash('All required fields must be filled', 'danger')
            return redirect(url_for('add_user'))
        
        # Validate email
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email', 'danger')
            return redirect(url_for('add_user'))
        
        # Validate password
        is_valid, error_msg = is_password_valid(password)
        if not is_valid:
            flash(error_msg, 'danger')
            return redirect(url_for('add_user'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('add_user'))
        
        # Check user limit
        allowed, error_msg = check_company_limits(session['company_id'], 'user')
        if not allowed:
            flash(error_msg, 'danger')
            return redirect(url_for('user_management'))
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Check if email already in use
            cur.execute("""
                SELECT id FROM users 
                WHERE email = %s AND company_id = %s
            """, (email, session['company_id']))
            if cur.fetchone():
                flash('This email is already registered in this company', 'danger')
                return redirect(url_for('add_user'))
            
            # Hash password
            hashed_password = generate_password_hash(password)
            
            # Insert new user
            cur.execute("""
                INSERT INTO users (
                    first_name, last_name, email, password, 
                    company_id, is_admin, email_verified
                ) VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            """, (
                first_name,
                last_name,
                email,
                hashed_password,
                session['company_id'],
                is_admin
            ))
            
            conn.commit()
            flash('User added successfully!', 'success')
            return redirect(url_for('user_management'))
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Error adding user: {str(e)}")
            flash('Error adding user', 'danger')
            return redirect(url_for('add_user'))
        finally:
            cur.close()
            conn.close()
    
    return render_template('add_user.html')

@app.route('/users/<int:user_id>/update_role', methods=['POST'])
@admin_required
def update_user_role(user_id):
    """Update user role"""
    new_role = request.form['role']
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Verify user belongs to company
        cur.execute('''
            UPDATE users SET role = %s 
            WHERE id = %s AND company_id = %s
        ''', (new_role, user_id, session['company_id']))
        
        if cur.rowcount == 0:
            flash('User not found or access denied', 'danger')
        else:
            conn.commit()
            flash('User role updated successfully', 'success')
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error updating user role: {str(e)}")
        flash('Error updating role', 'danger')
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('user_management'))

@app.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete user from company"""
    # Prevent admin from deleting themselves
    if user_id == session['user_id']:
        flash('You cannot delete yourself', 'danger')
        return redirect(url_for('user_management'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Verify user belongs to company
        cur.execute('''
            DELETE FROM users 
            WHERE id = %s AND company_id = %s
        ''', (user_id, session['company_id']))
        
        if cur.rowcount == 0:
            flash('User not found or access denied', 'danger')
        else:
            conn.commit()
            flash('User deleted successfully', 'success')
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error deleting user: {str(e)}")
        flash('Error deleting user', 'danger')
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('user_management'))

# Tender analysis routes
@app.route('/tender-analysis')
@login_required
def tender_analysis():
    """Tender analysis page"""
    return render_template('tender_analysis.html')

@app.route('/api/analyze-tender', methods=['POST'])
@login_required
def analyze_tender():
    """API for tender analysis with Gemini"""
    if request.method == 'POST':
        tender_text = request.form.get('tender_text', '').strip()
        if not tender_text:
            return jsonify({"error": "Tender text is required"}), 400
        
        try:
            prompt = f"""Analyze the following tender document and provide:
1. Summary of main requirements
2. Important deadlines
3. Evaluation criteria
4. Recommendations for proposal preparation

Document:
{tender_text}"""
            
            analysis = gemini_request(prompt)
            return jsonify({'analysis': analysis})
        except Exception as e:
            app.logger.error(f"Tender analysis error: {str(e)}")
            return jsonify({'error': 'Analysis error'}), 500
    
    return jsonify({'error': 'Invalid method'}), 405

# Invoices routes
@app.route('/invoices')
@login_required
def invoices():
    """Invoice list"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Income invoices
        cur.execute('''
            SELECT i.id, i.invoice_id, i.date, i.amount, i.currency,
                   i.invoice_link, p.name as project_name, 'income' as type
            FROM income i
            JOIN projects p ON i.project_id = p.id
            WHERE p.company_id = %s
            ORDER BY i.date DESC
        ''', (session['company_id'],))
        income_invoices = cur.fetchall()
        
        # Expense invoices
        cur.execute('''
            SELECT e.id, e.invoice_id, e.date, e.amount, e.currency,
                   e.invoice_link, p.name as project_name, 'expense' as type
            FROM expenses e
            JOIN projects p ON e.project_id = p.id
            WHERE p.company_id = %s
            ORDER BY e.date DESC
        ''', (session['company_id'],))
        expense_invoices = cur.fetchall()
        
        # Combine and sort
        all_invoices = []
        for inv in income_invoices + expense_invoices:
            all_invoices.append({
                'id': inv[0],
                'invoice_id': inv[1],
                'date': inv[2],
                'amount': convert_to_pln(inv[3], inv[4]),
                'original_amount': inv[3],
                'original_currency': inv[4],
                'invoice_link': inv[5],
                'project_name': inv[6],
                'type': inv[7]
            })
        
        all_invoices.sort(key=lambda x: x['date'], reverse=True)
        
        return render_template('invoices.html', invoices=all_invoices)
    except Exception as e:
        app.logger.error(f"Error loading invoices: {str(e)}")
        flash('Error loading invoices', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cur.close()
        conn.close()

# ============== PLANS AND SUBSCRIPTIONS ==============

@app.route('/plans')
@login_required
def plans():
    """Plan selection page"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Verify if company already has active plan
        cur.execute("SELECT is_active FROM companies WHERE id = %s", 
                   (session['company_id'],))
        company = cur.fetchone()
        
        if company and company[0]:
            flash('Your company already has an active plan', 'info')
            return redirect(url_for('dashboard'))
        
        # Fetch available plans
        cur.execute("SELECT id, name, description, price, features FROM plans WHERE is_active = TRUE")
        plans = cur.fetchall()
        return render_template('plans.html', plans=plans, stripe_public_key=stripe_public_key)
    except Exception as e:
        app.logger.error(f"Error loading plans: {str(e)}")
        flash('Error loading plans', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cur.close()
        conn.close()






@app.route('/create-checkout-session/<int:plan_id>', methods=['POST'])
@login_required
def create_checkout_session(plan_id):
    """Create checkout session for subscription"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Fetch plan data
        cur.execute("""
            SELECT id, name, price, stripe_price_id 
            FROM plans WHERE id = %s
        """, (plan_id,))
        plan = cur.fetchone()
        
        if not plan:
            return jsonify({'error': 'Plan not found'}), 404
        
        # Fetch company stripe_customer_id (decrypt)
        cur.execute("""
            SELECT stripe_customer_id 
            FROM companies 
            WHERE id = %s
        """, (session['company_id'],))
        customer = cur.fetchone()
        
        customer_id = None
        if customer and customer[0]:
            customer_id = decrypt_data(customer[0])
        
        if not customer_id:
            # Create Stripe customer if doesn't exist
            cur.execute("""
                SELECT name, email 
                FROM companies 
                WHERE id = %s
            """, (session['company_id'],))
            company = cur.fetchone()
            
            stripe_customer = stripe.Customer.create(
                email=company[1],
                name=company[0],
                metadata={'company_id': session['company_id']}
            )
            # Encrypt and store customer ID
            encrypted_customer_id = encrypt_data(stripe_customer.id)
            cur.execute("""
                UPDATE companies 
                SET stripe_customer_id = %s 
                WHERE id = %s
            """, (encrypted_customer_id, session['company_id']))
            conn.commit()
            customer_id = stripe_customer.id
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': plan[3],  # stripe_price_id
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('subscription_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('plans', _external=True),
            metadata={
                'company_id': session['company_id'],
                'plan_id': plan[0]
            }
        )
        
        return jsonify({'id': checkout_session.id})
        
    except Exception as e:
        app.logger.error(f"Error creating checkout session: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/activate_free_plan', methods=['POST'])
@login_required
def activate_free_plan():
    """Activate free plan for company"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Find free plan
        cur.execute("SELECT id FROM plans WHERE price = 0 AND is_active = TRUE LIMIT 1")
        free_plan = cur.fetchone()
        if not free_plan:
            return jsonify({'error': 'Free plan not found'}), 404
        
        # Update company with free plan
        cur.execute("""
            UPDATE companies 
            SET plan_id = %s, is_active = TRUE 
            WHERE id = %s
        """, (free_plan[0], session['company_id']))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error activating free plan: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

# Route for subscription management
@app.route('/subscriptions')
@admin_required
def subscriptions():
    """Subscription management dashboard"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get current subscription
        cur.execute("""
            SELECT s.id, p.name, s.status, s.current_period_end, 
                   s.stripe_subscription_id, p.price, s.cancel_at_period_end,
                   s.renewal_date
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.id
            WHERE s.company_id = %s
        """, (session['company_id'],))
        subscription = cur.fetchone()
        
        # Get payment history
        cur.execute("""
            SELECT id, amount, currency, payment_date, invoice_id
            FROM payments
            WHERE company_id = %s
            ORDER BY payment_date DESC
        """, (session['company_id'],))
        payments = cur.fetchall()
        
        # Get plan changes history
        cur.execute("""
            SELECT pc.change_date, p_old.name, p_new.name, p_new.price
            FROM plan_changes pc
            JOIN plans p_new ON pc.new_plan_id = p_new.id
            LEFT JOIN plans p_old ON pc.old_plan_id = p_old.id
            WHERE pc.company_id = %s
            ORDER BY pc.change_date DESC
        """, (session['company_id'],))
        changes = cur.fetchall()
        
        # Get available plans
        cur.execute("SELECT id, name, description, price, features FROM plans WHERE is_active = TRUE")
        plans = cur.fetchall()
        
        return render_template('subscriptions.html', 
                             subscription=subscription,
                             payments=payments,
                             changes=changes,
                             plans=plans)
    except Exception as e:
        app.logger.error(f"Error loading subscriptions: {str(e)}")
        flash('Error loading subscription information', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cur.close()
        conn.close()

@app.route('/change-plan', methods=['POST'])
@login_required
def change_plan():
    """Change company plan"""
    new_plan_id = request.form.get('new_plan_id')
    if not new_plan_id:
        flash('Plan not selected', 'danger')
        return redirect(url_for('subscription_management'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get current plan
        cur.execute("""
            SELECT s.stripe_subscription_id 
            FROM subscriptions s
            WHERE s.company_id = %s AND s.status = 'active'
        """, (session['company_id'],))
        subscription = cur.fetchone()
        
        if not subscription:
            flash('No active subscription found', 'danger')
            return redirect(url_for('subscription_management'))
        
        # Get new plan
        cur.execute("""
            SELECT stripe_price_id 
            FROM plans 
            WHERE id = %s AND is_active = TRUE
        """, (new_plan_id,))
        new_plan = cur.fetchone()
        
        if not new_plan:
            flash('Invalid plan', 'danger')
            return redirect(url_for('subscription_management'))
        
        # Update subscription in Stripe
        stripe.Subscription.modify(
            subscription[0],
            items=[{
                'price': new_plan[0],
            }]
        )
        
        # Update database
        cur.execute("""
            UPDATE subscriptions 
            SET plan_id = %s 
            WHERE stripe_subscription_id = %s
        """, (new_plan_id, subscription[0]))
        
        conn.commit()
        flash('Plan changed successfully!', 'success')
    except stripe.error.StripeError as e:
        conn.rollback()
        app.logger.error(f"Stripe error changing plan: {str(e)}")
        flash('Error processing plan change with Stripe', 'danger')
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error changing plan: {str(e)}")
        flash('Error changing plan', 'danger')
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('subscription_management'))

@app.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel subscription at period end"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get current subscription
        cur.execute("""
            SELECT stripe_subscription_id 
            FROM subscriptions 
            WHERE company_id = %s AND status = 'active'
        """, (session['company_id'],))
        subscription = cur.fetchone()
        
        if not subscription:
            flash('No active subscription found', 'danger')
            return redirect(url_for('subscriptions'))
        
        # Cancel in Stripe (end of period)
        stripe.Subscription.modify(
            subscription[0],
            cancel_at_period_end=True
        )
        
        # Update database
        cur.execute("""
            UPDATE subscriptions 
            SET cancel_at_period_end = TRUE 
            WHERE stripe_subscription_id = %s
        """, (subscription[0],))
        
        conn.commit()
        flash('Subscription will be canceled at the end of the billing period', 'success')
    except stripe.error.StripeError as e:
        conn.rollback()
        app.logger.error(f"Stripe error canceling subscription: {str(e)}")
        flash('Error canceling subscription with Stripe', 'danger')
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Error canceling subscription: {str(e)}")
        flash('Error canceling subscription', 'danger')
    finally:
        cur.close()
        conn.close()
    
    # FLUXO CORRIGIDO: Volta para página de planos após cancelamento
    return redirect(url_for('plans'))

# ============== STRIPE WEBHOOKS ==============

@app.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_webhook_secret
        )

        # Processar evento de checkout completo
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            handle_checkout_completed(session)

    except ValueError as e:
        return jsonify({'error': 'Payload inválido'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Assinatura inválida'}), 400
    except Exception as e:
        app.logger.error(f"Erro crítico no webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

    return '', 200


def handle_checkout_completed(session):
    """Ativa a assinatura após pagamento bem-sucedido"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Obter company_id da sessão
        company_id = session['metadata']['company_id']
        
        # Ativar empresa
        cur.execute("""
            UPDATE companies 
            SET is_active = TRUE 
            WHERE id = %s
        """, (company_id,))
        
        # Registrar assinatura
        subscription = stripe.Subscription.retrieve(session['subscription'])
        cur.execute("""
            INSERT INTO subscriptions (
                company_id, stripe_subscription_id, status,
                current_period_end
            ) VALUES (%s, %s, %s, %s)
        """, (
            company_id,
            subscription.id,
            subscription.status,
            datetime.fromtimestamp(subscription.current_period_end)
        ))
        
        conn.commit()
    except Exception as e:
        app.logger.error(f"Erro ao processar webhook: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

# ============== API ROUTES FOR SUBSCRIPTIONS ==============
@app.route('/payment-failed')
@login_required
def payment_failed():
    """Display payment failed page"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM payment_events 
            WHERE company_id = %s AND event_type = 'payment_failed'
            RETURNING id
        """, (session['company_id'],))
        
        if cur.fetchone():
            return render_template('payment_failed.html')
        else:
            return redirect(url_for('dashboard'))
    finally:
        conn.close()

@app.route('/api/subscriptions', methods=['POST'])
@login_required
def create_subscription():
    """Create new Stripe subscription"""
    data = request.get_json()
    plan_id = data.get('plan_id')
    
    if not plan_id:
        return jsonify({'error': 'Plan ID is required'}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get plan
        cur.execute("""
            SELECT stripe_price_id 
            FROM plans 
            WHERE id = %s AND is_active = TRUE
        """, (plan_id,))
        plan = cur.fetchone()
        
        if not plan:
            return jsonify({'error': 'Invalid plan'}), 404
        
        # Get Stripe customer
        cur.execute("""
            SELECT stripe_customer_id 
            FROM companies 
            WHERE id = %s
        """, (session['company_id'],))
        customer = cur.fetchone()
        
        if not customer or not customer[0]:
            return jsonify({'error': 'Stripe customer not found'}), 400
        
        customer_id = decrypt_data(customer[0])
        
        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': plan[0],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('subscription_success', _external=True),
            cancel_url=url_for('plans', _external=True),
            metadata={
                'company_id': session['company_id'],
                'plan_id': plan_id
            }
        )
        
        return jsonify({'session_id': session.id})
        
    except stripe.error.StripeError as e:
        app.logger.error(f"Stripe error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        app.logger.error(f"Subscription error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/subscriptions', methods=['GET'])
@login_required
def get_subscriptions():
    """List all company subscriptions"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT s.id, p.name, s.status, s.current_period_end,
                   s.stripe_subscription_id, s.renewal_date
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.id
            WHERE s.company_id = %s
        """, (session['company_id'],))
        
        subscriptions = []
        for row in cur.fetchall():
            subscriptions.append({
                'id': row[0],
                'plan_name': row[1],
                'status': row[2],
                'current_period_end': row[3].isoformat() if row[3] else None,
                'stripe_subscription_id': row[4],
                'renewal_date': row[5].isoformat() if row[5] else None
            })
        
        return jsonify(subscriptions)
    except Exception as e:
        app.logger.error(f"Error fetching subscriptions: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/subscriptions/webhook', methods=['POST'])
def stripe_webhook_handler():
    """Stripe webhook handler for subscription events"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_webhook_secret
        )
    except ValueError as e:
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({'error': 'Invalid signature'}), 400

    # Process events
    if event['type'] == 'checkout.session.completed':
        handle_checkout_completed(event['data']['object'])
    elif event['type'] == 'customer.subscription.created':
        handle_subscription_created(event['data']['object'])
    elif event['type'] == 'customer.subscription.updated':
        handle_subscription_updated(event['data']['object'])
    elif event['type'] == 'customer.subscription.deleted':
        handle_subscription_deleted(event['data']['object'])
    elif event['type'] == 'invoice.payment_succeeded':
        handle_invoice_payment_succeeded(event['data']['object'])
    elif event['type'] == 'invoice.payment_failed':
        handle_invoice_payment_failed(event['data']['object'])
    
    return jsonify({'success': True}), 200

def handle_checkout_completed(session):
    """Handle completed checkout session"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        subscription_id = session['subscription']
        company_id = session['metadata']['company_id']
        plan_id = session['metadata']['plan_id']
        
        # Get subscription details from Stripe
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Calculate renewal date
        renewal_date = datetime.fromtimestamp(subscription['current_period_end'])
        
        # Insert subscription into database
        cur.execute("""
            INSERT INTO subscriptions (
                company_id, plan_id, stripe_subscription_id,
                status, current_period_end, renewal_date
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            company_id,
            plan_id,
            subscription_id,
            subscription['status'],
            renewal_date,
            renewal_date
        ))
        
        # Activate company
        cur.execute("""
            UPDATE companies 
            SET is_active = TRUE 
            WHERE id = %s
        """, (company_id,))
        
        conn.commit()
        app.logger.info(f"Subscription activated for company {company_id}")
    except Exception as e:
        app.logger.error(f"Error handling checkout completed: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def handle_subscription_created(subscription):
    """Handle new subscription creation"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        customer_id = subscription['customer']
        subscription_id = subscription['id']
        status = subscription['status']
        renewal_date = datetime.fromtimestamp(subscription['current_period_end'])
        
        # Find company by customer ID
        cur.execute("""
            SELECT id 
            FROM companies 
            WHERE stripe_customer_id = %s
        """, (encrypt_data(customer_id),))
        company = cur.fetchone()
        
        if company:
            company_id = company[0]
            # Plan ID is not available in this event, will update later
            cur.execute("""
                INSERT INTO subscriptions (
                    company_id, stripe_subscription_id,
                    status, current_period_end, renewal_date
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                company_id,
                subscription_id,
                status,
                renewal_date,
                renewal_date
            ))
            conn.commit()
            app.logger.info(f"Subscription created for company {company_id}")
    except Exception as e:
        app.logger.error(f"Error handling subscription created: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        subscription_id = subscription['id']
        status = subscription['status']
        renewal_date = datetime.fromtimestamp(subscription['current_period_end'])
        cancel_at_period_end = subscription['cancel_at_period_end']
        
        # Update subscription in database
        cur.execute("""
            UPDATE subscriptions 
            SET status = %s,
                current_period_end = %s,
                renewal_date = %s,
                cancel_at_period_end = %s
            WHERE stripe_subscription_id = %s
        """, (
            status,
            renewal_date,
            renewal_date,
            cancel_at_period_end,
            subscription_id
        ))
        conn.commit()
        app.logger.info(f"Subscription updated: {subscription_id}")
    except Exception as e:
        app.logger.error(f"Error updating subscription: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        subscription_id = subscription['id']
        
        # Mark subscription as canceled
        cur.execute("""
            UPDATE subscriptions 
            SET status = 'canceled'
            WHERE stripe_subscription_id = %s
        """, (subscription_id,))
        
        # Deactivate company
        cur.execute("""
            UPDATE companies 
            SET is_active = FALSE 
            WHERE id = (
                SELECT company_id 
                FROM subscriptions 
                WHERE stripe_subscription_id = %s
            )
        """, (subscription_id,))
        
        conn.commit()
        app.logger.info(f"Subscription canceled: {subscription_id}")
    except Exception as e:
        app.logger.error(f"Error canceling subscription: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def handle_invoice_payment_succeeded(invoice):
    """Handle successful invoice payments"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        customer_id = invoice['customer']
        amount = invoice['amount_paid'] / 100  # Convert from cents
        currency = invoice['currency'].upper()
        invoice_id = invoice['id']
        invoice_url = invoice['hosted_invoice_url']
        
        # Find company by customer ID
        cur.execute("""
            SELECT id 
            FROM companies 
            WHERE stripe_customer_id = %s
        """, (encrypt_data(customer_id),))
        company = cur.fetchone()
        
        if company:
            company_id = company[0]
            # Record payment in database
            cur.execute("""
                INSERT INTO payments (
                    company_id, amount, currency, invoice_id, invoice_url
                ) VALUES (%s, %s, %s, %s, %s)
            """, (company_id, amount, currency, invoice_id, invoice_url))
            conn.commit()
            app.logger.info(f"Payment recorded for company {company_id}")
    except Exception as e:
        app.logger.error(f"Error handling invoice payment: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def handle_invoice_payment_failed(invoice):
    """Handle failed invoice payments"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        customer_id = invoice['customer']
        invoice_url = invoice['hosted_invoice_url']
        
        # Find company by customer ID
        cur.execute("""
            SELECT id 
            FROM companies 
            WHERE stripe_customer_id = %s
        """, (encrypt_data(customer_id),))
        company = cur.fetchone()
        
        if company:
            company_id = company[0]
            # Update subscription status to past_due
            cur.execute("""
                UPDATE subscriptions 
                SET status = 'past_due'
                WHERE company_id = %s
            """, (company_id,))
            
            # Get admin email
            cur.execute("""
                SELECT email, first_name 
                FROM users 
                WHERE company_id = %s AND is_admin = TRUE
                LIMIT 1
            """, (company_id,))
            admin = cur.fetchone()
            
            if admin:
                send_payment_failed_email(admin[0], admin[1], invoice_url)
            
            conn.commit()
            app.logger.info(f"Payment failed for company {company_id}")
    except Exception as e:
        app.logger.error(f"Error handling payment failure: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# Helper routes
@app.route('/subscription-success')
def subscription_success():
    """Success page after subscription"""
    return render_template('subscription_success.html')

# Route for company status
@app.route('/company-status')
@login_required
def company_status():
    """Display company status and resource usage"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Get company data
        cur.execute("""
            SELECT id, name, email, country, industry, date_registered, is_active
            FROM companies 
            WHERE id = %s
        """, (session['company_id'],))
        company = cur.fetchone()
        
        # Get current subscription
        cur.execute("""
            SELECT s.id, p.name, s.status, s.current_period_end, p.features
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.id
            WHERE s.company_id = %s
        """, (session['company_id'],))
        subscription = cur.fetchone()
        
        # Calculate resource usage
        # Projects
        cur.execute("SELECT COUNT(*) FROM projects WHERE company_id = %s", (session['company_id'],))
        project_count = cur.fetchone()[0]
        
        # Users
        cur.execute("SELECT COUNT(*) FROM users WHERE company_id = %s", (session['company_id'],))
        user_count = cur.fetchone()[0]
        
        # Storage (example, not implemented)
        storage_usage = 0
        
        # Get plan limits
        features = {}
        if subscription and subscription[4]:
            features = json.loads(subscription[4])
        
        max_projects = int(features.get('max_projects', 0))
        max_users = int(features.get('max_users', 0))
        max_storage = features.get('max_storage', '0')
        
        # Calculate percentages
        project_percentage = min(100, int((project_count / max_projects) * 100)) if max_projects > 0 else 0
        user_percentage = min(100, int((user_count / max_users) * 100)) if max_users > 0 else 0
        storage_percentage = 0  # not implemented
        
        usage = {
            'projects': {'current': project_count, 'max': max_projects, 'percentage': project_percentage},
            'users': {'current': user_count, 'max': max_users, 'percentage': user_percentage},
            'storage': {'current': storage_usage, 'max': max_storage, 'percentage': storage_percentage}
        }
        
        return render_template('company_status.html', 
                             company=company,
                             subscription=subscription,
                             usage=usage)
    except Exception as e:
        app.logger.error(f"Error loading company status: {str(e)}")
        flash('Error loading company information', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()

# ============== ADMIN PLAN MANAGEMENT VIEW ==============

@app.route('/subscription-management')
@admin_required
def subscription_management():
    """Admin view for managing company subscription"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get current subscription details
        cur.execute("""
            SELECT 
                s.id, 
                p.name as plan_name, 
                s.status, 
                s.current_period_end,
                s.renewal_date,
                s.cancel_at_period_end,
                s.stripe_subscription_id
            FROM subscriptions s
            JOIN plans p ON s.plan_id = p.id
            WHERE s.company_id = %s
        """, (session['company_id'],))
        subscription = cur.fetchone()
        
        # Get all available plans
        cur.execute("SELECT id, name, description, price, features FROM plans WHERE is_active = TRUE")
        plans = cur.fetchall()
        
        # Get payment history
        cur.execute("""
            SELECT id, amount, currency, payment_date, invoice_id
            FROM payments
            WHERE company_id = %s
            ORDER BY payment_date DESC
        """, (session['company_id'],))
        payments = cur.fetchall()
        
        return render_template('subscription_management.html',
                             subscription=subscription,
                             plans=plans,
                             payments=payments)
    except Exception as e:
        app.logger.error(f"Error loading subscription management: {str(e)}")
        flash('Error loading subscription details', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cur.close()
        conn.close()

# Database initialization
def init_db():
    """Initialize database with required tables"""
    conn = None
    try:
        app.logger.info("Initializing database...")
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if companies table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'companies'
            );
        """)
        exists = cur.fetchone()[0]
        
        if not exists:
            app.logger.info("Creating database tables...")
            
            # Create tables
            cur.execute("""
                CREATE TABLE companies (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    country VARCHAR(100),
                    industry VARCHAR(100),
                    date_registered TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT FALSE,
                    stripe_customer_id VARCHAR(255),
                    plan_id INTEGER,
                    cnpj VARCHAR(20)
                );
                
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100),
                    email VARCHAR(255) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    company_id INTEGER REFERENCES companies(id),
                    is_admin BOOLEAN DEFAULT FALSE,
                    email_verified BOOLEAN DEFAULT FALSE,
                    verification_token VARCHAR(255),
                    verification_token_expiry TIMESTAMP,
                    reset_token VARCHAR(255),
                    reset_token_expiry TIMESTAMP,
                    last_login TIMESTAMP,
                    role VARCHAR(20) DEFAULT 'User'
                );
                
                CREATE TABLE plans (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    features JSONB,
                    price DECIMAL(10, 2) NOT NULL,
                    stripe_price_id VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE
                );
                
                CREATE TABLE subscriptions (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER REFERENCES companies(id),
                    plan_id INTEGER REFERENCES plans(id),
                    stripe_subscription_id VARCHAR(255) UNIQUE,
                    status VARCHAR(50),
                    current_period_start TIMESTAMP,
                    current_period_end TIMESTAMP,
                    cancel_at_period_end BOOLEAN DEFAULT FALSE,
                    last_invoice_id VARCHAR(255),
                    last_invoice_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                );
                
                CREATE TABLE projects (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES companies(id),
                    name TEXT NOT NULL,
                    description TEXT,
                    start_date DATE,
                    end_date DATE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE tasks (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    title TEXT NOT NULL,
                    description TEXT,
                    due_date DATE,
                    assigned_user INTEGER REFERENCES users(id),
                    status TEXT NOT NULL DEFAULT 'Not Started',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE income (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    type TEXT NOT NULL,
                    date DATE NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    invoice_id TEXT,
                    invoice_link TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE expenses (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    type TEXT NOT NULL,
                    date DATE NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    invoice_id TEXT,
                    invoice_link TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE general_expenses (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER REFERENCES companies(id),
                    type VARCHAR(100) NOT NULL,
                    date DATE NOT NULL,
                    amount DECIMAL(15, 2) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE payments (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES companies(id),
                    amount DECIMAL(10,2) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    invoice_id TEXT NOT NULL UNIQUE,
                    invoice_url TEXT NOT NULL,
                    payment_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE plan_changes (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES companies(id),
                    old_plan_id INTEGER REFERENCES plans(id),
                    new_plan_id INTEGER NOT NULL REFERENCES plans(id),
                    change_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    stripe_event_id TEXT
                );
                
                CREATE TABLE payment_events (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL REFERENCES companies(id),
                    event_type VARCHAR(50) NOT NULL,
                    event_data JSONB,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE audit_log (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    company_id INTEGER REFERENCES companies(id),
                    action TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id INTEGER,
                    ip_address TEXT,
                    user_agent TEXT,
                    details JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Insert default plans (including free plan)
            cur.execute("""
                INSERT INTO plans (name, description, features, price, stripe_price_id) 
                VALUES 
                    ('Free', 'Initial free plan', 
                    '{"max_projects": 3, "max_users": 1, "max_storage": "100MB"}', 
                    0.00, 'price_1Rap7kGK1tkBcsruKBjT5y7c'),

                    ('Basic', 'Basic plan for small teams', 
                    '{"max_projects": 10, "max_users": 5, "max_storage": "1GB"}', 
                    99.00, 'price_1Rap86GK1tkBcsruzIHX09Ek'),

                    ('Professional', 'Complete plan for businesses', 
                    '{"max_projects": "Unlimited", "max_users": 20, "max_storage": "10GB"}', 
                    199.00, 'price_1RapH6GK1tkBcsruge7gNO4m'),

                    ('Enterprise', 'Custom solution', 
                    '{"max_projects": "Unlimited", "max_users": "Unlimited", "max_storage": "100GB"}', 
                    499.00, 'price_1RapHbGK1tkBcsru3vvG2fbZ');
            """)

            conn.commit()
            app.logger.info("Database initialized successfully!")
        else:
            app.logger.info("Database already exists")
            
    except Exception as e:
        app.logger.error(f"Error initializing database: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# Application entry point
if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Additional configurations
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
    app.config['SESSION_COOKIE_guardar/14/06 email e testeHTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Run application
    app.run(
        host=os.getenv('FLASK_HOST', '0.0.0.0'),
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'True') == 'True'
    )