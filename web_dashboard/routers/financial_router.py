from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import json
import os
import time
import requests

from web_dashboard.auth import get_current_admin
from web_dashboard.services.storage_service import web_db_get as db_get
from web_dashboard.database import get_web_db_connection, release_web_db_connection
from web_dashboard.config import ADMIN_ID, BOT_TOKEN

router = APIRouter()
ENABLE_FULL_DATA_BACKUP = os.getenv("ENABLE_FULL_DATA_BACKUP", "false").lower() in ("1", "true", "yes", "on")


class UserIdRequest(BaseModel):
    user_id: int


class UsernameRequest(BaseModel):
    username: str


class MessageRequest(BaseModel):
    message: str


class PrivateMessageRequest(BaseModel):
    username: str
    message: str


class PlanMessageRequest(BaseModel):
    plan: str
    message: str

class AddWalletRequest(BaseModel):
    username: str
    wallet_address: str
    wallet_network: str

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


def save_data(data):
    critical_keys = [
        "user_plans",
        "user_balance",
        "user_deposits",
        "user_telegram_ids",
        "verified_users",
    ]

    critical_items_count = sum(
        len(data.get(key, {}))
        for key in critical_keys
        if isinstance(data.get(key, {}), dict)
    )

    if critical_items_count == 0:
        users = db_get("users", {})
        if isinstance(users, dict) and users:
            raise HTTPException(status_code=500, detail="Refusing to save empty critical data while users exist")

    if ENABLE_FULL_DATA_BACKUP:
        existing_data = db_get("data", {})
        if isinstance(existing_data, dict) and existing_data:
            db_set("data_backup_before_last_save", existing_data)
    db_set("data", data)


def save_users(users):
    db_set("users", users)


def add_transaction(data, username, tx_type, amount=0, note=""):
    transactions = data.get("transactions", {})
    transactions.setdefault(username, []).append({
        "type": tx_type,
        "amount": round(float(amount), 2),
        "note": note,
        "time": now_str()
    })
    data["transactions"] = transactions


def add_user_system_notification(data, username, title, message, notification_type="system"):
    notifications = data.get("user_system_notifications", {})

    if not isinstance(notifications, dict):
        notifications = {}

    notifications.setdefault(username, []).append({
        "title": title,
        "message": message,
        "type": notification_type,
        "time": now_str(),
        "read": False,
        "notification_cleared": False
    })

    notifications[username] = notifications[username][-200:]
    data["user_system_notifications"] = notifications


def send_telegram(chat_id, text):
    if not BOT_TOKEN or not chat_id:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": int(chat_id), "text": text},
            timeout=10
        )
        return bool(r.json().get("ok"))
    except Exception:
        return False


def send_telegram_photo(chat_id, file_bytes, caption=""):
    if not BOT_TOKEN or not chat_id:
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": int(chat_id),
                "caption": caption or ""
            },
            files={
                "photo": ("image.jpg", file_bytes)
            },
            timeout=30
        )

        return bool(response.json().get("ok"))

    except Exception as e:
        print(f"[SEND_TELEGRAM_PHOTO_ERROR] {e}")
        return False


def send_telegram_document(chat_id, file_bytes, filename, caption=""):
    if not BOT_TOKEN or not chat_id:
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
            data={
                "chat_id": int(chat_id),
                "caption": caption or ""
            },
            files={
                "document": (filename, file_bytes)
            },
            timeout=30
        )

        return bool(response.json().get("ok"))

    except Exception as e:
        print(f"[SEND_TELEGRAM_DOCUMENT_ERROR] {e}")
        return False

def send_telegram_media(chat_id, file_bytes, filename, caption=""):
    if not BOT_TOKEN or not chat_id:
        return False

    filename_lower = filename.lower()

    if filename_lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {
            "photo": (filename, file_bytes)
        }
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        files = {
            "document": (filename, file_bytes)
        }

    try:
        response = requests.post(
            url,
            data={
                "chat_id": int(chat_id),
                "caption": caption or ""
            },
            files=files,
            timeout=30
        )

        result = response.json()
        return bool(result.get("ok"))

    except Exception as e:
        print(f"[SEND_TELEGRAM_MEDIA_ERROR] {e}")
        return False

