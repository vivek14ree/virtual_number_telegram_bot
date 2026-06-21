# database.py
import sqlite3
from datetime import datetime

DB_NAME = "telegram_bot.db"

def get_db():
    """Get database connection."""
    return sqlite3.connect(DB_NAME)

def setup_database():
    """Create all tables if they don't exist."""
    conn = get_db()
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        first_name TEXT,
        balance_npr REAL DEFAULT 0,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        order_id_5sim TEXT,
        phone TEXT,
        service TEXT,
        country TEXT,
        price_usd REAL,
        price_npr REAL,
        status TEXT,
        code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Payments table
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount_npr REAL,
        gateway TEXT,
        transaction_id TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Add missing columns if upgrading
    c.execute("PRAGMA table_info(orders)")
    columns = [col[1] for col in c.fetchall()]
    if 'service' not in columns:
        c.execute("ALTER TABLE orders ADD COLUMN service TEXT")
    if 'code' not in columns:
        c.execute("ALTER TABLE orders ADD COLUMN code TEXT")
    
    conn.commit()
    conn.close()
    print("✅ Database ready")

# ============ USER FUNCTIONS ============

def add_user(user_id, username, first_name):
    """Add a new user to database."""
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                  (user_id, username, first_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user(user_id):
    """Get user by Telegram ID."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_user_balance(user_id):
    """Get user's balance in NPR."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance_npr FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_user_balance(user_id, amount, operation="add"):
    """Add or deduct balance."""
    conn = get_db()
    c = conn.cursor()
    if operation == "add":
        c.execute("UPDATE users SET balance_npr = balance_npr + ? WHERE user_id = ?", (amount, user_id))
    else:
        c.execute("UPDATE users SET balance_npr = balance_npr - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# ============ ORDER FUNCTIONS ============

def record_order(user_id, order_id_5sim, phone, service, country, price_usd, price_npr, status):
    """Record a new order."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO orders 
                 (user_id, order_id_5sim, phone, service, country, price_usd, price_npr, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, order_id_5sim, phone, service, country, price_usd, price_npr, status))
    order_db_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_db_id

def update_order_status(order_db_id, status, code=None):
    """Update order status and code."""
    conn = get_db()
    c = conn.cursor()
    if code:
        c.execute("UPDATE orders SET status = ?, code = ? WHERE id = ?", (status, code, order_db_id))
    else:
        c.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_db_id))
    conn.commit()
    conn.close()

def get_user_orders(user_id, limit=15):
    """Get user's recent orders."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT id, service, country, phone, price_npr, status, code, created_at
                 FROM orders WHERE user_id = ?
                 ORDER BY created_at DESC LIMIT ?''', (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows