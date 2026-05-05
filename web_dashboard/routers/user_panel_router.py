import json
import time
import requests
import base64
from datetime import datetime
from web_dashboard.config import ADMIN_ID, BOT_TOKEN

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from web_dashboard.database import get_web_db_connection, release_web_db_connection
from web_dashboard.routers.user_auth_router import get_current_user, hash_password, verify_password
from web_dashboard.services.storage_service import web_db_get as db_get


router = APIRouter()

PLANS = {
    "الباقة الفضية": {
        "name": "الفضية",
        "code": "silver",
        "min_deposit": 10,
        "max_deposit": 100,
        "profit": "2% يومياً",
        "withdraw_time": "كل 30 يوم",
        "withdraw_days": 30
    },
    "الباقة الذهبية": {
        "name": "الذهبية",
        "code": "gold",
        "min_deposit": 101,
        "max_deposit": 300,
        "profit": "2% يومياً",
        "withdraw_time": "كل 20 يوم",
        "withdraw_days": 20
    },
    "باقة VIP": {
        "name": "VIP",
        "code": "vip",
        "min_deposit": 301,
        "max_deposit": None,
        "profit": "2% يومياً",
        "withdraw_time": "كل 10 أيام",
        "withdraw_days": 10
    }
}


PLAN_CODE_MAP = {
    "silver": "الباقة الفضية",
    "gold": "الباقة الذهبية",
    "vip": "باقة VIP"
}

VERIFICATION_COUNTRIES = {
    "سويسرا",
    "إيطاليا",
    "إسبانيا",
    "اليونان",
    "بولندا",
    "التشيك",
    "رومانيا",
    "هنغاريا",
    "فنلندا",
    "قطر",
    "النمسا",
    "ألمانيا",
    "تركيا",
    "السعودية",
    "الإمارات",
    "العراق",
    "الأردن",
    "سوريا",
    "لبنان",
    "مصر",
    "فلسطين",
    "هولندا",
    "فرنسا",
    "بلجيكا",
    "السويد",
    "الدنمارك",
    "النرويج",
    "بريطانيا",
    "أمريكا - نيويورك",
    "كندا - تورونتو",
}


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def send_telegram_message(chat_id: int, text: str, reply_markup=None):
    if not BOT_TOKEN:
        return False

    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        if reply_markup:
            payload["reply_markup"] = reply_markup

        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10
        )

        result = response.json()
        return bool(result.get("ok"))

    except Exception as e:
        print(f"[TELEGRAM_SEND_ERROR] {e}")
        return False


def send_telegram_photo(chat_id, file_bytes, caption=""):
    if not BOT_TOKEN or not chat_id:
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": int(chat_id),
                "caption": caption or "",
                "parse_mode": "HTML"
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
                "caption": caption or "",
                "parse_mode": "HTML"
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

def send_telegram_media_to_admin(file_bytes: bytes, filename: str, caption: str = ""):
    if not BOT_TOKEN:
        return None

    mime_name = filename.lower()

    if mime_name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {
            "photo": (filename, file_bytes)
        }
        data = {
            "chat_id": ADMIN_ID,
            "caption": caption or "",
            "parse_mode": "HTML"
        }
        media_type = "photo"
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        files = {
            "document": (filename, file_bytes)
        }
        data = {
            "chat_id": ADMIN_ID,
            "caption": caption or "",
            "parse_mode": "HTML"
        }
        media_type = "document"

    response = requests.post(url, data=data, files=files, timeout=30)
    result = response.json()

    if not result.get("ok"):
        raise HTTPException(status_code=500, detail="فشل إرسال الملف إلى الدعم")

    message = result.get("result", {})

    if media_type == "photo":
        photos = message.get("photo", [])
        file_id = photos[-1]["file_id"] if photos else None
    else:
        file_id = message.get("document", {}).get("file_id")

    return {
        "type": media_type,
        "file_id": file_id,
        "filename": filename
    }

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
        raise HTTPException(status_code=500, detail=f"Database write error: {str(e)}")

    finally:
        if cur:
            cur.close()
        release_web_db_connection(conn)


def save_data(data):
    db_set("data", data)


def save_users(users):
    db_set("users", users)


def load_storage():
    users = db_get("users", {})
    data = db_get("data", {})

    if not isinstance(users, dict):
        raise HTTPException(status_code=500, detail="Invalid users storage")

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Invalid data storage")

    return users, data


