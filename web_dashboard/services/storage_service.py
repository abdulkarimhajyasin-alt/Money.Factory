import json

from web_dashboard.database import get_web_db_connection, release_web_db_connection


def web_db_get(key, default_value=None):
    conn = None
    cur = None

    try:
        conn = get_web_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT value FROM bot_storage WHERE key = %s;", (key,))
        row = cur.fetchone()

        if row:
            return row["value"]

        return default_value

    except Exception as e:
        print(f"[WEB_DB_GET_ERROR] key={key} error={e}")
        return default_value

    finally:
        if cur:
            cur.close()
        release_web_db_connection(conn)


def get_all_users():
    return web_db_get("users", {})


def get_all_data():
    return web_db_get("data", {})


def get_user_by_username(username):
    users = get_all_users()
    return users.get(username)


def get_user_count():
    users = get_all_users()
    return len(users)


def get_users_by_plan():
    data = get_all_data()
    user_plans = data.get("user_plans", {})

    result = {}

    for username, plan in user_plans.items():
        result.setdefault(plan, 0)
        result[plan] += 1

    return result


def get_total_balances():
    data = get_all_data()
    balances = data.get("user_balance", {})

    return sum(float(v) for v in balances.values())