import time


def get_user_capital(state, username):
    return round(float(state["user_deposits"].get(username, 0)), 2)


def get_user_total_balance(state, username):
    return round(float(state["user_balance"].get(username, 0)), 2)


def get_user_profit_only(state, username):
    capital = get_user_capital(state, username)
    balance = get_user_total_balance(state, username)
    profit_only = round(balance - capital, 2)
    return profit_only if profit_only > 0 else 0.0


def get_profit_capital_for_user(state, username, save_data_func):
    pending_data = state["pending_profit_capital_activation"].get(username)

    if not pending_data:
        return get_user_capital(state, username)

    activate_at = float(pending_data.get("activate_at", 0))
    old_capital = round(float(pending_data.get("old_capital", 0)), 2)

    if time.time() < activate_at:
        return old_capital

    state["pending_profit_capital_activation"].pop(username, None)
    save_data_func()
    return get_user_capital(state, username)


def get_daily_profit_amount(state, username, save_data_func):
    capital = get_profit_capital_for_user(state, username, save_data_func)
    if capital <= 0:
        return 0.0
    return round(capital * 0.02, 2)


def get_min_withdraw_amount(state, username):
    capital = get_user_capital(state, username)
    return round(capital * 0.20, 2)


def update_profit(state, username, add_transaction_func, save_data_func):
    if username not in state["user_deposits"]:
        return

    if state["stopped_profit_users"].get(username, False):
        return

    total_capital = float(state["user_deposits"].get(username, 0))
    if total_capital <= 0:
        return

    now = time.time()
    last_time = float(state["user_last_profit"].get(username, now))
    days_passed = int((now - last_time) // 86400)

    if days_passed <= 0:
        return

    pending_data = state["pending_profit_capital_activation"].get(username)
    total_profit = 0.0
    activated_during_update = False

    for day_index in range(1, days_passed + 1):
        profit_day_time = last_time + (day_index * 86400)

        if pending_data:
            activate_at = float(pending_data.get("activate_at", 0))
            old_capital = float(pending_data.get("old_capital", total_capital))

            if profit_day_time < activate_at:
                profit_capital = old_capital
            else:
                profit_capital = total_capital
                activated_during_update = True
        else:
            profit_capital = total_capital

        daily_profit = profit_capital * 0.02
        total_profit += daily_profit

    total_profit = round(total_profit, 2)

    if total_profit > 0:
        state["user_balance"][username] = round(
            float(state["user_balance"].get(username, 0)) + total_profit,
            2
        )

    state["user_last_profit"][username] = last_time + (days_passed * 86400)

    if activated_during_update:
        state["pending_profit_capital_activation"].pop(username, None)

    add_transaction_func(
        username,
        "profit",
        total_profit,
        f"إضافة أرباح {days_passed} يوم"
    )

    save_data_func()


def get_next_profit_time(state, username):
    last_time = float(state["user_last_profit"].get(username, time.time()))
    next_time = last_time + 86400
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_time))