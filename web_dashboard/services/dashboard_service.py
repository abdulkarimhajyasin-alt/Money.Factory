from web_dashboard.services.storage_service import get_all_users, get_all_data


def build_dashboard_summary():
    users = get_all_users()
    data = get_all_data()

    user_plans = data.get("user_plans", {})
    user_balance = data.get("user_balance", {})
    user_deposits = data.get("user_deposits", {})
    verified_users = data.get("verified_users", {})
    user_statuses = data.get("user_statuses", {})
    pending_deposit_requests = data.get("pending_deposit_requests", {})
    pending_withdraw_requests = data.get("pending_withdraw_requests", {})
    capital_withdraw_requests = data.get("capital_withdraw_requests", {})

    total_users = len(users)
    verified_count = sum(1 for username in users if bool(verified_users.get(username, False)))
    active_count = sum(1 for username in users if user_statuses.get(username, "active") == "active")
    frozen_count = sum(1 for username in users if user_statuses.get(username) == "frozen")
    banned_count = sum(1 for username in users if user_statuses.get(username) == "banned")

    silver_count = sum(1 for username in users if user_plans.get(username) == "الباقة الفضية")
    gold_count = sum(1 for username in users if user_plans.get(username) == "الباقة الذهبية")
    vip_count = sum(1 for username in users if user_plans.get(username) == "باقة VIP")
    no_plan_count = sum(1 for username in users if user_plans.get(username) in [None, "NONE"])

    total_capital = round(sum(float(user_deposits.get(username, 0)) for username in users), 2)
    total_balances = round(sum(float(user_balance.get(username, 0)) for username in users), 2)
    total_profit_only = max(round(total_balances - total_capital, 2), 0)

    return {
        "total_users": total_users,
        "verified_users": verified_count,
        "unverified_users": total_users - verified_count,
        "active_users": active_count,
        "frozen_users": frozen_count,
        "banned_users": banned_count,
        "silver_users": silver_count,
        "gold_users": gold_count,
        "vip_users": vip_count,
        "no_plan_users": no_plan_count,
        "total_capital": total_capital,
        "total_balances": total_balances,
        "total_profit_only": total_profit_only,
        "pending_deposits": len(pending_deposit_requests),
        "pending_withdraws": len(pending_withdraw_requests),
        "pending_capital_withdraws": len(capital_withdraw_requests),
        "subscriptions_open": data.get("subscriptions_open", True),
        "bot_maintenance_mode": data.get("bot_maintenance_mode", False),
        "support_employees_enabled": data.get("support_employees_enabled", False),
    }