def get_tg_id(data, username):
    tg_id = data.get("user_telegram_ids", {}).get(username)
    try:
        return int(tg_id) if tg_id is not None else None
    except Exception:
        return None


def build_telegram_file_url(file_id):
    if not file_id or not BOT_TOKEN:
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
        return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{result['result']['file_path']}"
    except Exception:
        return None


@router.get("/pending-deposits")
def get_pending_deposits(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    result = []
    for user_id, request in data.get("pending_deposit_requests", {}).items():
        proof_file_id = request.get("proof_file_id")

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
    "final_capital": request.get("final_capital"),

    # صورة إثبات الدفع من لوحة المستخدم Web
    "proof_image_base64": request.get("proof_image_base64"),

    # صورة إثبات الدفع من بوت تيليغرام
    "proof_file_id": proof_file_id,
    "proof_image_url": build_telegram_file_url(proof_file_id)
      })
    return {"count": len(result), "pending_deposits": result}

@router.post("/add-wallet")
def add_wallet_to_user(
    request: AddWalletRequest,
    admin: str = Depends(get_current_admin)
):
    data = db_get("data", {})
    users = db_get("users", {})

    username = request.username.strip()
    wallet_address = request.wallet_address.strip()
    wallet_network = request.wallet_network.strip()

    if not username:
        raise HTTPException(status_code=400, detail="اسم المستخدم غير موجود")

    if username not in users:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if not wallet_address:
        raise HTTPException(status_code=400, detail="أدخل عنوان محفظة صحيح")

    if not wallet_network:
        raise HTTPException(status_code=400, detail="أدخل اسم شبكة صحيح")

    user_wallet_address = data.get("user_wallet_address", {})
    user_wallet_network = data.get("user_wallet_network", {})

    user_wallet_address[username] = wallet_address
    user_wallet_network[username] = wallet_network

    data["user_wallet_address"] = user_wallet_address
    data["user_wallet_network"] = user_wallet_network

    db_set("data", data)

    return {
        "success": True,
        "username": username,
        "wallet_address": wallet_address,
        "wallet_network": wallet_network
    }


@router.post("/approve-deposit")
def approve_deposit(request: UserIdRequest, admin: str = Depends(get_current_admin)):
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

    if req_type == "topup_deposit":
        user_deposits[username] = round(float(user_deposits.get(username, 0)) + amount, 2)
        user_balance[username] = round(float(user_balance.get(username, 0)) + amount, 2)
        log_type = "topup_deposit"
        tx_type = "topup_deposit_approved"
        note = "إيداع جديد من لوحة الويب"
    elif req_type == "plan_change":
        old_plan = req.get("old_plan", user_plans.get(username, "NONE"))
        new_plan = req.get("new_plan", plan)
        user_balance[username] = round(float(user_balance.get(username, 0)) + amount, 2)
        user_deposits[username] = round(float(user_deposits.get(username, 0)) + amount, 2)
        user_plans[username] = new_plan
        user_last_profit[username] = time.time()
        log_type = "plan_change"
        tx_type = "plan_change_approved"
        note = f"تغيير الباقة من {old_plan} إلى {new_plan} من لوحة الويب"
    else:
        user_balance[username] = amount
        user_deposits[username] = amount
        user_plans[username] = plan
        user_last_profit[username] = time.time()
        if username not in user_first_deposit_time:
            user_first_deposit_time[username] = time.time()
        log_type = "new_deposit"
        tx_type = "deposit_approved"
        note = f"تفعيل {plan} من لوحة الويب"

    user_deposit_logs.setdefault(username, []).append({
        "amount": amount,
        "time": now_str(),
        "status": "approved",
        "type": log_type,
        "note": note
    })

    data["user_balance"] = user_balance
    data["user_deposits"] = user_deposits
    data["user_plans"] = user_plans
    data["user_last_profit"] = user_last_profit
    data["user_first_deposit_time"] = user_first_deposit_time
    data["user_deposit_logs"] = user_deposit_logs
    add_transaction(data, username, tx_type, amount, note)

    pending.pop(str(user_id), None)
    pending.pop(user_id, None)
    data["pending_deposit_requests"] = pending

    save_data(data)
    send_telegram(user_id, f"✅ تمت الموافقة على الإيداع بقيمة {amount}$")
    return {"success": True, "username": username, "amount": amount}


