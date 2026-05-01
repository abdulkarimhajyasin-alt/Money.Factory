from fastapi import APIRouter, Depends

from web_dashboard.auth import get_current_admin
from web_dashboard.services.storage_service import web_db_get as db_get

router = APIRouter()

import requests
from web_dashboard.config import BOT_TOKEN
from fastapi.responses import RedirectResponse


def build_telegram_file_url(file_id):
    if not file_id:
        return None

    try:
        response = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=10
        )

        result = response.json()

        if not result.get("ok"):
            return None

        file_path = result["result"]["file_path"]

        return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    except Exception:
        return None

@router.get("/pending-deposits")
def get_pending_deposits(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})

    pending_deposit_requests = data.get("pending_deposit_requests", {})

    result = []

    for user_id, request in pending_deposit_requests.items():
        result.append({
            "user_id": user_id,
            "username": request.get("username", "غير معروف"),
            "plan": request.get("plan", "غير معروف"),
            "amount": request.get("amount", 0),
            "type": request.get("type", "new_deposit"),
            "time": request.get("time", "غير متوفر"),
            "old_plan": request.get("old_plan"),
            "new_plan": request.get("new_plan"),
            "old_capital": request.get("old_capital"),
            "final_capital": request.get("final_capital")
        })

    return {
        "count": len(result),
        "pending_deposits": result
    }

from pydantic import BaseModel
from fastapi import HTTPException
import json
import time

from web_dashboard.database import get_web_db_connection, release_web_db_connection


class DepositActionRequest(BaseModel):
    user_id: int


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def db_set(key, value):
    conn = None
    cur = None

    try:
        conn = get_web_db_connection()
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
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if cur:
            cur.close()
        release_web_db_connection(conn)


@router.post("/approve-deposit")
def approve_deposit(
    request: DepositActionRequest,
    admin: str = Depends(get_current_admin)
):
    data = db_get("data", {})
    user_id = request.user_id

    pending = data.get("pending_deposit_requests", {})
    req = pending.get(str(user_id)) or pending.get(user_id)

    if not req:
        raise HTTPException(status_code=404, detail="Deposit request not found")

    username = req["username"]
    amount = round(float(req["amount"]), 2)
    plan = req["plan"]
    req_type = req.get("type", "new_deposit")

    user_balance = data.get("user_balance", {})
    user_deposits = data.get("user_deposits", {})
    user_plans = data.get("user_plans", {})
    user_last_profit = data.get("user_last_profit", {})
    user_first_deposit_time = data.get("user_first_deposit_time", {})
    user_deposit_logs = data.get("user_deposit_logs", {})
    transactions = data.get("transactions", {})

    if req_type == "topup_deposit":
        old_capital = round(float(user_deposits.get(username, 0)), 2)
        old_balance = round(float(user_balance.get(username, 0)), 2)

        user_deposits[username] = round(old_capital + amount, 2)
        user_balance[username] = round(old_balance + amount, 2)

        user_deposit_logs.setdefault(username, []).append({
            "amount": amount,
            "time": now_str(),
            "status": "approved",
            "type": "topup_deposit",
            "note": "تمت الموافقة على إيداع جديد من لوحة الويب"
        })

        transactions.setdefault(username, []).append({
            "type": "topup_deposit_approved",
            "amount": amount,
            "note": "إيداع جديد من لوحة الويب",
            "time": now_str()
        })

    elif req_type == "plan_change":
        old_plan = req.get("old_plan", user_plans.get(username, "NONE"))
        new_plan = req.get("new_plan", plan)

        user_balance[username] = round(float(user_balance.get(username, 0)) + amount, 2)
        user_deposits[username] = round(float(user_deposits.get(username, 0)) + amount, 2)
        user_plans[username] = new_plan
        user_last_profit[username] = time.time()

        transactions.setdefault(username, []).append({
            "type": "plan_change_approved",
            "amount": amount,
            "note": f"تغيير الباقة من {old_plan} إلى {new_plan} من لوحة الويب",
            "time": now_str()
        })

    else:
        user_balance[username] = amount
        user_deposits[username] = amount
        user_plans[username] = plan
        user_last_profit[username] = time.time()

        if username not in user_first_deposit_time:
            user_first_deposit_time[username] = time.time()

        user_deposit_logs.setdefault(username, []).append({
            "amount": amount,
            "time": now_str(),
            "status": "approved",
            "type": "new_deposit",
            "note": f"تمت الموافقة على إيداع وتفعيل {plan} من لوحة الويب"
        })

        transactions.setdefault(username, []).append({
            "type": "deposit_approved",
            "amount": amount,
            "note": f"تفعيل {plan} من لوحة الويب",
            "time": now_str()
        })

    pending.pop(str(user_id), None)
    pending.pop(user_id, None)

    data["pending_deposit_requests"] = pending
    data["user_balance"] = user_balance
    data["user_deposits"] = user_deposits
    data["user_plans"] = user_plans
    data["user_last_profit"] = user_last_profit
    data["user_first_deposit_time"] = user_first_deposit_time
    data["user_deposit_logs"] = user_deposit_logs
    data["transactions"] = transactions

    db_set("data", data)

    return {
        "success": True,
        "message": "Deposit approved successfully",
        "username": username,
        "amount": amount
    }


