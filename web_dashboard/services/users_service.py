from web_dashboard.services.storage_service import get_all_users, get_all_data


def build_users_list():
    users = get_all_users()
    data = get_all_data()

    user_plans = data.get("user_plans", {})
    user_balance = data.get("user_balance", {})
    user_deposits = data.get("user_deposits", {})
    user_statuses = data.get("user_statuses", {})
    verified_users = data.get("verified_users", {})
    user_full_name = data.get("user_full_name", {})
    user_residence = data.get("user_residence", {})
    user_telegram_ids = data.get("user_telegram_ids", {})
    user_referrer = data.get("user_referrer", {})

    result = []

    for username, password in users.items():
        capital = round(float(user_deposits.get(username, 0)), 2)
        balance = round(float(user_balance.get(username, 0)), 2)
        profit_only = round(balance - capital, 2)

        if profit_only < 0:
            profit_only = 0

        result.append({
            "username": username,
            "password": password,
            "telegram_id": user_telegram_ids.get(username),
            "full_name": user_full_name.get(username, "غير متوفر"),
            "residence": user_residence.get(username, "غير متوفر"),
            "plan": user_plans.get(username, "NONE"),
            "status": user_statuses.get(username, "active"),
            "verified": bool(verified_users.get(username, False)),
            "capital": capital,
            "balance": balance,
            "profit_only": profit_only,
            "referrer": user_referrer.get(username, "بدون دعوة"),
            "children_count": sum(
                1 for child_username, referrer_username in user_referrer.items()
                if referrer_username == username
              )
        })

    return result


def search_users(search_text=""):
    users = build_users_list()

    if not search_text:
        return users

    search_text = search_text.strip().lower()

    return [
        user for user in users
        if search_text in user["username"].lower()
        or search_text in str(user.get("password", "")).lower()
        or search_text in str(user.get("full_name", "")).lower()
        or search_text in str(user.get("telegram_id", "")).lower()
        or search_text in str(user.get("residence", "")).lower()
        or search_text in str(user.get("plan", "")).lower()
        or search_text in str(user.get("status", "")).lower()
    ]