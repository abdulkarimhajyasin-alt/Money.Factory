import time


DAILY_PROFIT_RATE = 0.02
MIN_WITHDRAW_RATE = 0.20
SECONDS_PER_DAY = 86400


def round_money(value):
    return round(float(value), 2)


def calculate_profit_only(balance, capital):
    profit_only = round_money(balance) - round_money(capital)
    return round_money(profit_only) if profit_only > 0 else 0.0


def calculate_daily_profit(capital):
    capital = round_money(capital)
    if capital <= 0:
        return 0.0
    return round_money(capital * DAILY_PROFIT_RATE)


def calculate_min_withdraw(capital):
    return round_money(round_money(capital) * MIN_WITHDRAW_RATE)


def calculate_days_passed(last_time, now=None):
    current_time = time.time() if now is None else now
    return int((current_time - float(last_time)) // SECONDS_PER_DAY)


def calculate_elapsed_profit(last_time, days_passed, total_capital, pending_data=None):
    total_capital = float(total_capital)
    total_profit = 0.0
    activated_during_update = False

    for day_index in range(1, days_passed + 1):
        profit_day_time = float(last_time) + (day_index * SECONDS_PER_DAY)

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

        total_profit += profit_capital * DAILY_PROFIT_RATE

    return round_money(total_profit), activated_during_update