@router.post("/reject-deposit")
def reject_deposit(request: UserIdRequest, admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    pending = data.get("pending_deposit_requests", {})
    req = pending.get(str(request.user_id)) or pending.get(request.user_id)
    if not req:
        raise HTTPException(status_code=404, detail="Deposit request not found")
    username = req.get("username")
    amount = round(float(req.get("amount", 0)), 2)
    data.setdefault("user_deposit_logs", {}).setdefault(username, []).append({
        "amount": amount,
        "time": now_str(),
        "status": "rejected",
        "type": req.get("type", "new_deposit"),
        "note": "تم رفض طلب الإيداع من لوحة الويب"
    })
    add_transaction(data, username, "deposit_rejected", amount, "تم رفض طلب الإيداع من لوحة الويب")
    pending.pop(str(request.user_id), None)
    pending.pop(request.user_id, None)
    data["pending_deposit_requests"] = pending
    save_data(data)
    send_telegram(request.user_id, "❌ تم رفض طلب الإيداع")
    return {"success": True, "username": username, "amount": amount}


@router.get("/pending-withdraws")
def get_pending_withdraws(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    result = []
    for user_id, request in data.get("pending_withdraw_requests", {}).items():
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
    return {"count": len(result), "pending_withdraws": result}


@router.post("/approve-withdraw")
def approve_withdraw(request: UserIdRequest, admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    pending = data.get("pending_withdraw_requests", {})
    req = pending.get(str(request.user_id)) or pending.get(request.user_id)
    if not req:
        raise HTTPException(status_code=404, detail="Withdraw request not found")

    username = req["username"]
    amount = round(float(req["amount"]), 2)
    user_balance = data.get("user_balance", {})
    user_deposits = data.get("user_deposits", {})
    current_balance = round(float(user_balance.get(username, 0)), 2)
    capital = round(float(user_deposits.get(username, 0)), 2)
    max_profit = max(round(current_balance - capital, 2), 0)
    amount = min(amount, max_profit)

    if amount <= 0:
        raise HTTPException(status_code=400, detail="No available profit to withdraw")

    user_balance[username] = round(current_balance - amount, 2)
    data["user_balance"] = user_balance
    data.setdefault("user_last_withdraw_time", {})[username] = time.time()
    data.setdefault("manual_withdraw_open", {}).pop(username, None)
    data.setdefault("user_withdraw_logs", {}).setdefault(username, []).append({
        "amount": amount,
        "time": now_str(),
        "status": "approved",
        "note": "تمت الموافقة على سحب الأرباح من لوحة الويب"
    })
    add_transaction(data, username, "withdraw_approved", amount, "تمت الموافقة على سحب الأرباح من لوحة الويب")
    pending.pop(str(request.user_id), None)
    pending.pop(request.user_id, None)
    data["pending_withdraw_requests"] = pending
    save_data(data)
    send_telegram(request.user_id, f"✅ تمت الموافقة على طلب السحب بقيمة {amount}$")
    return {"success": True, "username": username, "amount": amount}


@router.post("/reject-withdraw")
def reject_withdraw(request: UserIdRequest, admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    pending = data.get("pending_withdraw_requests", {})
    req = pending.get(str(request.user_id)) or pending.get(request.user_id)
    if not req:
        raise HTTPException(status_code=404, detail="Withdraw request not found")
    username = req["username"]
    amount = round(float(req.get("amount", 0)), 2)
    data.setdefault("user_withdraw_logs", {}).setdefault(username, []).append({
        "amount": amount,
        "time": now_str(),
        "status": "rejected",
        "note": "تم رفض طلب سحب الأرباح من لوحة الويب"
    })
    add_transaction(data, username, "withdraw_rejected", amount, "تم رفض طلب سحب الأرباح من لوحة الويب")
    pending.pop(str(request.user_id), None)
    pending.pop(request.user_id, None)
    data["pending_withdraw_requests"] = pending
    save_data(data)
    send_telegram(request.user_id, "❌ تم رفض طلب سحب الأرباح")
    return {"success": True, "username": username, "amount": amount}


@router.get("/capital-withdraws")
def get_capital_withdraws(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    result = []
    for user_id, request in data.get("capital_withdraw_requests", {}).items():
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
    return {"count": len(result), "capital_withdraws": result}


@router.post("/capital-paid")
def capital_paid(request: UserIdRequest, admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    capital_requests = data.get("capital_withdraw_requests", {})
    req = capital_requests.get(str(request.user_id)) or capital_requests.get(request.user_id)
    if not req:
        raise HTTPException(status_code=404, detail="Capital withdraw request not found")

    username = req.get("username")
    amount = round(float(req.get("amount", 0)), 2)

    data.setdefault("user_balance", {})[username] = 0
    data.setdefault("user_deposits", {})[username] = 0
    data.setdefault("user_plans", {})[username] = "NONE"
    data.setdefault("user_last_profit", {})[username] = time.time()
    data.setdefault("stopped_profit_users", {}).pop(username, None)
    capital_requests.pop(str(request.user_id), None)
    capital_requests.pop(request.user_id, None)
    data["capital_withdraw_requests"] = capital_requests
    add_transaction(data, username, "capital_withdraw_paid", amount, "تم دفع سحب رأس المال وإغلاق الباقة من لوحة الويب")
    save_data(data)
    send_telegram(request.user_id, f"✅ تم دفع سحب رأس المال بقيمة {amount}$ وإغلاق الباقة")
    return {"success": True, "username": username, "amount": amount}


@router.get("/verification-requests")
def get_verification_requests(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    result = []
    for user_id, request in data.get("pending_verification_requests", {}).items():
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
            "front_id_url": build_telegram_file_url(request.get("front_id_file_id")) or request.get("front_image_base64"),
            "back_id_url": build_telegram_file_url(request.get("back_id_file_id")) or request.get("back_image_base64"),
        })
    return {"count": len(result), "verification_requests": result}


@router.post("/approve-verification")
def approve_verification(request: UserIdRequest, admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    pending = data.get("pending_verification_requests", {})
    req = pending.get(str(request.user_id)) or pending.get(request.user_id)
    if not req:
        raise HTTPException(status_code=404, detail="Verification request not found")

    username = req["username"]
    data.setdefault("verified_users", {})[username] = True
    data.setdefault("user_full_name", {})[username] = req.get("full_name", "")
    data.setdefault("user_residence", {})[username] = req.get("residence", "")
    if req.get("timezone"):
        data.setdefault("user_timezone", {})[username] = req.get("timezone")
    if req.get("front_id_file_id") or req.get("back_id_file_id"):
        data.setdefault("user_identity_photos", {})[username] = {
            "front_id_file_id": req.get("front_id_file_id"),
            "back_id_file_id": req.get("back_id_file_id"),
            "updated_at": now_str()
        }

    pending.pop(str(request.user_id), None)
    pending.pop(request.user_id, None)
    data["pending_verification_requests"] = pending
    add_transaction(data, username, "verification_approved", 0, "تمت الموافقة على التوثيق من لوحة الويب")
    save_data(data)
    send_telegram(request.user_id, "✅ تمت الموافقة على توثيق حسابك")
    return {"success": True, "username": username}


@router.post("/reject-verification")
def reject_verification(request: UserIdRequest, admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    pending = data.get("pending_verification_requests", {})
    req = pending.get(str(request.user_id)) or pending.get(request.user_id)
    if not req:
        raise HTTPException(status_code=404, detail="Verification request not found")
    username = req["username"]
    pending.pop(str(request.user_id), None)
    pending.pop(request.user_id, None)
    data["pending_verification_requests"] = pending
    add_transaction(data, username, "verification_rejected", 0, "تم رفض التوثيق من لوحة الويب")
    save_data(data)
    send_telegram(request.user_id, "❌ تم رفض طلب توثيق الحساب")
    return {"success": True, "username": username}


@router.post("/toggle-subscriptions")
def toggle_subscriptions(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    data["subscriptions_open"] = not bool(data.get("subscriptions_open", True))
    save_data(data)
    return {"success": True, "subscriptions_open": data["subscriptions_open"]}


@router.post("/toggle-maintenance")
def toggle_maintenance(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    data["bot_maintenance_mode"] = not bool(data.get("bot_maintenance_mode", False))
    save_data(data)
    return {"success": True, "bot_maintenance_mode": data["bot_maintenance_mode"]}


@router.post("/toggle-support-employees")
def toggle_support_employees(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    data["support_employees_enabled"] = not bool(data.get("support_employees_enabled", False))
    save_data(data)
    return {"success": True, "support_employees_enabled": data["support_employees_enabled"]}


@router.get("/deleted-accounts")
def deleted_accounts(admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    items = data.get("deleted_accounts_log", [])
    return {"count": len(items), "deleted_accounts": list(reversed(items[-200:]))}


@router.post("/send-private-message")
def send_private_message(request: PrivateMessageRequest, admin: str = Depends(get_current_admin)):
    data = db_get("data", {})
    users = db_get("users", {})

    username = request.username.strip()

    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")

    tg_id = get_tg_id(data, username)

    if not tg_id:
        raise HTTPException(status_code=400, detail="Telegram ID not found")

    msg = request.message.replace("\\n", "\n")

    ok = send_telegram(
        tg_id,
        f"📨 رسالة من الإدارة:\n\n{msg}"
    )

    if ok:
        add_user_system_notification(
            data,
            username,
            "رسالة من الإدارة",
            msg,
            "private_message"
        )

    add_transaction(
        data,
        username,
        "admin_private_message",
        0,
        f"رسالة من لوحة الويب: {request.message[:80]}"
    )

    save_data(data)

    return {"success": ok}


@router.post("/broadcast")
def broadcast(request: MessageRequest, admin: str = Depends(get_current_admin)):
    chat_ids = db_get("chat_ids", [])
    data = db_get("data", {})

    msg = request.message.replace("\\n", "\n")

    success = 0
    failed = 0

    telegram_to_username = {
        str(tg_id): username
        for username, tg_id in data.get("user_telegram_ids", {}).items()
    }

    for uid in chat_ids:
        if send_telegram(uid, msg):
            success += 1
            username = telegram_to_username.get(str(uid))
            if username:
                add_user_system_notification(
                    data,
                    username,
                    "رسالة نظام",
                    msg,
                    "broadcast"
                )
        else:
            failed += 1

    save_data(data)

    return {
        "success": True,
        "sent": success,
        "failed": failed
    }
from fastapi import UploadFile, File, Form

@router.post("/broadcast-media-legacy", include_in_schema=False)
async def broadcast_media_legacy(
    caption: str = Form(""),
    file: UploadFile = File(...),
    admin: str = Depends(get_current_admin)
):
    chat_ids = db_get("chat_ids", [])

    success = 0
    failed = 0

    file_bytes = await file.read()

    for uid in chat_ids:
        try:
            if file.content_type.startswith("image"):
                send_telegram_photo(uid, file_bytes, caption)
            else:
                send_telegram_document(uid, file_bytes, file.filename, caption)

            success += 1
        except:
            failed += 1

    return {
        "success": True,
        "sent": success,
        "failed": failed
    }

@router.post("/broadcast-media")
async def broadcast_media(
    caption: str = Form(""),
    file: UploadFile = File(...),
    admin: str = Depends(get_current_admin)
):
    chat_ids = db_get("chat_ids", [])
    data = db_get("data", {})

    file_bytes = await file.read()
    caption = caption.replace("\\n", "\n")
    notification_message = caption or file.filename or "ملف من الإدارة"
    telegram_to_username = {
        str(tg_id): username
        for username, tg_id in data.get("user_telegram_ids", {}).items()
    }

    success = 0
    failed = 0

    for uid in chat_ids:
        if send_telegram_media(uid, file_bytes, file.filename, caption):
            success += 1
            username = telegram_to_username.get(str(uid))
            if username:
                add_user_system_notification(
                    data,
                    username,
                    "مرفق من الإدارة",
                    notification_message,
                    "broadcast_media"
                )
        else:
            failed += 1

    save_data(data)

    return {
        "success": True,
        "sent": success,
        "failed": failed
    }


@router.post("/plan-message")
def plan_message(request: PlanMessageRequest, admin: str = Depends(get_current_admin)):
    data = db_get("data", {})

    target_users = [
        username
        for username, plan in data.get("user_plans", {}).items()
        if plan == request.plan
    ]

    msg = request.message.replace("\\n", "\n")

    success = 0
    failed = 0

    for username in target_users:
        tg_id = get_tg_id(data, username)

        if send_telegram(
            tg_id,
            f"📨 رسالة من الإدارة لمشتركي {request.plan}:\n\n{msg}"
        ):
            success += 1
            add_user_system_notification(
                data,
                username,
                f"رسالة من الإدارة لمشتركي {request.plan}",
                msg,
                "plan_message"
            )
        else:
            failed += 1

    save_data(data)

    return {
        "success": True,
        "sent": success,
        "failed": failed
    }

@router.post("/plan-message-media")
async def plan_message_media(
    plan: str = Form(...),
    caption: str = Form(""),
    file: UploadFile = File(...),
    admin: str = Depends(get_current_admin)
):
    data = db_get("data", {})

    target_users = [
        username
        for username, user_plan in data.get("user_plans", {}).items()
        if user_plan == plan
    ]

    file_bytes = await file.read()
    caption = caption.replace("\\n", "\n")

    final_caption = (
        f"📨 رسالة من الإدارة لمشتركي {plan}:\n\n{caption}"
        if caption
        else f"📨 رسالة من الإدارة لمشتركي {plan}"
    )

    success = 0
    failed = 0

    for username in target_users:
        tg_id = get_tg_id(data, username)

        if send_telegram_media(tg_id, file_bytes, file.filename, final_caption):
            success += 1
            add_user_system_notification(
                data,
                username,
                f"مرفق من الإدارة لمشتركي {plan}",
                caption or file.filename or "ملف من الإدارة",
                "plan_message_media"
            )
        else:
            failed += 1

    save_data(data)

    return {
        "success": True,
        "sent": success,
        "failed": failed
    }


@router.post("/delete-user")
def delete_user(request: UsernameRequest, admin: str = Depends(get_current_admin)):
    username = request.username.strip()
    users = db_get("users", {})
    data = db_get("data", {})
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = get_tg_id(data, username)
    balance = round(float(data.get("user_balance", {}).get(username, 0)), 2)
    capital = round(float(data.get("user_deposits", {}).get(username, 0)), 2)

    deleted_accounts_log = data.get("deleted_accounts_log", [])
    deleted_accounts_log.append({
        "username": username,
        "telegram_id": user_id,
        "full_name": data.get("user_full_name", {}).get(username, "غير متوفر"),
        "residence": data.get("user_residence", {}).get(username, "غير متوفر"),
        "status_before_delete": data.get("user_statuses", {}).get(username, "active"),
        "plan_before_delete": data.get("user_plans", {}).get(username, "NONE"),
        "capital_before_delete": capital,
        "balance_before_delete": balance,
        "profit_only_before_delete": max(round(balance - capital, 2), 0),
        "deleted_at": now_str(),
        "source": "web_admin_dashboard"
    })
    data["deleted_accounts_log"] = deleted_accounts_log[-1000:]

    keys_by_username = [
        "user_plans", "user_balance", "transactions", "user_deposits", "user_last_profit",
        "user_withdraw_logs", "user_deposit_logs", "user_statuses", "support_blocked_users",
        "user_first_deposit_time", "user_last_withdraw_time", "user_telegram_ids",
        "user_residence", "user_full_name", "verified_users", "user_referrer",
        "referral_bonus_paid", "stopped_profit_users", "support_waiting_reply",
        "manual_withdraw_open", "user_created_time", "user_wallet_address",
        "user_wallet_network", "user_identity_photos", "user_timezone",
        "pending_profit_capital_activation", "web_identity_images"
    ]
    for key in keys_by_username:
        item = data.get(key, {})
        if isinstance(item, dict):
            item.pop(username, None)
            data[key] = item

    if user_id:
        for key in ["pending_deposit_requests", "pending_withdraw_requests", "capital_withdraw_requests", "pending_verification_requests", "logged_in_users"]:
            item = data.get(key, {})
            if isinstance(item, dict):
                item.pop(str(user_id), None)
                item.pop(user_id, None)
                data[key] = item

    for child, parent in list(data.get("user_referrer", {}).items()):
        if parent == username:
            data["user_referrer"].pop(child, None)

    users.pop(username, None)
    save_users(users)
    save_data(data)
    return {"success": True, "username": username}


@router.get("/telegram-file/{file_id}")
def get_telegram_file(file_id: str, admin: str = Depends(get_current_admin)):
    file_url = build_telegram_file_url(file_id)
    if not file_url:
        raise HTTPException(status_code=404, detail="File not found")
    return RedirectResponse(file_url)
