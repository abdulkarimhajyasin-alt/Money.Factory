from database import db_get, db_set


def load_users(state):
    state["users"] = db_get("users", {})


def save_users(state):
    db_set("users", state["users"])


def load_chat_ids(state):
    state["chat_ids"] = db_get("chat_ids", [])


def save_chat_ids(state):
    db_set("chat_ids", state["chat_ids"])


def load_data(state):
    data = db_get("data", {})

    state["user_plans"] = data.get("user_plans", {})
    state["user_balance"] = data.get("user_balance", {})
    state["transactions"] = data.get("transactions", {})
    state["user_deposits"] = data.get("user_deposits", {})
    state["user_last_profit"] = data.get("user_last_profit", {})
    state["user_withdraw_logs"] = data.get("user_withdraw_logs", {})
    state["user_deposit_logs"] = data.get("user_deposit_logs", {})
    state["support_blocked_users"] = data.get("support_blocked_users", {})
    state["user_first_deposit_time"] = data.get("user_first_deposit_time", {})
    state["user_last_withdraw_time"] = data.get("user_last_withdraw_time", {})
    state["user_telegram_ids"] = data.get("user_telegram_ids", {})
    state["subscriptions_open"] = data.get("subscriptions_open", True)
    state["bot_maintenance_mode"] = data.get("bot_maintenance_mode", False)

    state["pending_verification_requests"] = {
        int(k): v for k, v in data.get("pending_verification_requests", {}).items()
    }

    state["user_residence"] = data.get("user_residence", {})
    state["user_full_name"] = data.get("user_full_name", {})
    state["verified_users"] = data.get("verified_users", {})
    state["user_referrer"] = data.get("user_referrer", {})
    state["referral_bonus_paid"] = data.get("referral_bonus_paid", {})

    state["capital_withdraw_requests"] = {
        int(k): v for k, v in data.get("capital_withdraw_requests", {}).items()
    }

    state["stopped_profit_users"] = data.get("stopped_profit_users", {})
    state["support_waiting_reply"] = data.get("support_waiting_reply", {})

    state["support_employees_enabled"] = data.get("support_employees_enabled", False)
    state["support_claims"] = data.get("support_claims", {})
    state["support_message_copies"] = data.get("support_message_copies", {})

    state["admin_sent_batches"] = data.get("admin_sent_batches", {})
    state["admin_last_batch_id"] = data.get("admin_last_batch_id", None)
    state["deleted_accounts_log"] = data.get("deleted_accounts_log", [])
    state["manual_withdraw_open"] = data.get("manual_withdraw_open", {})
    state["user_created_time"] = data.get("user_created_time", {})
    state["user_tree_views"] = data.get("user_tree_views", {})
    state["user_wallet_address"] = data.get("user_wallet_address", {})
    state["user_wallet_network"] = data.get("user_wallet_network", {})
    state["user_identity_photos"] = data.get("user_identity_photos", {})
    state["pending_profit_capital_activation"] = data.get("pending_profit_capital_activation", {})

    state["pending_deposit_requests"] = {
        int(k): v for k, v in data.get("pending_deposit_requests", {}).items()
    }

    state["pending_withdraw_requests"] = {
        int(k): v for k, v in data.get("pending_withdraw_requests", {}).items()
    }

    state["logged_in_users"] = {
        int(k): v for k, v in data.get("logged_in_users", {}).items()
    }

    state["user_statuses"] = data.get("user_statuses", {})


def save_data(state):
    data = {
        "user_plans": state["user_plans"],
        "user_balance": state["user_balance"],
        "transactions": state["transactions"],
        "user_deposits": state["user_deposits"],
        "user_last_profit": state["user_last_profit"],
        "user_withdraw_logs": state["user_withdraw_logs"],
        "user_deposit_logs": state["user_deposit_logs"],
        "support_blocked_users": state["support_blocked_users"],
        "user_first_deposit_time": state["user_first_deposit_time"],
        "user_last_withdraw_time": state["user_last_withdraw_time"],
        "user_telegram_ids": state["user_telegram_ids"],
        "subscriptions_open": state["subscriptions_open"],
        "bot_maintenance_mode": state["bot_maintenance_mode"],
        "pending_verification_requests": {
            str(k): v for k, v in state["pending_verification_requests"].items()
        },
        "user_residence": state["user_residence"],
        "user_full_name": state["user_full_name"],
        "verified_users": state["verified_users"],
        "user_referrer": state["user_referrer"],
        "referral_bonus_paid": state["referral_bonus_paid"],
        "capital_withdraw_requests": {
            str(k): v for k, v in state["capital_withdraw_requests"].items()
        },
        "stopped_profit_users": state["stopped_profit_users"],
        "support_waiting_reply": state["support_waiting_reply"],
        "support_employees_enabled": state["support_employees_enabled"],
        "support_claims": state["support_claims"],
        "support_message_copies": state["support_message_copies"],
        "admin_sent_batches": state["admin_sent_batches"],
        "admin_last_batch_id": state["admin_last_batch_id"],
        "deleted_accounts_log": state["deleted_accounts_log"],
        "manual_withdraw_open": state["manual_withdraw_open"],
        "user_created_time": state["user_created_time"],
        "user_tree_views": state["user_tree_views"],
        "user_wallet_address": state["user_wallet_address"],
        "user_wallet_network": state["user_wallet_network"],
        "user_identity_photos": state["user_identity_photos"],
        "pending_profit_capital_activation": state["pending_profit_capital_activation"],
        "pending_deposit_requests": {
            str(k): v for k, v in state["pending_deposit_requests"].items()
        },
        "pending_withdraw_requests": {
            str(k): v for k, v in state["pending_withdraw_requests"].items()
        },
        "logged_in_users": {
            str(k): v for k, v in state["logged_in_users"].items()
        },
        "user_statuses": state["user_statuses"],
    }

    db_set("data", data)