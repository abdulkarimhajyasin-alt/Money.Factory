import json
import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None


def init_db_pool():
    global db_pool

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL غير موجود. تأكد من إضافته داخل Render Environment.")

    if db_pool is None:
        db_pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor
        )


def get_db_connection():
    global db_pool

    if db_pool is None:
        init_db_pool()

    return db_pool.getconn()


def release_db_connection(conn):
    global db_pool

    if db_pool is not None and conn is not None:
        db_pool.putconn(conn)


def close_db_pool():
    global db_pool

    if db_pool is not None:
        db_pool.closeall()
        db_pool = None


def init_db():
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_storage (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL
            );
        """)

        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"خطأ في init_db: {e}")
        raise

    finally:
        if cur:
            cur.close()
        release_db_connection(conn)


def db_get(key, default_value):
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT value FROM bot_storage WHERE key = %s;", (key,))
        row = cur.fetchone()

        if row:
            return row["value"]

        return default_value

    except Exception as e:
        print(f"خطأ في db_get للعنصر {key}: {e}")
        raise

    finally:
        if cur:
            cur.close()
        release_db_connection(conn)


def db_set(key, value):
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO bot_storage (key, value)
            VALUES (%s, %s::jsonb)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value;
        """, (key, json.dumps(value, ensure_ascii=False)))

        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"خطأ في db_set للعنصر {key}: {e}")
        raise

    finally:
        if cur:
            cur.close()
        release_db_connection(conn)
