import sqlite3
import time
from typing import Optional

def get_conn(path: str = None):
    if path is None:
        path = 'bot.db'
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(path: str = None):
    conn = get_conn(path)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        balance INTEGER DEFAULT 0,
        created_at INTEGER
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        type TEXT,
        count INTEGER,
        reward INTEGER,
        channel_message_id INTEGER,
        created_at INTEGER
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        amount INTEGER,
        details TEXT,
        status TEXT DEFAULT 'pending',
        created_at INTEGER
    )
    ''')
    conn.commit()
    return conn

# Backwards-compatible API used by older telebot examples
def initialize_db(path: str = None):
    """Compatibility wrapper for `initialize_db()` used in telebot examples."""
    return init_db(path)

def get_or_create_user(conn, telegram_id: int, username: Optional[str]):
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE telegram_id=?', (telegram_id,))
    row = cur.fetchone()
    if row:
        return row
    now = int(time.time())
    cur.execute('INSERT INTO users (telegram_id, username, created_at) VALUES (?,?,?)', (telegram_id, username, now))
    conn.commit()
    cur.execute('SELECT * FROM users WHERE telegram_id=?', (telegram_id,))
    return cur.fetchone()

def add_user_balance(conn_or_id, telegram_id_or_amount, maybe_amount=None):
    """
    Compatibility wrapper to support two call styles used in simple examples:
    - add_user_balance(user_id, amount) when module is imported as `import db`
    - add_user_balance(conn, user_id, amount) when passing connection explicitly
    """
    # Determine calling pattern
    if maybe_amount is None:
        # Called as add_user_balance(user_id, amount)
        user_id = conn_or_id
        amount = telegram_id_or_amount
        conn = get_conn()
    else:
        conn = conn_or_id
        user_id = telegram_id_or_amount
        amount = maybe_amount

    # Ensure user exists
    get_or_create_user(conn, user_id, None)
    add_balance(conn, user_id, amount)

def get_user_balance(conn_or_id, telegram_id=None):
    """
    Compatibility wrapper supporting both `get_user_balance(user_id)`
    and `get_user_balance(conn, user_id)`.
    """
    if telegram_id is None:
        user_id = conn_or_id
        conn = get_conn()
    else:
        conn = conn_or_id
        user_id = telegram_id
    return get_balance(conn, user_id)

def add_balance(conn, telegram_id: int, amount: int):
    cur = conn.cursor()
    cur.execute('UPDATE users SET balance = balance + ? WHERE telegram_id=?', (amount, telegram_id))
    conn.commit()

def get_balance(conn, telegram_id: int) -> int:
    cur = conn.cursor()
    cur.execute('SELECT balance FROM users WHERE telegram_id=?', (telegram_id,))
    row = cur.fetchone()
    return row['balance'] if row else 0

def log_submission(conn, telegram_id: int, type_: str, count: int, reward: int, channel_message_id: Optional[int]):
    cur = conn.cursor()
    now = int(time.time())
    cur.execute('INSERT INTO submissions (telegram_id, type, count, reward, channel_message_id, created_at) VALUES (?,?,?,?,?,?)',
                (telegram_id, type_, count, reward, channel_message_id, now))
    conn.commit()

def create_withdrawal(conn, telegram_id: int, amount: int, details: str):
    cur = conn.cursor()
    now = int(time.time())
    cur.execute('INSERT INTO withdrawals (telegram_id, amount, details, created_at) VALUES (?,?,?,?)', (telegram_id, amount, details, now))
    conn.commit()
    return cur.lastrowid

def list_pending_withdrawals(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM withdrawals WHERE status='pending'")
    return cur.fetchall()
