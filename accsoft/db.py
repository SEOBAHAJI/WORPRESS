import sqlite3
import threading
from contextlib import contextmanager

from .config import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pass_hash TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS products(
  id INTEGER PRIMARY KEY, sku TEXT UNIQUE, name TEXT NOT NULL, category TEXT DEFAULT '',
  currency TEXT NOT NULL DEFAULT 'IRT' CHECK(currency IN ('IRT','USD')),
  price REAL NOT NULL DEFAULT 0, cost REAL NOT NULL DEFAULT 0,
  stock INTEGER NOT NULL DEFAULT 0, min_stock INTEGER NOT NULL DEFAULT 0,
  image TEXT DEFAULT '', woo_id INTEGER UNIQUE, woo_dirty INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS stock_moves(
  id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id),
  qty INTEGER NOT NULL, reason TEXT NOT NULL, ref TEXT DEFAULT '', note TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS customers(
  id INTEGER PRIMARY KEY, first_name TEXT DEFAULT '', last_name TEXT DEFAULT '',
  phone TEXT UNIQUE, welcomed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sales(
  id INTEGER PRIMARY KEY, number INTEGER UNIQUE, customer_id INTEGER REFERENCES customers(id),
  channel TEXT NOT NULL CHECK(channel IN ('offline','online')),
  subtotal INTEGER NOT NULL, discount INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL,
  cogs INTEGER NOT NULL DEFAULT 0, pay_method TEXT DEFAULT 'cash', note TEXT DEFAULT '',
  woo_order_id INTEGER UNIQUE, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sale_items(
  id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
  product_id INTEGER REFERENCES products(id), name TEXT NOT NULL,
  qty INTEGER NOT NULL, unit_price INTEGER NOT NULL, unit_cost INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS expenses(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, amount INTEGER NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sms_log(
  id INTEGER PRIMARY KEY, phone TEXT, text TEXT, ok INTEGER, detail TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_sales_date ON sales(created_at);
CREATE INDEX IF NOT EXISTS ix_items_sale ON sale_items(sale_id);
"""

# مهاجرت‌های نسخه‌دار؛ هر مورد یک‌بار اجرا می‌شود (PRAGMA user_version). هرگز موارد قبلی را تغییر ندهید.
MIGRATIONS = [
    """
    ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'admin';
    ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1;
    ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT '';
    ALTER TABLE products ADD COLUMN kind TEXT NOT NULL DEFAULT 'simple';
    ALTER TABLE products ADD COLUMN parent_id INTEGER REFERENCES products(id);
    ALTER TABLE products ADD COLUMN attrs TEXT DEFAULT '';
    ALTER TABLE products ADD COLUMN image_dirty INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE sales ADD COLUMN user_id INTEGER;
    ALTER TABLE sales ADD COLUMN paid INTEGER;
    UPDATE sales SET paid=total WHERE paid IS NULL;
    CREATE TABLE suppliers(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT DEFAULT '', note TEXT DEFAULT '',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE purchases(
      id INTEGER PRIMARY KEY, number INTEGER UNIQUE, supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
      total INTEGER NOT NULL, paid INTEGER NOT NULL DEFAULT 0, note TEXT DEFAULT '', user_id INTEGER,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE purchase_items(
      id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
      product_id INTEGER NOT NULL REFERENCES products(id), qty INTEGER NOT NULL, unit_cost INTEGER NOT NULL);
    CREATE TABLE payments(
      id INTEGER PRIMARY KEY, party_type TEXT NOT NULL CHECK(party_type IN ('customer','supplier')),
      party_id INTEGER NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), method TEXT DEFAULT 'cash',
      note TEXT DEFAULT '', user_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX ix_payments_party ON payments(party_type, party_id);
    CREATE TABLE audit(
      id INTEGER PRIMARY KEY, user_id INTEGER, username TEXT, action TEXT NOT NULL, detail TEXT DEFAULT '',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE licenses(
      id INTEGER PRIMARY KEY, product TEXT NOT NULL, key TEXT NOT NULL UNIQUE,
      added_at TEXT DEFAULT CURRENT_TIMESTAMP);
    INSERT INTO licenses(product,key) SELECT 'accsoft', value FROM settings WHERE key='license_key' AND value!='';
    DELETE FROM settings WHERE key='license_key';
    """,
    "ALTER TABLE users ADD COLUMN account TEXT NOT NULL DEFAULT ''",
    """
    CREATE TABLE IF NOT EXISTS installments(
      id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
      due_date TEXT NOT NULL, amount INTEGER NOT NULL, paid INTEGER NOT NULL DEFAULT 0,
      note TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """
]


class DB:
    def __init__(self, path=None):
        self.path = str(path or data_dir() / "accsoft.db")
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self):
        ver = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for i, script in enumerate(MIGRATIONS[ver:], start=ver + 1):
            self.conn.execute("BEGIN")
            try:
                for stmt in script.split(";\n"):
                    if stmt.strip():
                        self.conn.execute(stmt)
                self.conn.execute(f"PRAGMA user_version={i}")
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    @contextmanager
    def tx(self):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        r = self.q(sql, args)
        return r[0] if r else None

    def get(self, key, default=None):
        r = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return r["value"] if r else default

    def set(self, key, value):
        with self.lock:
            self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