@router.post("/reject-deposit")
def reject_deposit(
    request: DepositActionRequest,
    admin: str = Depends(get_current_admin)
):
    data = db_get("data", {})
    user_id = request.user_id

    pending = data.get("pending_deposit_requests", {})
    req = pending.get(str(user_id)) or pending.get(user_id)

    if not req:
        raise HTTPException(status_code=404, detail="Deposit request not found")

    username = req.get("username")
    amount = round(float(req.get("amount", 0)), 2)
    req_type = req.get("type", "new_deposit")

    user_deposit_logs = data.get("user_deposit_logs", {})
    transactions = data.get("transactions", {})

    if username:
        user_deposit_logs.setdefault(username, []).append({
            "amount": amount,
            "time": now_str(),
            "status": "rejected",
            "type": req_type,
            "note": "تم رفض طلب الإيداع من لوحة الويب"
        })

        transactions.setdefault(username, []).append({
            "type": "deposit_rejected",
            "amount": amount,
            "note": "تم رفض طلب الإيداع من لوحة الويب",
            "time": now_str()
        })

    pending.pop(str(user_id), None)
    pending.pop(user_id, None)

    data["pending_deposit_requests"] = pending
    data["user_deposit_logs"] = user_deposit_logs
    data["transactions"] = transactions

    db_set("data", data)

    return {
        "success": True,
        "message": "Deposit rejected successfully",
        "username": username,
        "amount": amount
    }

@router.get("/pending-withdraws")
def get_pending_withdraws(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})

    pending_withdraw_requests = data.get("pending_withdraw_requests", {})

    result = []

    for user_id, request in pending_withdraw_requests.items():
        result.append({
            "user_id": user_id,
            "username": request.get("username", "غير معروف"),
            "plan": request.get("plan", "غير معروف"),
            "amount": request.get("amount", 0),
            "time": request.get("time", "غير متوفر"),
            "type": request.get("type", "profit_only"),
            "withdraw_wallet_address": request.get("withdraw_wallet_address", "غير متوفر"),
            "withdraw_wallet_network": request.get("withdraw_wallet_network", "غير متوفر"),
            "saved_wallet_address": request.get("saved_wallet_address", "غير متوفر"),
            "saved_wallet_network": request.get("saved_wallet_network", "غير متوفر"),
            "wallets_match_result": request.get("wallets_match_result", "غير متوفر")
        })

    return {
        "count": len(result),
        "pending_withdraws": result
    }

@router.post("/approve-withdraw")
def approve_withdraw(
    request: DepositActionRequest,
    admin: str = Depends(get_current_admin)
):
    data = db_get("data", {})
    user_id = request.user_id

    pending = data.get("pending_withdraw_requests", {})
    req = pending.get(str(user_id)) or pending.get(user_id)

    if not req:
        raise HTTPException(status_code=404, detail="Withdraw request not found")

    username = req["username"]
    amount = round(float(req["amount"]), 2)

    user_balance = data.get("user_balance", {})
    user_deposits = data.get("user_deposits", {})
    user_withdraw_logs = data.get("user_withdraw_logs", {})
    transactions = data.get("transactions", {})
    user_last_withdraw_time = data.get("user_last_withdraw_time", {})

    current_balance = round(float(user_balance.get(username, 0)), 2)
    capital = round(float(user_deposits.get(username, 0)), 2)

    max_profit_available = round(current_balance - capital, 2)

    if max_profit_available < 0:
        max_profit_available = 0

    amount = min(amount, max_profit_available)

    if amount <= 0:
        raise HTTPException(status_code=400, detail="No available profit to withdraw")

    user_balance[username] = round(current_balance - amount, 2)
    user_last_withdraw_time[username] = time.time()

    manual_withdraw_open = data.get("manual_withdraw_open", {})
    manual_withdraw_open.pop(username, None)

    user_withdraw_logs.setdefault(username, []).append({
        "amount": amount,
        "time": now_str(),
        "status": "approved",
        "note": "تمت الموافقة على سحب الأرباح من لوحة الويب"
    })

    transactions.setdefault(username, []).append({
        "type": "withdraw_approved",
        "amount": amount,
        "note": "تمت الموافقة على سحب الأرباح من لوحة الويب",
        "time": now_str()
    })

    pending.pop(str(user_id), None)
    pending.pop(user_id, None)

    data["pending_withdraw_requests"] = pending
    data["user_balance"] = user_balance
    data["user_last_withdraw_time"] = user_last_withdraw_time
    data["manual_withdraw_open"] = manual_withdraw_open
    data["user_withdraw_logs"] = user_withdraw_logs
    data["transactions"] = transactions

    db_set("data", data)

    return {
        "success": True,
        "message": "Withdraw approved successfully",
        "username": username,
        "amount": amount
    }