def get_telegram_id(data, username):
    tg_id = data.get("user_telegram_ids", {}).get(username)

    if tg_id is None:
        return None

    try:
        return int(tg_id)
    except Exception:
        return None


def add_transaction(data, username, tx_type, amount=0, note=""):
    transactions = data.get("transactions", {})

    if username not in transactions or not isinstance(transactions.get(username), list):
        transactions[username] = []

    transactions[username].append({
        "type": tx_type,
        "amount": round(float(amount), 2),
        "note": note,
        "time": now_str()
    })

    data["transactions"] = transactions


def get_status(data, username):
    return data.get("user_statuses", {}).get(username, "active")


def get_capital(data, username):
    return round(float(data.get("user_deposits", {}).get(username, 0)), 2)


def get_balance(data, username):
    return round(float(data.get("user_balance", {}).get(username, 0)), 2)


def get_profit_only(data, username):
    profit = round(get_balance(data, username) - get_capital(data, username), 2)
    return profit if profit > 0 else 0


def get_next_profit_data(data, username):
    now_ts = time.time()

    last_profit = data.get("user_last_profit", {}).get(username)

    if last_profit is None:
        return None, None

    next_profit = float(last_profit) + 86400
    seconds = int(next_profit - now_ts)

    if seconds < 0:
        seconds = 0

    return next_profit, seconds


def get_next_withdraw_data(data, username):
    now_ts = time.time()

    plan_name = data.get("user_plans", {}).get(username)

    if plan_name not in PLANS:
        return None, None

    interval_days = PLANS[plan_name]["withdraw_days"]

    first_deposit = data.get("user_first_deposit_time", {}).get(username)
    last_withdraw = data.get("user_last_withdraw_time", {}).get(username)

    base_time = None

    if last_withdraw is not None:
        base_time = float(last_withdraw)
    elif first_deposit is not None:
        base_time = float(first_deposit)

    if base_time is None:
        return None, None

    next_withdraw = base_time + (interval_days * 86400)
    seconds = int(next_withdraw - now_ts)

    if seconds < 0:
        seconds = 0

    return next_withdraw, seconds


def is_withdraw_available(data, username):
    next_withdraw, seconds = get_next_withdraw_data(data, username)

    if next_withdraw is None:
        return False

    return time.time() >= float(next_withdraw)


def build_referral_link(data, username):
    tg_id = get_telegram_id(data, username)

    if not tg_id:
        return "غير متاح حتى يتم ربط حسابك بتليغرام"

    return f"https://t.me/Moneyfactory1bot?start=ref_{tg_id}"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class SupportRequest(BaseModel):
    message: str

class EmptyRequest(BaseModel):
    pass    


class DepositRequest(BaseModel):
    plan_code: str
    amount: float
    proof_image_base64: str | None = None


class WithdrawRequest(BaseModel):
    amount: float
    wallet_address: str
    wallet_network: str


class CapitalWithdrawRequest(BaseModel):
    wallet_address: str
    wallet_network: str


class VerificationRequest(BaseModel):
    full_name: str
    residence: str
    front_image_base64: str
    back_image_base64: str


class DeleteAccountRequest(BaseModel):
    password: str
    confirm_text: str


@router.get("/me")
def get_my_dashboard(username: str = Depends(get_current_user)):
    users, data = load_storage()

    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")

    plan = data.get("user_plans", {}).get(username, "NONE")
    status = get_status(data, username)
    verified = bool(data.get("verified_users", {}).get(username, False))

    capital = get_capital(data, username)
    balance = get_balance(data, username)
    profit_only = get_profit_only(data, username)

    next_profit_time, next_profit_seconds = get_next_profit_data(data, username)
    next_withdraw_time, withdraw_countdown_seconds = get_next_withdraw_data(data, username)

    user_referrer = data.get("user_referrer", {})
    children = [
        child for child, parent in user_referrer.items()
        if parent == username
    ]

    transactions = data.get("transactions", {}).get(username, [])
    deposits = data.get("user_deposit_logs", {}).get(username, [])
    withdraws = data.get("user_withdraw_logs", {}).get(username, [])

    return {
        "username": username,
        "telegram_id": get_telegram_id(data, username),
        "full_name": data.get("user_full_name", {}).get(username, "غير متوفر"),
        "residence": data.get("user_residence", {}).get(username, "غير متوفر"),
        "plan": plan,
        "status": status,
        "verified": verified,
        "capital": capital,
        "balance": balance,
        "profit_only": profit_only,
        "daily_profit": round(capital * 0.02, 2),
        "min_withdraw": round(capital * 0.20, 2),
        "next_profit_time": next_profit_time,
        "next_profit_seconds": next_profit_seconds,
        "next_withdraw_time": next_withdraw_time,
        "withdraw_countdown_seconds": withdraw_countdown_seconds,
        "withdraw_available": is_withdraw_available(data, username),
        "referral_link": build_referral_link(data, username),
        "children_count": len(children),
        "children": children,
        "transactions": transactions[-30:],
        "deposits": deposits[-20:],
        "withdraws": withdraws[-20:]
    }


