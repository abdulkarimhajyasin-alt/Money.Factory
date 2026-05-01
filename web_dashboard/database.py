import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from web_dashboard.config import DATABASE_URL

web_db_pool = None


def init_web_db_pool():
    global web_db_pool

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL غير موجود")

    if web_db_pool is None:
        web_db_pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor
        )


def get_web_db_connection():
    global web_db_pool

    if web_db_pool is None:
        init_web_db_pool()

    return web_db_pool.getconn()


def release_web_db_connection(conn):
    global web_db_pool

    if web_db_pool is not None and conn is not None:
        web_db_pool.putconn(conn)


def close_web_db_pool():
    global web_db_pool

    if web_db_pool is not None:
        web_db_pool.closeall()
        web_db_pool = None