@router.post("/reject-withdraw")
def reject_withdraw(
    request: DepositActionRequest,
    admin: str = Depends(get_current_admin)
):
    data = db_get("data", {})
    user_id = request.user_id

    pending = data.get("pending_withdraw_requests", {})
    req = pending.get(str(user_id)) or pending.get(user_id)

    if not req:
        raise HTTPException(status_code=404, detail="Withdraw request not found")

    username = req["username"]
    amount = round(float(req.get("amount", 0)), 2)

    user_withdraw_logs = data.get("user_withdraw_logs", {})
    transactions = data.get("transactions", {})

    user_withdraw_logs.setdefault(username, []).append({
        "amount": amount,
        "time": now_str(),
        "status": "rejected",
        "note": "تم رفض طلب سحب الأرباح من لوحة الويب"
    })

    transactions.setdefault(username, []).append({
        "type": "withdraw_rejected",
        "amount": amount,
        "note": "تم رفض طلب سحب الأرباح من لوحة الويب",
        "time": now_str()
    })

    pending.pop(str(user_id), None)
    pending.pop(user_id, None)

    data["pending_withdraw_requests"] = pending
    data["user_withdraw_logs"] = user_withdraw_logs
    data["transactions"] = transactions

    db_set("data", data)

    return {
        "success": True,
        "message": "Withdraw rejected successfully",
        "username": username,
        "amount": amount
    }

@router.get("/capital-withdraws")
def get_capital_withdraws(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})

    capital_withdraw_requests = data.get("capital_withdraw_requests", {})

    result = []

    for user_id, request in capital_withdraw_requests.items():
        result.append({
            "user_id": user_id,
            "username": request.get("username", "غير معروف"),
            "amount": request.get("amount", 0),
            "request_time": request.get("request_time", "غير متوفر"),
            "due_time": request.get("due_time", "غير متوفر"),
            "wallet": request.get("wallet", "غير محفوظة"),
            "network": request.get("network", "غير محفوظة"),
            "admin_notified": request.get("admin_notified", False)
        })

    return {
        "count": len(result),
        "capital_withdraws": result
    }

@router.post("/capital-paid")
def capital_paid(
    request: DepositActionRequest,
    admin: str = Depends(get_current_admin)
):
    data = db_get("data", {})
    user_id = request.user_id

    capital_requests = data.get("capital_withdraw_requests", {})
    req = capital_requests.get(str(user_id)) or capital_requests.get(user_id)

    if not req:
        raise HTTPException(status_code=404, detail="Capital withdraw request not found")

    username = req.get("username")
    amount = round(float(req.get("amount", 0)), 2)

    user_balance = data.get("user_balance", {})
    user_deposits = data.get("user_deposits", {})
    user_plans = data.get("user_plans", {})
    user_last_profit = data.get("user_last_profit", {})
    transactions = data.get("transactions", {})
    stopped_profit_users = data.get("stopped_profit_users", {})

    user_balance[username] = 0
    user_deposits[username] = 0
    user_plans[username] = "NONE"
    user_last_profit[username] = time.time()

    stopped_profit_users.pop(username, None)

    capital_requests.pop(str(user_id), None)
    capital_requests.pop(user_id, None)

    transactions.setdefault(username, []).append({
        "type": "capital_withdraw_paid",
        "amount": amount,
        "note": "تم دفع سحب رأس المال وإغلاق الباقة من لوحة الويب",
        "time": now_str()
    })

    data["user_balance"] = user_balance
    data["user_deposits"] = user_deposits
    data["user_plans"] = user_plans
    data["user_last_profit"] = user_last_profit
    data["transactions"] = transactions
    data["stopped_profit_users"] = stopped_profit_users
    data["capital_withdraw_requests"] = capital_requests

    db_set("data", data)

    return {
        "success": True,
        "message": "Capital withdraw paid successfully",
        "username": username,
        "amount": amount
    }

@router.get("/verification-requests")
def get_verification_requests(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})

    pending_verification_requests = data.get("pending_verification_requests", {})

    result = []

    for user_id, request in pending_verification_requests.items():
        result.append({
            "user_id": user_id,
            "username": request.get("username", "غير معروف"),
            "full_name": request.get("full_name", "غير متوفر"),
            "residence": request.get("residence", "غير متوفر"),
            "timezone": request.get("timezone", "Europe/Vienna"),
            "telegram_first_name": request.get("telegram_first_name", "غير متوفر"),
            "telegram_username": request.get("telegram_username", "لا يوجد"),
            "telegram_id": request.get("telegram_id", user_id),
            "time": request.get("time", "غير متوفر"),
            "front_id_file_id": request.get("front_id_file_id"),
            "back_id_file_id": request.get("back_id_file_id"),
            "front_id_url": build_telegram_file_url(request.get("front_id_file_id")),
            "back_id_url": build_telegram_file_url(request.get("back_id_file_id"))
        })

    return {
        "count": len(result),
        "verification_requests": result
    }

@router.get("/telegram-file/{file_id}")
def get_telegram_file(
    file_id: str,
    admin: str = Depends(get_current_admin)
):
    file_url = build_telegram_file_url(file_id)

    if not file_url:
        raise HTTPException(status_code=404, detail="File not found")

    return RedirectResponse(file_url)