@router.get("/plans")
def get_plans(username: str = Depends(get_current_user)):
    return {
        "plans": PLANS
    }


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    username: str = Depends(get_current_user)
):
    users, data = load_storage()

    stored_password = users.get(username)
    if not verify_password(stored_password, request.old_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    if len(request.new_password.strip()) < 3:
        raise HTTPException(status_code=400, detail="New password is too short")

    users[username] = hash_password(request.new_password.strip())

    add_transaction(
        data,
        username,
        "user_web_change_password",
        0,
        "قام المستخدم بتغيير كلمة المرور من لوحة الويب"
    )

    save_users(users)
    save_data(data)

    return {
        "success": True,
        "message": "Password changed successfully"
    }

@router.get("/support-messages")
def get_support_messages(username: str = Depends(get_current_user)):
    users, data = load_storage()

    support_chat_messages = data.get("support_chat_messages", {})
    messages = support_chat_messages.get(username, [])

    unread_count = sum(
        1 for msg in messages
        if msg.get("sender") == "support" and not msg.get("read", False)
    )

    return {
        "messages": messages[-50:],
        "unread_count": unread_count
    }

@router.post("/support-mark-read")
def mark_support_messages_read(username: str = Depends(get_current_user)):
    users, data = load_storage()

    support_chat_messages = data.get("support_chat_messages", {})
    messages = support_chat_messages.get(username, [])

    for msg in messages:
        if msg.get("sender") == "support":
            msg["read"] = True

    support_chat_messages[username] = messages
    data["support_chat_messages"] = support_chat_messages

    save_data(data)

    return {
        "success": True
    }


@router.post("/support")
def send_support_message(
    request: SupportRequest,
    username: str = Depends(get_current_user)
):
    users, data = load_storage()

    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message is empty")

    telegram_id = get_telegram_id(data, username)
    full_name = data.get("user_full_name", {}).get(username, "غير متوفر")
    residence = data.get("user_residence", {}).get(username, "غير متوفر")
    plan = data.get("user_plans", {}).get(username, "NONE")
    balance = get_balance(data, username)
    capital = get_capital(data, username)
    profit = get_profit_only(data, username)

    # منع المستخدم من إرسال أكثر من رسالة دعم قبل رد الإدارة
    support_waiting_reply = data.get("support_waiting_reply", {})

    if support_waiting_reply.get(username, False):
          raise HTTPException(
            status_code=400,
            detail="لديك رسالة دعم قيد الانتظار. يرجى انتظار رد الإدارة قبل إرسال رسالة جديدة."
          )

    support_waiting_reply[username] = True
    data["support_waiting_reply"] = support_waiting_reply

    support_opened_at = data.get("support_opened_at", {})
    support_opened_at.pop(username, None)
    data["support_opened_at"] = support_opened_at

    support_messages = data.get("web_support_messages", [])
    support_chat_messages = data.get("support_chat_messages", {})
    support_chat_messages.setdefault(username, []).append({
    "sender": "user",
    "message": message,
    "time": now_str(),
    "read": True
     })
    data["support_chat_messages"] = support_chat_messages

    support_messages.append({
        "username": username,
        "telegram_id": telegram_id,
        "full_name": full_name,
        "residence": residence,
        "plan": plan,
        "balance": balance,
        "capital": capital,
        "profit_only": profit,
        "message": message,
        "status": "sent_to_admin",
        "source": "web_user_dashboard",
        "time": now_str()
    })

    data["web_support_messages"] = support_messages

    add_transaction(
        data,
        username,
        "support_message_sent",
        0,
        f"أرسل المستخدم رسالة دعم من لوحة الويب: {message[:80]}"
    )

    admin_text = (
        "📩 <b>رسالة دعم جديدة</b>\n\n"
        "🌐 <b>المصدر:</b> لوحة المستخدم Web\n"
        f"👤 <b>Username:</b> {username}\n"
        f"🧾 <b>الاسم:</b> {full_name}\n"
        f"🌍 <b>الدولة:</b> {residence}\n"
        f"🆔 <b>Telegram ID:</b> {telegram_id or 'غير متاح'}\n"
        f"📦 <b>الباقة:</b> {plan}\n"
        f"💰 <b>الرصيد:</b> {balance}$\n"
        f"🏦 <b>رأس المال:</b> {capital}$\n"
        f"📈 <b>الأرباح:</b> {profit}$\n\n"
        f"💬 <b>رسالة المستخدم:</b>\n{message}\n\n"
        "↩️ <b>للرد:</b>\n"
        "افتح البوت كأدمن واستخدم نفس نظام الرد على الدعم الموجود لديك."
    )

    reply_markup = {
    "inline_keyboard": [
        [
            {
                "text": "✉️ رد على المستخدم",
                "callback_data": f"reply_support_{telegram_id}"
            }
        ]
                       ]
           }

    sent = send_telegram_message(ADMIN_ID, admin_text, reply_markup=reply_markup)

    if not sent:
        support_messages[-1]["status"] = "saved_but_telegram_failed"
        data["web_support_messages"] = support_messages

    save_data(data)

    return {
        "success": True,
        "message": "Support message sent successfully" if sent else "Support message saved, but Telegram send failed",
        "telegram_sent": sent
    }

@router.post("/support-media")
async def send_support_media(
    caption: str = Form(""),
    file: UploadFile = File(...),
    username: str = Depends(get_current_user)
):
    users, data = load_storage()

    if data.get("support_waiting_reply", {}).get(username, False):
        raise HTTPException(
            status_code=400,
            detail="لديك رسالة دعم قيد الانتظار. يرجى انتظار رد الإدارة قبل إرسال رسالة جديدة."
        )

    telegram_id = get_telegram_id(data, username)
    full_name = data.get("user_full_name", {}).get(username, "غير متوفر")
    residence = data.get("user_residence", {}).get(username, "غير متوفر")
    plan = data.get("user_plans", {}).get(username, "NONE")
    balance = get_balance(data, username)
    capital = get_capital(data, username)
    profit = get_profit_only(data, username)

    file_bytes = await file.read()

    admin_caption = (
        "📩 <b>رسالة دعم جديدة</b>\n\n"
        "🌐 <b>المصدر:</b> لوحة المستخدم Web\n"
        f"👤 <b>Username:</b> {username}\n"
        f"🧾 <b>الاسم:</b> {full_name}\n"
        f"🌍 <b>الدولة:</b> {residence}\n"
        f"🆔 <b>Telegram ID:</b> {telegram_id or 'غير متاح'}\n"
        f"📦 <b>الباقة:</b> {plan}\n"
        f"💰 <b>الرصيد:</b> {balance}$\n"
        f"📥 <b>رأس المال:</b> {capital}$\n"
        f"💵 <b>الأرباح:</b> {profit}$\n"
        f"🕒 <b>الوقت:</b> {now_str()}\n\n"
        f"📝 <b>النص المرفق:</b>\n{caption or 'بدون نص'}"
    )

    media_result = send_telegram_media_to_admin(
        file_bytes=file_bytes,
        filename=file.filename,
        caption=admin_caption
    )

    support_chat_messages = data.get("support_chat_messages", {})
    support_chat_messages.setdefault(username, []).append({
        "sender": "user",
        "type": media_result["type"],
        "file_id": media_result["file_id"],
        "filename": media_result["filename"],
        "message": caption,
        "time": now_str(),
        "read": True
    })
    data["support_chat_messages"] = support_chat_messages

    support_waiting_reply = data.get("support_waiting_reply", {})
    support_waiting_reply[username] = True
    data["support_waiting_reply"] = support_waiting_reply

    add_transaction(
        data,
        username,
        "support_media_sent",
        0,
        f"أرسل المستخدم صورة/ملف دعم من لوحة الويب: {caption[:80]}"
    )

    save_data(data)

    return {
        "success": True,
        "media_type": media_result["type"]
    }


@router.post("/deposit-request")
def create_deposit_request(
    request: DepositRequest,
    username: str = Depends(get_current_user)
):
    users, data = load_storage()

    plan_code = request.plan_code.strip().lower()

    if plan_code not in PLAN_CODE_MAP:
        raise HTTPException(status_code=400, detail="Invalid plan")

    plan_name = PLAN_CODE_MAP[plan_code]
    amount = round(float(request.amount), 2)

    plan = PLANS[plan_name]

    if amount < float(plan["min_deposit"]):
        raise HTTPException(status_code=400, detail="Amount is below plan minimum")

    if plan["max_deposit"] is not None and amount > float(plan["max_deposit"]):
        raise HTTPException(status_code=400, detail="Amount is above plan maximum")

    status = get_status(data, username)

    if status in ["banned", "frozen"]:
        raise HTTPException(status_code=400, detail="Account is not active")

    user_id = get_telegram_id(data, username)

    if not user_id:
        raise HTTPException(status_code=400, detail="Telegram ID is required")

    pending = data.get("pending_deposit_requests", {})

    if str(user_id) in pending:
        raise HTTPException(status_code=400, detail="You already have a pending deposit")

    current_plan = data.get("user_plans", {}).get(username, "NONE")

    req_type = "new_deposit" if current_plan in [None, "NONE"] else "topup_deposit"

    if req_type == "new_deposit" and not data.get("subscriptions_open", True):
        raise HTTPException(status_code=400, detail="Subscriptions are currently closed")

    capital_requests = data.get("capital_withdraw_requests", {})
    if str(user_id) in capital_requests or user_id in capital_requests:
        raise HTTPException(status_code=400, detail="You have a pending capital withdraw request")

    pending[str(user_id)] = {
        "username": username,
        "amount": amount,
        "plan": plan_name,
        "type": req_type,
        "time": now_str(),
        "source": "web_user_dashboard",
        "proof_image_base64": request.proof_image_base64
    }

    data["pending_deposit_requests"] = pending

    add_transaction(
        data,
        username,
        "web_deposit_request",
        amount,
        f"طلب إيداع من لوحة المستخدم | الباقة: {plan_name}"
    )

    save_data(data)

    return {
        "success": True,
        "message": "Deposit request created successfully"
    }


@router.post("/withdraw-request")
def create_withdraw_request(
    request: WithdrawRequest,
    username: str = Depends(get_current_user)
):
    users, data = load_storage()

    status = get_status(data, username)

    if status in ["banned", "frozen"]:
        raise HTTPException(status_code=400, detail="Account is not active")

    if not bool(data.get("verified_users", {}).get(username, False)):
        raise HTTPException(status_code=400, detail="Account must be verified")

    plan = data.get("user_plans", {}).get(username, "NONE")

    if plan not in PLANS:
        raise HTTPException(status_code=400, detail="No active plan")

    if not is_withdraw_available(data, username):
        raise HTTPException(status_code=400, detail="Withdraw is not available yet")

    amount = round(float(request.amount), 2)
    profit_only = get_profit_only(data, username)
    min_withdraw = round(get_capital(data, username) * 0.20, 2)

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    if amount > profit_only:
        raise HTTPException(status_code=400, detail="Amount exceeds available profit")

    if amount < min_withdraw:
        raise HTTPException(status_code=400, detail="Amount is below minimum withdraw")

    user_id = get_telegram_id(data, username)

    if not user_id:
        raise HTTPException(status_code=400, detail="Telegram ID is required")

    pending = data.get("pending_withdraw_requests", {})

    if str(user_id) in pending:
        raise HTTPException(status_code=400, detail="You already have a pending withdraw")

    saved_wallet = data.get("user_wallet_address", {}).get(username, "غير محفوظ")
    saved_network = data.get("user_wallet_network", {}).get(username, "غير محفوظ")

    wallets_match = "المحافظ متطابقة ✅" if request.wallet_address == saved_wallet else "المحافظ غير متطابقة ⚠️"

    pending[str(user_id)] = {
        "username": username,
        "amount": amount,
        "plan": plan,
        "time": now_str(),
        "type": "profit_only",
        "source": "web_user_dashboard",
        "withdraw_wallet_address": request.wallet_address,
        "withdraw_wallet_network": request.wallet_network,
        "saved_wallet_address": saved_wallet,
        "saved_wallet_network": saved_network,
        "wallets_match_result": wallets_match
    }

    data["pending_withdraw_requests"] = pending

    add_transaction(
        data,
        username,
        "web_withdraw_request",
        amount,
        "طلب سحب أرباح من لوحة المستخدم"
    )

    save_data(data)

    reply_markup = {
    "inline_keyboard": [
                [
                 {
                "text": "✅ موافقة",
                "callback_data": f"approve_withdraw_{user_id}"
                  },
               {
                "text": "❌ رفض",
                "callback_data": f"reject_withdraw_{user_id}"
               }
                 ]
            ]
           }

    admin_text = (
    f"💸 طلب سحب أرباح جديد\n\n"
    f"👤 المستخدم: {username}\n"
    f"🆔 ID: {user_id}\n"
    f"📌 الحالة: {get_status(data, username)}\n"
    f"📦 الباقة: {plan}\n"
    f"💰 مبلغ السحب: {amount}$\n"
    f"🕒 وقت الطلب: {pending[str(user_id)]['time']}\n\n"
    f"💼 عنوان المحفظة المدخل للسحب: {request.wallet_address}\n"
    f"🌐 الشبكة المدخلة للسحب: {request.wallet_network}\n\n"
    f"🏦 محفظة الإيداع المحفوظة: {saved_wallet}\n"
    f"🌐 شبكة الإيداع المحفوظة: {saved_network}\n\n"
    f"{wallets_match}"
        )

    telegram_sent = send_telegram_message(
    ADMIN_ID,
    admin_text,
    reply_markup=reply_markup
            )

    return {
    "success": True,
    "message": "Withdraw request created successfully",
    "telegram_sent": telegram_sent
         }


@router.post("/capital-withdraw-request")
def create_capital_withdraw_request(
    request: CapitalWithdrawRequest,
    username: str = Depends(get_current_user)
):
    users, data = load_storage()

    if not bool(data.get("verified_users", {}).get(username, False)):
        raise HTTPException(status_code=400, detail="Account must be verified")

    plan = data.get("user_plans", {}).get(username, "NONE")

    if plan not in PLANS:
        raise HTTPException(status_code=400, detail="No active plan")

    user_id = get_telegram_id(data, username)

    if not user_id:
        raise HTTPException(status_code=400, detail="Telegram ID is required")

    capital_requests = data.get("capital_withdraw_requests", {})

    if str(user_id) in capital_requests:
        raise HTTPException(status_code=400, detail="You already have a capital withdraw request")

    total_amount = get_balance(data, username)

    if total_amount <= 0:
        raise HTTPException(status_code=400, detail="No balance available")

    capital_requests[str(user_id)] = {
        "username": username,
        "amount": total_amount,
        "wallet": request.wallet_address,
        "network": request.wallet_network,
        "request_time": time.time(),
        "due_time": time.time() + (10 * 86400),
        "admin_notified": False,
        "source": "web_user_dashboard"
    }

    data["capital_withdraw_requests"] = capital_requests

    stopped_profit_users = data.get("stopped_profit_users", {})
    stopped_profit_users[username] = True
    data["stopped_profit_users"] = stopped_profit_users

    add_transaction(
        data,
        username,
        "web_capital_withdraw_request",
        total_amount,
        "طلب سحب رأس المال وإيقاف الربح من لوحة المستخدم"
    )

    save_data(data)

    return {
        "success": True,
        "message": "Capital withdraw request created successfully"
    }


@router.post("/verification-request")
def create_verification_request(
    request: VerificationRequest,
    username: str = Depends(get_current_user)
):
    users, data = load_storage()

    if bool(data.get("verified_users", {}).get(username, False)):
        raise HTTPException(status_code=400, detail="Account already verified")

    user_id = get_telegram_id(data, username)

    if not user_id:
        raise HTTPException(status_code=400, detail="Telegram ID is required")

    pending = data.get("pending_verification_requests", {})

    if str(user_id) in pending:
        raise HTTPException(status_code=400, detail="You already have a pending verification request")

    residence = request.residence.strip()
    if residence not in VERIFICATION_COUNTRIES:
        raise HTTPException(status_code=400, detail="Residence must be selected from the country list")

    pending[str(user_id)] = {
        "username": username,
        "full_name": request.full_name.strip(),
        "residence": residence,
        "telegram_id": user_id,
        "time": now_str(),
        "type": "web_account_verification",
        "source": "web_user_dashboard",
        "front_image_base64": request.front_image_base64,
        "back_image_base64": request.back_image_base64
    }

    data["pending_verification_requests"] = pending

    web_identity_images = data.get("web_identity_images", {})
    web_identity_images[username] = {
        "front_image_base64": request.front_image_base64,
        "back_image_base64": request.back_image_base64,
        "updated_at": now_str()
    }

    data["web_identity_images"] = web_identity_images

    add_transaction(
        data,
        username,
        "web_verification_request",
        0,
        "طلب توثيق حساب من لوحة المستخدم"
    )

    save_data(data)

    return {
        "success": True,
        "message": "Verification request created successfully"
    }


@router.post("/delete-account")
def delete_my_account(
    request: DeleteAccountRequest,
    username: str = Depends(get_current_user)
):
    users, data = load_storage()

    if not verify_password(users.get(username), request.password):
        raise HTTPException(status_code=400, detail="Password is incorrect")

    if request.confirm_text.strip().upper() != "DELETE":
        raise HTTPException(status_code=400, detail="Confirmation text must be DELETE")

    user_id = get_telegram_id(data, username)

    deleted_accounts_log = data.get("deleted_accounts_log", [])

    deleted_accounts_log.append({
        "username": username,
        "telegram_id": user_id,
        "full_name": data.get("user_full_name", {}).get(username, "غير متوفر"),
        "residence": data.get("user_residence", {}).get(username, "غير متوفر"),
        "status_before_delete": get_status(data, username),
        "plan_before_delete": data.get("user_plans", {}).get(username, "NONE"),
        "capital_before_delete": get_capital(data, username),
        "balance_before_delete": get_balance(data, username),
        "profit_only_before_delete": get_profit_only(data, username),
        "deleted_at": now_str(),
        "source": "web_user_dashboard"
    })

    data["deleted_accounts_log"] = deleted_accounts_log[-1000:]

    keys_by_username = [
        "user_plans",
        "user_balance",
        "transactions",
        "user_deposits",
        "user_last_profit",
        "user_withdraw_logs",
        "user_deposit_logs",
        "user_statuses",
        "support_blocked_users",
        "user_first_deposit_time",
        "user_last_withdraw_time",
        "user_telegram_ids",
        "user_residence",
        "user_full_name",
        "verified_users",
        "user_referrer",
        "referral_bonus_paid",
        "stopped_profit_users",
        "support_waiting_reply",
        "manual_withdraw_open",
        "user_created_time",
        "user_wallet_address",
        "user_wallet_network",
        "user_identity_photos",
        "user_timezone",
        "pending_profit_capital_activation",
        "web_identity_images"
    ]

    for key in keys_by_username:
        item = data.get(key, {})
        if isinstance(item, dict):
            item.pop(username, None)
            data[key] = item

    if user_id:
        for key in [
            "pending_deposit_requests",
            "pending_withdraw_requests",
            "capital_withdraw_requests",
            "pending_verification_requests",
            "logged_in_users"
        ]:
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

    return {
        "success": True,
        "message": "Account deleted successfully"
    }

@router.post("/support/send-media")
async def send_support_media(
    user_id: int = Form(...),
    caption: str = Form(""),
    file: UploadFile = File(...),
    username: str = Depends(get_current_user)
):
    file_bytes = await file.read()

    try:
        if file.content_type.startswith("image"):
            send_telegram_photo(
                user_id,
                file_bytes,
                f"📩 رد من الدعم:\n\n{caption}"
            )
        else:
            send_telegram_document(
                user_id,
                file_bytes,
                file.filename,
                f"📩 رد من الدعم:\n\n{caption}"
            )

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}
    
@router.get("/telegram-media/{file_id}")
def get_user_telegram_media(
    file_id: str,
    username: str = Depends(get_current_user)
):
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN غير موجود")

    try:
        file_info = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": file_id},
            timeout=15
        ).json()

        if not file_info.get("ok"):
            raise HTTPException(status_code=404, detail="تعذر جلب الملف من Telegram")

        file_path = file_info["result"]["file_path"]

        file_response = requests.get(
            f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}",
            timeout=30
        )

        if file_response.status_code != 200:
            raise HTTPException(status_code=404, detail="تعذر تحميل الملف")

        content_type = file_response.headers.get("content-type", "application/octet-stream")
        encoded = base64.b64encode(file_response.content).decode("utf-8")

        return {
            "data_url": f"data:{content_type};base64,{encoded}",
            "content_type": content_type,
            "file_path": file_path
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Media error: {str(e)}")    
