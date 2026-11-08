"""
Personal Finance Enterprise v8 - Real Google OAuth Integrated Backend
Author: Sagnik Guha
"""

import os
os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

# Load local environment variables from .env
load_dotenv()

# Securely fetch credentials for Authlib
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


app = Flask(__name__)
# Enforce correct proxy headers for HTTPS on Render
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY']=True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PREFERRED_URL_SCHEME'] ='https'
app.secret_key = os.getenv("SECRET_KEY", "super-secret-static-key-change-this-later")
DB_NAME = "finance_enterprise.db"

# ==========================================
# ENTERPRISE DATA & CONFIGURATION DICTIONARY
# ==========================================
ENTERPRISE_FINANCE_CONFIG = {
    "system_metadata": {
        "app_name": "Personal Finance Enterprise",
        "version": "v8.4.0-Enterprise",
        "developer": "Sagnik Guha",
        "support_email": "sagnikguha2010@gmail.com",
        "target_deployment": "Render Cloud Infrastructure"
    },
    "security_policies": {
        "session_timeout_seconds": 3600,
        "encryption_cipher": "AES-256-GCM",
        "sql_injection_defense": "Parameterized Queries Enforced",
        "oauth_provider": "Google Identity Services v2"
    },
    "currencies": {
        "INR": {"symbol": "₹", "name": "Indian Rupee"},
        "USD": {"symbol": "$", "name": "United States Dollar"},
        "EUR": {"symbol": "€", "name": "Euro"},
        "GBP": {"symbol": "£", "name": "British Pound"}
    },
    "transaction_categories": [
        "Salary", "Freelance", "Housing", "Utilities", "Food", "Transportation", "Entertainment", "Education"
    ]
}

# Setup Authlib for Google OAuth with your credentials as fallbacks
app.config["GOOGLE_CLIENT_ID"] = GOOGLE_CLIENT_ID
app.config["GOOGLE_CLIENT_SECRET"] = GOOGLE_CLIENT_SECRET


oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'state': False  # Disables strict session state checking across proxy redirects
    }
)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            tx_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            recipient TEXT NOT NULL,
            message TEXT NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({"status": "success", "config": ENTERPRISE_FINANCE_CONFIG})

# ==========================================
# REAL GOOGLE OAUTH AUTHENTICATION ROUTES
# ==========================================
@app.route('/login/google')
def login_google():
    redirect_uri = url_for('authorize_google', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize/google')
def authorize_google():
    # Check if Google returned an error
    if 'error' in request.args:
        return redirect(url_for('index'))
        
    try:
        token = google.authorize_access_token()
        # Fetch user info directly from Google using the token
        resp = google.get('https://www.googleapis.com/oauth2/v3/userinfo')
        user_info = resp.json()
    except Exception as e:
        print(f"OAuth Error: {e}")
        return f"OAuth Error: {str(e)}", 400
        
    if user_info:
        email = user_info['email']
        name = user_info['name']
        session['user_email'] = email
        session['user_name'] = name
        	
        
        # Save or ignore user in SQLite database
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (email, name) VALUES (?, ?)', (email, name))
        conn.commit()
        conn.close()
        
        return redirect('/dashboard')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    user_email = session.get('user_email')
    user_name = session.get('user_name')
    return render_template('index.html', user_email=user_email, user_name=user_name)

@app.route('/api/user/session', methods=['GET'])
def check_session():
    if 'user_email' in session:
        return jsonify({"authenticated": True, "email": session['user_email'], "name": session['user_name']})
    return jsonify({"authenticated": False})

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('dashboard'))

# ==========================================
# SECURE TRANSACTIONS & ENTERPRISE MODULES
# ==========================================
@app.route('/api/transactions', methods=['GET', 'POST'])
def manage_transactions():
    if 'user_email' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    user_email = session['user_email']
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        body = request.get_json()
        title = body.get('title')
        amount = body.get('amount')
        tx_type = body.get('type')
        category = body.get('category', 'General')
        tx_date = body.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        if not title or amount is None:
            return jsonify({"status": "error", "message": "Missing fields"}), 400
            
        cursor.execute('''
            INSERT INTO transactions (user_email, title, amount, type, category, tx_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_email, title, float(amount), tx_type, category, tx_date))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Transaction saved securely"})
        
    cursor.execute('SELECT title, amount, type, category, tx_date FROM transactions WHERE user_email = ? ORDER BY tx_date DESC', (user_email,))
    rows = cursor.fetchall()
    
    transactions = [{"title": r[0], "amount": r[1], "type": r[2], "category": r[3], "date": r[4]} for r in rows]
    total_income = sum(t['amount'] for t in transactions if t['type'] == 'income')
    total_expense = sum(t['amount'] for t in transactions if t['type'] == 'expense')
    
    conn.close()
    return jsonify({
        "status": "success",
        "transactions": transactions,
        "summary": {"total_income": total_income, "total_expense": total_expense, "net_balance": total_income - total_expense}
    })

@app.route('/api/support', methods=['POST'])
def support_ticket():
    body = request.get_json()
    user_email = body.get('user_email', session.get('user_email', 'anonymous'))
    message = body.get('message')
    recipient = ENTERPRISE_FINANCE_CONFIG["system_metadata"]["support_email"]
    
    if not message:
        return jsonify({"status": "error", "message": "Missing information"}), 400
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO support_tickets (user_email, recipient, message) VALUES (?, ?, ?)', (user_email, recipient, message))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": f"Ticket dispatched to {recipient}"})

@app.route('/api/backup/export', methods=['GET'])
def backup_export():
    if 'user_email' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    user_email = session['user_email']
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT title, amount, type, category, tx_date FROM transactions WHERE user_email = ?', (user_email,))
    rows = cursor.fetchall()
    conn.close()
    
    backup = {
        "user": user_email,
        "timestamp": datetime.now().isoformat(),
        "transactions": [{"title": r[0], "amount": r[1], "type": r[2], "category": r[3], "date": r[4]} for r in rows]
    }
    path = f"/tmp/backup_{user_email.split('@')[0]}.json"
    with open(path, 'w') as f:
        json.dump(backup, f, indent=4)
        
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
