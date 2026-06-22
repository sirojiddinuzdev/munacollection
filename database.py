import sqlite3
import os
from datetime import datetime
import config

class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_file, timeout=20.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = 10000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn

    def init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    phone_number TEXT,
                    registered_at TEXT
                )
            """)

            # Products table (Ads)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    photo_id TEXT,
                    location TEXT,
                    delivery_time TEXT,
                    price TEXT,
                    description TEXT,
                    group_message_id INTEGER,
                    status TEXT DEFAULT 'active',
                    created_at TEXT
                )
            """)

            # Orders table (Purchases)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_id INTEGER,
                    receipt_photo_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)

            # Settings table (for dynamic card info, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Add new columns to orders if not exist
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN approved_at TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN delivery_deadline TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN delivered_at TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE orders ADD COLUMN last_notified_days_left INTEGER DEFAULT -1")
            except sqlite3.OperationalError:
                pass
            
            conn.commit()

    # User management
    def add_user(self, user_id, username, phone_number):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            registered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT OR REPLACE INTO users (user_id, username, phone_number, registered_at) VALUES (?, ?, ?, ?)",
                (user_id, username, phone_number, registered_at)
            )
            conn.commit()

    def get_user(self, user_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def is_user_registered(self, user_id):
        user = self.get_user(user_id)
        return user is not None

    # Product/Ad management
    def add_product(self, photo_id, location, delivery_time, price, description, group_message_id=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """INSERT INTO products (photo_id, location, delivery_time, price, description, group_message_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (photo_id, location, delivery_time, price, description, group_message_id, created_at)
            )
            conn.commit()
            return cursor.lastrowid

    def get_product(self, product_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE id = ? AND status = 'active'", (product_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_active_products(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE status = 'active' ORDER BY id DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_product(self, product_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE products SET status = 'deleted' WHERE id = ?", (product_id,))
            conn.commit()

    def update_product_field(self, product_id, field, value):
        valid_fields = ['photo_id', 'location', 'delivery_time', 'price', 'description', 'group_message_id']
        if field not in valid_fields:
            raise ValueError(f"Invalid field name: {field}")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (value, product_id))
            conn.commit()

    # Order management
    def create_order(self, user_id, product_id, receipt_photo_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO orders (user_id, product_id, receipt_photo_id, created_at) VALUES (?, ?, ?, ?)",
                (user_id, product_id, receipt_photo_id, created_at)
            )
            conn.commit()
            return cursor.lastrowid

    def get_order(self, order_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.*, u.username, u.phone_number, 
                       p.location, p.delivery_time, p.price, p.description
                FROM orders o
                JOIN users u ON o.user_id = u.user_id
                JOIN products p ON o.product_id = p.id
                WHERE o.id = ?
            """, (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_order_status(self, order_id, status):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
            conn.commit()

    def approve_order(self, order_id, approved_at, delivery_deadline):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = 'approved', approved_at = ?, delivery_deadline = ?, last_notified_days_left = -1 WHERE id = ?",
                (approved_at, delivery_deadline, order_id)
            )
            conn.commit()

    def deliver_order(self, order_id, delivered_at):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = 'delivered', delivered_at = ? WHERE id = ?",
                (delivered_at, order_id)
            )
            conn.commit()

    def extend_order_deadline(self, order_id, new_deadline):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET delivery_deadline = ?, last_notified_days_left = -1 WHERE id = ?",
                (new_deadline, order_id)
            )
            conn.commit()

    def update_order_notified_days(self, order_id, days):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE orders SET last_notified_days_left = ? WHERE id = ?", (days, order_id))
            conn.commit()

    def get_undelivered_orders(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.*, u.username, u.phone_number, 
                       p.location, p.delivery_time, p.price, p.description, p.photo_id
                FROM orders o
                JOIN users u ON o.user_id = u.user_id
                JOIN products p ON o.product_id = p.id
                WHERE o.status = 'approved'
                ORDER BY o.id ASC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_delivered_orders(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT o.*, u.username, u.phone_number, 
                       p.location, p.delivery_time, p.price, p.description, p.photo_id
                FROM orders o
                JOIN users u ON o.user_id = u.user_id
                JOIN products p ON o.product_id = p.id
                WHERE o.status = 'delivered'
                ORDER BY o.delivered_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # Settings management
    def get_setting(self, key, default=None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def set_setting(self, key, value):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()

# Expose global database instance
db = Database(config.DB_FILE)
