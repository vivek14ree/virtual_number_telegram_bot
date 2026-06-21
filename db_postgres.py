# db_postgres.py - PostgreSQL Database Functions
import os
import psycopg2
from datetime import datetime

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_db():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(DATABASE_URL)

def setup_database():
    """Create all tables in PostgreSQL."""
    conn = get_db()
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance_npr REAL DEFAULT 0,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Orders table
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
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
        )
    ''')
    
    # Failed orders table
    c.execute('''
        CREATE TABLE IF NOT EXISTS failed_orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            service TEXT,
            country TEXT,
            cost_usd REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ PostgreSQL Database ready")

def add_user(user_id, username, first_name):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (user_id, username, first_name) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING",
            (user_id, username, first_name)
        )
        conn.commit()
    except Exception as e:
        print(f"Error adding user: {e}")
    finally:
        conn.close()

def get_user_balance(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance_npr FROM users WHERE user_id = %s", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_user_balance(user_id, amount, operation="add"):
    conn = get_db()
    c = conn.cursor()
    if operation == "add":
        c.execute("UPDATE users SET balance_npr = balance_npr + %s WHERE user_id = %s", (amount, user_id))
    else:
        c.execute("UPDATE users SET balance_npr = balance_npr - %s WHERE user_id = %s", (amount, user_id))
    conn.commit()
    conn.close()

def record_order(user_id, order_id_5sim, phone, service, country, price_usd, price_npr, status):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO orders (user_id, order_id_5sim, phone, service, country, price_usd, price_npr, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    ''', (user_id, order_id_5sim, phone, service, country, price_usd, price_npr, status))
    order_db_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return order_db_id

def update_order_status(order_db_id, status, code=None):
    conn = get_db()
    c = conn.cursor()
    if code:
        c.execute("UPDATE orders SET status = %s, code = %s WHERE id = %s", (status, code, order_db_id))
    else:
        c.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_db_id))
    conn.commit()
    conn.close()

def get_user_orders(user_id, limit=15):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT id, service, country, phone, price_npr, status, code, created_at
        FROM orders WHERE user_id = %s
        ORDER BY created_at DESC LIMIT %s
    ''', (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def log_failure(user_id, service, country, cost_usd):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO failed_orders (user_id, service, country, cost_usd) VALUES (%s, %s, %s, %s)",
        (user_id, service, country, cost_usd)
    )
    conn.commit()
    conn.close()
    print(f"❌ FAILED: User {user_id} | {service} | {country} | Lost ${cost_usd:.4f}")