import json
import os
import time
import requests
import base64
from web_dashboard.config import ADMIN_ID, BOT_TOKEN
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from web_dashboard.auth import get_current_admin
from web_dashboard.database import get_web_db_connection, release_web_db_connection
from web_dashboard.services.storage_service import web_db_get as db_get
from web_dashboard.services.users_service import build_users_list, search_users


router = APIRouter()
ENABLE_FULL_DATA_BACKUP = os.getenv("ENABLE_FULL_DATA_BACKUP", "false").lower() in ("1", "true", "yes", "on")

@router.get("/link-telegram", response_class=HTMLResponse)
async def link_telegram(token: str):
    data = db_get("data", {})

    telegram_link_tokens = data.get("telegram_link_tokens", {})
    token_data = telegram_link_tokens.get(token)

    # لو التوكن غير موجود، تحقّق هل الحساب مربوط سابقاً بنفس التوكن
    if not token_data:
        # محاولة قراءة username من Query أو تجاهل
        # نرجّع نجاح عام لتفادي 400 بعد أول فتح
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)

    # انتهاء الصلاحية (اختياري)
    if time.time() - float(token_data.get("time", 0)) > 300:
        return HTMLResponse("""
        <h2>⏳ انتهت صلاحية الرابط</h2>
        <p>أنشئ رابطاً جديداً من البوت.</p>
        """, status_code=410)

    username = token_data.get("username")
    user_id = int(token_data.get("user_id"))

    users = db_get("users", {})
    if username not in users:
        return HTMLResponse("""
        <h2>❌ لم يتم العثور على الحساب</h2>
        """, status_code=404)

    # اربط (أو أكّد الربط إن كان موجوداً)
    user_telegram_ids = data.get("user_telegram_ids", {})
    user_telegram_ids[username] = user_id

    # بدلاً من الحذف، علّم التوكن كمستخدم
    token_data["used"] = True
    telegram_link_tokens[token] = token_data

    data["user_telegram_ids"] = user_telegram_ids
    data["telegram_link_tokens"] = telegram_link_tokens
    db_set("data", data)

    return HTMLResponse("""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تم الربط</title>
</head>
<body style="font-family: Arial; text-align: center; padding-top: 80px;">
    <h2>✅ تم ربط حسابك بنجاح</h2>
    <p>يمكنك الآن تسجيل الدخول إلى لوحة المستخدم.</p>
    <a href="/user" style="
    display:inline-block;
    margin-top:20px;
    padding:12px 24px;
    background:#2563eb;
    color:white;
    text-decoration:none;
    border-radius:8px;
    font-weight:bold;
">الانتقال إلى لوحة المستخدم</a>
</body>
</html>
""")

@router.get("/telegram-login", response_class=HTMLResponse)
async def telegram_login(token: str):
    from web_dashboard.routers.user_auth_router import create_user_access_token

    data = db_get("data", {})

    telegram_link_tokens = data.get("telegram_link_tokens", {})
    token_data = telegram_link_tokens.get(token)

    if not token_data:
        return HTMLResponse("""
        <h2>❌ رابط غير صالح</h2>
        <p>يرجى تسجيل الدخول من البوت من جديد.</p>
        """, status_code=400)

    if time.time() - float(token_data.get("time", 0)) > 300:
        return HTMLResponse("""
        <h2>⏳ انتهت صلاحية الرابط</h2>
        <p>يرجى تسجيل الدخول من البوت من جديد.</p>
        """, status_code=410)

    username = token_data.get("username")
    user_id = int(token_data.get("user_id"))

    users = db_get("users", {})

    if username not in users:
        return HTMLResponse("""
        <h2>❌ الحساب غير موجود</h2>
        <p>يجب إنشاء حساب في لوحة المستخدم أولاً بنفس اسم المستخدم.</p>
        """, status_code=404)

    user_telegram_ids = data.get("user_telegram_ids", {})
    user_telegram_ids[username] = user_id

    token_data["used"] = True
    telegram_link_tokens[token] = token_data

    data["user_telegram_ids"] = user_telegram_ids
    data["telegram_link_tokens"] = telegram_link_tokens
    db_set("data", data)

    access_token = create_user_access_token(username)

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تسجيل الدخول</title>
    </head>
    <body style="font-family: Arial; text-align: center; padding-top: 80px;">
        <h2>✅ تم تسجيل الدخول بنجاح</h2>
        <p>جاري تحويلك إلى لوحة المستخدم...</p>

        <script>
            localStorage.setItem("user_token", "{access_token}");
            localStorage.setItem("username", "{username}");
            window.location.href = "/user";
        </script>
    </body>
    </html>
    """)


@router.get("/dashboard-login", response_class=HTMLResponse)
async def dashboard_login(token: str):
    from web_dashboard.routers.user_auth_router import create_user_access_token

    data = db_get("data", {})
    dashboard_tokens = data.get("telegram_dashboard_tokens", {})

    if not isinstance(dashboard_tokens, dict):
        dashboard_tokens = {}

    username = None

    for saved_username, saved_token in dashboard_tokens.items():
        if saved_token == token:
            username = saved_username
            break

    if not username:
        return HTMLResponse("""
        <h2>❌ رابط غير صالح</h2>
        <p>يرجى تسجيل الدخول من البوت من جديد للحصول على رابط إدارة الحساب.</p>
        """, status_code=400)

    users = db_get("users", {})

    if username not in users:
        return HTMLResponse("""
        <h2>❌ الحساب غير موجود</h2>
        <p>لا يمكن فتح لوحة المستخدم لأن الحساب غير موجود أو تم حذفه.</p>
        """, status_code=404)

    access_token = create_user_access_token(username)

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>تسجيل الدخول</title>
    </head>
    <body style="font-family: Arial; text-align: center; padding-top: 80px; background:#020617; color:white;">
        <h2>✅ تم تسجيل الدخول بنجاح</h2>
        <p>جاري تحويلك إلى لوحة المستخدم...</p>

        <script>
            localStorage.setItem("user_token", {json.dumps(access_token)});
            localStorage.setItem("username", {json.dumps(username)});
            window.location.href = "/user";
        </script>
    </body>
    </html>
    """)


PLANS = {
    "الباقة الفضية": {
        "name": "الفضية",
        "min_deposit": 10,
        "max_deposit": 100,
        "profit": "2% يومياً",
        "withdraw_time": "كل 30 يوم",
        "withdraw_days": 30
    },
    "الباقة الذهبية": {
        "name": "الذهبية",
        "min_deposit": 101,
        "max_deposit": 300,
        "profit": "2% يومياً",
        "withdraw_time": "كل 20 يوم",
        "withdraw_days": 20
    },
    "باقة VIP": {
        "name": "VIP",
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


class UsernameRequest(BaseModel):
    username: str


class BalanceRequest(BaseModel):
    username: str
    amount: float


class ChangePlanRequest(BaseModel):
    username: str
    plan_code: str


class AdminSubscriberRequest(BaseModel):
    username: str
    password: str
    full_name: str
    front_id_image_base64: str | None = None
    back_id_image_base64: str | None = None
    capital: float
    telegram_id: int | None = None
    verified: bool
    plan: str
    referral_mode: str
    referrer_username: str | None = None
    residence: str
    created_at: str


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
        raise HTTPException(status_code=500, detail=f"Database write error: {str(e)}")

    finally:
        if cur:
            cur.close()
        release_web_db_connection(conn)


def load_storage():
    users = db_get("users", {})
    data = db_get("data", {})

    if not isinstance(users, dict):
        raise HTTPException(status_code=500, detail="Invalid users storage format")

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Invalid data storage format")

    return users, data


def save_data(data):
    if ENABLE_FULL_DATA_BACKUP:
        existing_data = db_get("data", {})
        if isinstance(existing_data, dict) and existing_data:
            db_set("data_backup_before_last_save", existing_data)
    db_set("data", data)


def save_users(users):
    db_set("users", users)


def ensure_user_exists(username, users):
    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")


def add_transaction(data, username, tx_type, amount, note=""):
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


def parse_admin_created_at(value: str):
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M:%S").timestamp()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid creation date/time")


def get_user_status(data, username):
    user_statuses = data.get("user_statuses", {})
    return user_statuses.get(username, "active")


@router.post("/admin-subscriber")
def admin_create_or_update_subscriber(
    request: AdminSubscriberRequest,
    admin: str = Depends(get_current_admin)
):
    from web_dashboard.routers.user_auth_router import hash_password
    from web_dashboard.routers.user_panel_router import VERIFICATION_COUNTRIES

    username = request.username.strip()
    password = request.password.strip()
    full_name = request.full_name.strip()
    residence = request.residence.strip()
    plan = request.plan.strip()
    referral_mode = request.referral_mode.strip()
    referrer_username = (request.referrer_username or "").strip()
    capital = round(float(request.capital), 2)

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")

    if len(password) < 3:
        raise HTTPException(status_code=400, detail="Password must be at least 3 characters")

    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required")

    if capital < 0:
        raise HTTPException(status_code=400, detail="Capital cannot be negative")

    if plan not in [*PLANS.keys(), "NONE"]:
        raise HTTPException(status_code=400, detail="Invalid plan")

    if residence not in VERIFICATION_COUNTRIES:
        raise HTTPException(status_code=400, detail="Residence must be selected from the country list")

    created_ts = parse_admin_created_at(request.created_at)
    now_ts = time.time()

    if created_ts > now_ts:
        raise HTTPException(status_code=400, detail="Creation date cannot be in the future")

    users, data = load_storage()
    existed = username in users

    if referral_mode not in ["none", "friend"]:
        raise HTTPException(status_code=400, detail="Invalid referral mode")

    if referral_mode == "friend":
        if not referrer_username:
            raise HTTPException(status_code=400, detail="Referrer username is required")
        if referrer_username == username:
            raise HTTPException(status_code=400, detail="User cannot invite himself")
        if referrer_username not in users:
            raise HTTPException(status_code=400, detail="Referrer user does not exist")

    users[username] = hash_password(password)

    full_days = int(max(0, now_ts - created_ts) // 86400)
    accrued_profit = 0.0

    if plan in PLANS and capital > 0:
        accrued_profit = round(capital * 0.02 * full_days, 2)

    balance = round(capital + accrued_profit, 2)
    last_profit_ts = created_ts + (full_days * 86400)

    def set_map(key, value):
        item = data.get(key, {})
        if not isinstance(item, dict):
            item = {}
        item[username] = value
        data[key] = item

    set_map("user_plans", plan)
    set_map("user_balance", balance)
    set_map("user_deposits", capital)
    set_map("user_last_profit", last_profit_ts)
    set_map("user_first_deposit_time", created_ts)
    set_map("user_created_time", created_ts)
    set_map("user_statuses", data.get("user_statuses", {}).get(username, "active"))
    set_map("user_full_name", full_name)
    set_map("user_residence", residence)
    set_map("verified_users", bool(request.verified))

    if request.telegram_id:
        set_map("user_telegram_ids", int(request.telegram_id))

    user_referrer = data.get("user_referrer", {})
    if not isinstance(user_referrer, dict):
        user_referrer = {}

    if referral_mode == "friend":
        user_referrer[username] = referrer_username
    else:
        user_referrer.pop(username, None)

    data["user_referrer"] = user_referrer

    web_identity_images = data.get("web_identity_images", {})
    if not isinstance(web_identity_images, dict):
        web_identity_images = {}

    web_identity_images[username] = {
        "front_image_base64": request.front_id_image_base64 or "",
        "back_image_base64": request.back_id_image_base64 or "",
        "source": "admin_subscriber_form",
        "time": now_str()
    }
    data["web_identity_images"] = web_identity_images

    add_transaction(
        data,
        username,
        "admin_subscriber_restore" if existed else "admin_subscriber_create",
        capital,
        f"إضافة/تحديث مشترك من لوحة الأدمن. رأس المال: {capital}$، الأرباح المحتسبة: {accrued_profit}$، تاريخ الإنشاء: {request.created_at}"
    )

    save_users(users)
    save_data(data)

    return {
        "success": True,
        "created": not existed,
        "username": username,
        "capital": capital,
        "balance": balance,
        "accrued_profit": accrued_profit,
        "full_days": full_days,
        "last_profit_time": last_profit_ts
    }


@router.post("/admin-subscriber-form")
async def admin_create_or_update_subscriber_form(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    capital: float = Form(...),
    telegram_id: str = Form(""),
    verified: str = Form(...),
    plan: str = Form(...),
    referral_mode: str = Form(...),
    referrer_username: str = Form(""),
    residence: str = Form(...),
    created_at: str = Form(...),
    front_id_image: UploadFile | None = File(None),
    back_id_image: UploadFile | None = File(None),
    admin: str = Depends(get_current_admin)
):
    async def upload_to_data_url(upload: UploadFile | None):
        if not upload or not upload.filename:
            return ""

        file_bytes = await upload.read()

        if not file_bytes:
            return ""

        mime_type = upload.content_type or "application/octet-stream"
        encoded = base64.b64encode(file_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    request = AdminSubscriberRequest(
        username=username,
        password=password,
        full_name=full_name,
        front_id_image_base64=await upload_to_data_url(front_id_image),
        back_id_image_base64=await upload_to_data_url(back_id_image),
        capital=capital,
        telegram_id=int(telegram_id) if str(telegram_id).strip() else None,
        verified=str(verified).lower() == "true",
        plan=plan,
        referral_mode=referral_mode,
        referrer_username=referrer_username,
        residence=residence,
        created_at=created_at
    )

    return admin_create_or_update_subscriber(request, admin)


def set_user_status(data, username, status):
    user_statuses = data.get("user_statuses", {})
    user_statuses[username] = status
    data["user_statuses"] = user_statuses


def get_user_capital(data, username):
    user_deposits = data.get("user_deposits", {})
    return round(float(user_deposits.get(username, 0)), 2)


def get_user_balance(data, username):
    user_balance = data.get("user_balance", {})
    return round(float(user_balance.get(username, 0)), 2)


def get_saved_telegram_id(data, username):
    user_telegram_ids = data.get("user_telegram_ids", {})
    tg_id = user_telegram_ids.get(username)

    if tg_id is None:
        return None

    try:
        return int(tg_id)
    except Exception:
        return None
    
@router.get("/children/{username}")
def get_user_children(
    username: str,
    admin: str = Depends(get_current_admin)
):
    users = build_users_list()

    children = [
        user for user in users
        if user.get("referrer") == username
    ]

    return {
        "parent": username,
        "count": len(children),
        "children": children
    }    


@router.get("/")
def get_users(
    search: str = Query(default="", description="بحث عن المستخدم"),
    admin: str = Depends(get_current_admin)
):
    if search:
        users = search_users(search)
    else:
        users = build_users_list()

    return {
        "count": len(users),
        "users": users
    }


@router.post("/ban")
def ban_user(
    request: UsernameRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()
    users, data = load_storage()

    ensure_user_exists(username, users)

    if get_user_status(data, username) == "banned":
        return {
            "success": True,
            "message": "User already banned",
            "username": username,
            "status": "banned"
        }

    set_user_status(data, username, "banned")
    add_transaction(data, username, "ban", 0, "تم حظر الحساب من لوحة الويب")

    save_data(data)

    return {
        "success": True,
        "message": f"User {username} banned successfully",
        "username": username,
        "status": "banned"
    }


@router.post("/unban")
def unban_user(
    request: UsernameRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()
    users, data = load_storage()

    ensure_user_exists(username, users)

    set_user_status(data, username, "active")
    add_transaction(data, username, "unban", 0, "تم فك الحظر من لوحة الويب")

    save_data(data)

    return {
        "success": True,
        "message": f"User {username} unbanned successfully",
        "username": username,
        "status": "active"
    }


@router.post("/freeze")
def freeze_user(
    request: UsernameRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()
    users, data = load_storage()

    ensure_user_exists(username, users)

    if get_user_status(data, username) == "banned":
        raise HTTPException(status_code=400, detail="Cannot freeze a banned user")

    set_user_status(data, username, "frozen")
    add_transaction(data, username, "freeze", 0, "تم تجميد الحساب ماليًا من لوحة الويب")

    save_data(data)

    return {
        "success": True,
        "message": f"User {username} frozen successfully",
        "username": username,
        "status": "frozen"
    }


@router.post("/unfreeze")
def unfreeze_user(
    request: UsernameRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()
    users, data = load_storage()

    ensure_user_exists(username, users)

    if get_user_status(data, username) == "banned":
        raise HTTPException(status_code=400, detail="Cannot unfreeze a banned user")

    set_user_status(data, username, "active")
    add_transaction(data, username, "unfreeze", 0, "تم فك التجميد من لوحة الويب")

    save_data(data)

    return {
        "success": True,
        "message": f"User {username} unfrozen successfully",
        "username": username,
        "status": "active"
    }


@router.post("/add-balance")
def add_balance(
    request: BalanceRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()
    amount = round(float(request.amount), 2)

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")

    users, data = load_storage()
    ensure_user_exists(username, users)

    user_balance = data.get("user_balance", {})
    current_balance = round(float(user_balance.get(username, 0)), 2)
    new_balance = round(current_balance + amount, 2)

    user_balance[username] = new_balance
    data["user_balance"] = user_balance

    add_transaction(data, username, "admin_add_balance", amount, "إضافة رصيد من لوحة الويب")

    save_data(data)

    return {
        "success": True,
        "message": "Balance added successfully",
        "username": username,
        "amount": amount,
        "old_balance": current_balance,
        "new_balance": new_balance
    }


@router.post("/subtract-balance")
def subtract_balance(
    request: BalanceRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()
    amount = round(float(request.amount), 2)

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")

    users, data = load_storage()
    ensure_user_exists(username, users)

    user_balance = data.get("user_balance", {})
    current_balance = round(float(user_balance.get(username, 0)), 2)
    new_balance = round(current_balance - amount, 2)

    if new_balance < 0:
        new_balance = 0

    deducted = round(current_balance - new_balance, 2)

    user_balance[username] = new_balance
    data["user_balance"] = user_balance

    add_transaction(data, username, "admin_subtract_balance", deducted, "خصم رصيد من لوحة الويب")

    save_data(data)

    return {
        "success": True,
        "message": "Balance subtracted successfully",
        "username": username,
        "requested_amount": amount,
        "deducted_amount": deducted,
        "old_balance": current_balance,
        "new_balance": new_balance
    }


@router.post("/change-plan")
def change_plan(
    request: ChangePlanRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()
    plan_code = request.plan_code.strip().lower()

    if plan_code not in PLAN_CODE_MAP:
        raise HTTPException(status_code=400, detail="Invalid plan code. Use silver, gold, or vip")

    new_plan = PLAN_CODE_MAP[plan_code]

    users, data = load_storage()
    ensure_user_exists(username, users)

    user_plans = data.get("user_plans", {})
    old_plan = user_plans.get(username, "NONE")

    user_plans[username] = new_plan
    data["user_plans"] = user_plans

    now_ts = time.time()

    user_first_deposit_time = data.get("user_first_deposit_time", {})
    if username not in user_first_deposit_time:
        user_first_deposit_time[username] = now_ts

    data["user_first_deposit_time"] = user_first_deposit_time

    user_last_withdraw_time = data.get("user_last_withdraw_time", {})
    user_last_withdraw_time[username] = now_ts
    data["user_last_withdraw_time"] = user_last_withdraw_time

    add_transaction(
        data,
        username,
        "admin_set_plan",
        0,
        f"تغيير الباقة من {old_plan} إلى {new_plan} من لوحة الويب"
    )

    save_data(data)

    return {
        "success": True,
        "message": "Plan changed successfully",
        "username": username,
        "old_plan": old_plan,
        "new_plan": new_plan
    }


@router.post("/reset-withdraw")
def reset_withdraw(
    request: UsernameRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()

    users, data = load_storage()
    ensure_user_exists(username, users)

    now_ts = time.time()

    user_first_deposit_time = data.get("user_first_deposit_time", {})
    if username not in user_first_deposit_time:
        user_first_deposit_time[username] = now_ts

    data["user_first_deposit_time"] = user_first_deposit_time

    user_last_withdraw_time = data.get("user_last_withdraw_time", {})
    user_last_withdraw_time[username] = now_ts
    data["user_last_withdraw_time"] = user_last_withdraw_time

    add_transaction(data, username, "admin_reset_withdraw_cycle", 0, "إعادة ضبط دورة السحب من لوحة الويب")

    save_data(data)

    return {
        "success": True,
        "message": "Withdraw cycle reset successfully",
        "username": username
    }


@router.post("/delete-subscription")
def delete_subscription(
    request: UsernameRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()

    users, data = load_storage()
    ensure_user_exists(username, users)

    old_plan = data.get("user_plans", {}).get(username, "NONE")
    old_capital = get_user_capital(data, username)
    old_balance = get_user_balance(data, username)

    user_plans = data.get("user_plans", {})
    user_plans[username] = "NONE"
    data["user_plans"] = user_plans

    user_balance = data.get("user_balance", {})
    user_balance[username] = 0
    data["user_balance"] = user_balance

    user_deposits = data.get("user_deposits", {})
    user_deposits[username] = 0
    data["user_deposits"] = user_deposits

    user_last_profit = data.get("user_last_profit", {})
    user_last_profit[username] = time.time()
    data["user_last_profit"] = user_last_profit

    for key in [
        "user_first_deposit_time",
        "user_last_withdraw_time",
        "stopped_profit_users",
        "manual_withdraw_open",
        "pending_profit_capital_activation"
    ]:
        item = data.get(key, {})
        if isinstance(item, dict):
            item.pop(username, None)
            data[key] = item

    user_id = get_saved_telegram_id(data, username)

    if user_id:
        for key in [
            "pending_deposit_requests",
            "pending_withdraw_requests",
            "capital_withdraw_requests"
        ]:
            item = data.get(key, {})
            if isinstance(item, dict):
                item.pop(str(user_id), None)
                item.pop(user_id, None)
                data[key] = item

    user_deposit_logs = data.get("user_deposit_logs", {})
    user_deposit_logs[username] = []
    data["user_deposit_logs"] = user_deposit_logs

    user_withdraw_logs = data.get("user_withdraw_logs", {})
    user_withdraw_logs[username] = []
    data["user_withdraw_logs"] = user_withdraw_logs

    add_transaction(
        data,
        username,
        "admin_delete_subscription",
        0,
        f"حذف الاشتراك من لوحة الويب | الباقة السابقة: {old_plan} | رأس المال السابق: {old_capital}$ | الرصيد السابق: {old_balance}$"
    )

    save_data(data)

    return {
        "success": True,
        "message": "Subscription deleted successfully",
        "username": username,
        "old_plan": old_plan,
        "old_capital": old_capital,
        "old_balance": old_balance
    }

@router.post("/open-withdraw")
def open_withdraw(
    request: UsernameRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()

    users, data = load_storage()
    ensure_user_exists(username, users)

    user_plans = data.get("user_plans", {})
    plan_name = user_plans.get(username)

    if plan_name in [None, "NONE"]:
        raise HTTPException(status_code=400, detail="User has no active plan")

    if plan_name not in PLANS:
        raise HTTPException(status_code=400, detail="Unknown user plan")

    manual_withdraw_open = data.get("manual_withdraw_open", {})

    if manual_withdraw_open.get(username, {}).get("is_open", False):
        return {
            "success": True,
            "message": "Withdraw already open",
            "username": username
        }

    interval_days = PLANS[plan_name]["withdraw_days"]
    now_ts = time.time()

    user_first_deposit_time = data.get("user_first_deposit_time", {})
    if username not in user_first_deposit_time:
        user_first_deposit_time[username] = now_ts
    data["user_first_deposit_time"] = user_first_deposit_time

    user_last_withdraw_time = data.get("user_last_withdraw_time", {})
    original_last_withdraw_time = user_last_withdraw_time.get(username, None)

    user_last_withdraw_time[username] = now_ts - (interval_days * 86400)
    data["user_last_withdraw_time"] = user_last_withdraw_time

    manual_withdraw_open[username] = {
        "is_open": True,
        "original_last_withdraw_time": original_last_withdraw_time,
        "opened_at": now_ts
    }
    data["manual_withdraw_open"] = manual_withdraw_open

    add_transaction(
        data,
        username,
        "admin_open_withdraw",
        0,
        "قام الأدمن بفتح السحب للمستخدم من لوحة الويب"
    )

    save_data(data)

    return {
        "success": True,
        "message": "Withdraw opened successfully",
        "username": username
    }


@router.post("/close-withdraw")
def close_withdraw(
    request: UsernameRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()

    users, data = load_storage()
    ensure_user_exists(username, users)

    manual_withdraw_open = data.get("manual_withdraw_open", {})
    saved_data = manual_withdraw_open.get(username, {})

    if not saved_data.get("is_open", False):
        raise HTTPException(status_code=400, detail="Manual withdraw is not open for this user")

    original_last_withdraw_time = saved_data.get("original_last_withdraw_time", None)

    user_last_withdraw_time = data.get("user_last_withdraw_time", {})

    if original_last_withdraw_time is None:
        user_last_withdraw_time.pop(username, None)
    else:
        user_last_withdraw_time[username] = float(original_last_withdraw_time)

    data["user_last_withdraw_time"] = user_last_withdraw_time

    manual_withdraw_open.pop(username, None)
    data["manual_withdraw_open"] = manual_withdraw_open

    add_transaction(
        data,
        username,
        "admin_close_manual_withdraw",
        0,
        "قام الأدمن بإيقاف فتح السحب وإعادة الوضع الطبيعي من لوحة الويب"
    )

    save_data(data)

    return {
        "success": True,
        "message": "Withdraw closed successfully",
        "username": username
    }

@router.get("/details/{username}")
def get_user_details(
    username: str,
    admin: str = Depends(get_current_admin)
):
    users = db_get("users", {})
    data = db_get("data", {})

    if username not in users:
        raise HTTPException(status_code=404, detail="User not found")

    password = users.get(username, "")

    # --- Financial ---
    balance = round(float(data.get("user_balance", {}).get(username, 0)), 2)
    capital = round(float(data.get("user_deposits", {}).get(username, 0)), 2)
    profit_only = round(balance - capital, 2)
    if profit_only < 0:
        profit_only = 0

    # --- Basic ---
    telegram_id = data.get("user_telegram_ids", {}).get(username)
    full_name = data.get("user_full_name", {}).get(username, "غير متوفر")
    residence = data.get("user_residence", {}).get(username, "غير متوفر")

    # --- Status ---
    plan = data.get("user_plans", {}).get(username, "NONE")
    status = data.get("user_statuses", {}).get(username, "active")
    verified = bool(data.get("verified_users", {}).get(username, False))

    # --- Referral ---
    user_referrer = data.get("user_referrer", {})
    referrer = user_referrer.get(username, "بدون دعوة")

    children_count = sum(
        1 for child, parent in user_referrer.items()
        if parent == username
    )

    # --- Withdraw System ---
    manual_withdraw_open = data.get("manual_withdraw_open", {}).get(username, {})
    is_withdraw_open = bool(manual_withdraw_open.get("is_open", False))

    first_deposit_time = data.get("user_first_deposit_time", {}).get(username)
    last_withdraw_time = data.get("user_last_withdraw_time", {}).get(username)

        # --- Countdown Data ---
    now_ts = time.time()

    last_profit_time = data.get("user_last_profit", {}).get(username)
    next_profit_time = None
    next_profit_seconds = None

    if last_profit_time:
        next_profit_time = float(last_profit_time) + 86400
        next_profit_seconds = int(next_profit_time - now_ts)
        if next_profit_seconds < 0:
            next_profit_seconds = 0

    next_withdraw_time = None
    withdraw_countdown_seconds = None

    if plan in PLANS:
        interval_days = PLANS[plan]["withdraw_days"]

        base_withdraw_time = None

        if last_withdraw_time:
            base_withdraw_time = float(last_withdraw_time)
        elif first_deposit_time:
            base_withdraw_time = float(first_deposit_time)

        if base_withdraw_time:
            next_withdraw_time = base_withdraw_time + (interval_days * 86400)
            withdraw_countdown_seconds = int(next_withdraw_time - now_ts)

            if withdraw_countdown_seconds < 0:
                withdraw_countdown_seconds = 0

    # --- Logs ---
    transactions = data.get("transactions", {}).get(username, [])
    deposits = data.get("user_deposit_logs", {}).get(username, [])
    withdraws = data.get("user_withdraw_logs", {}).get(username, [])

    # --- Identity ---
    identity_photos = data.get("user_identity_photos", {}).get(username, {})
    front_id_file_id = identity_photos.get("front_id_file_id")
    back_id_file_id = identity_photos.get("back_id_file_id")

    front_id_url = None
    back_id_url = None

    if front_id_file_id:
        try:
            from web_dashboard.routers.financial_router import build_telegram_file_url
            front_id_url = build_telegram_file_url(front_id_file_id)
        except:
            pass

    if back_id_file_id:
        try:
            from web_dashboard.routers.financial_router import build_telegram_file_url
            back_id_url = build_telegram_file_url(back_id_file_id)
        except:
            pass

    return {
        # Basic
        "username": username,
        "password": password,
        "telegram_id": telegram_id,
        "full_name": full_name,
        "residence": residence,

        # Financial
        "balance": balance,
        "capital": capital,
        "profit_only": profit_only,

        # Status
        "plan": plan,
        "status": status,
        "verified": verified,

        # Referral
        "referrer": referrer,
        "children_count": children_count,

        # Withdraw
        "manual_withdraw_open": is_withdraw_open,
        "first_deposit_time": first_deposit_time,
        "last_withdraw_time": last_withdraw_time,

        "next_profit_time": next_profit_time,
        "next_profit_seconds": next_profit_seconds,
        "next_withdraw_time": next_withdraw_time,
        "withdraw_countdown_seconds": withdraw_countdown_seconds,

        # Logs
        "transactions": transactions,
        "deposits": deposits,
        "withdraws": withdraws,

        "transactions_count": len(transactions),
        "deposits_count": len(deposits),
        "withdraws_count": len(withdraws),

        # Identity
        "front_id_url": front_id_url,
        "back_id_url": back_id_url
    }
class SupportReplyRequest(BaseModel):
    username: str
    message: str


def send_telegram_message(chat_id: int, text: str):
    if not BOT_TOKEN or not chat_id:
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": int(chat_id),
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=10
        )

        result = response.json()
        return bool(result.get("ok"))

    except Exception as e:
        print(f"[ADMIN_WEB_SUPPORT_SEND_ERROR] {e}")
        return False

def send_telegram_media(chat_id: int, file_bytes: bytes, filename: str, caption: str = ""):
    if not BOT_TOKEN or not chat_id:
        return None

    mime_name = filename.lower()

    if mime_name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {
            "photo": (filename, file_bytes)
        }
        data = {
            "chat_id": int(chat_id),
            "caption": caption or ""
        }
        media_type = "photo"
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        files = {
            "document": (filename, file_bytes)
        }
        data = {
            "chat_id": int(chat_id),
            "caption": caption or ""
        }
        media_type = "document"

    response = requests.post(url, data=data, files=files, timeout=30)
    result = response.json()

    if not result.get("ok"):
        raise HTTPException(status_code=500, detail="فشل إرسال الملف عبر تيليغرام")

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


@router.get("/support-requests")
def get_support_requests(admin: str = Depends(get_current_admin)):
    users, data = load_storage()

    support_waiting_reply = data.get("support_waiting_reply", {})
    support_chat_messages = data.get("support_chat_messages", {})

    result = []

    for username, waiting in support_waiting_reply.items():
        

        if username not in users:
            continue

        support_opened_at = data.get("support_opened_at", {})
        opened_at = support_opened_at.get(username)

        if opened_at:
            if time.time() - float(opened_at) > 1800:
                continue

        messages = support_chat_messages.get(username, [])
        last_message = messages[-1] if messages else {}

        result.append({
            "username": username,
            "telegram_id": data.get("user_telegram_ids", {}).get(username),
            "full_name": data.get("user_full_name", {}).get(username, "غير متوفر"),
            "residence": data.get("user_residence", {}).get(username, "غير متوفر"),
            "plan": data.get("user_plans", {}).get(username, "NONE"),
            "balance": round(float(data.get("user_balance", {}).get(username, 0)), 2),
            "capital": round(float(data.get("user_deposits", {}).get(username, 0)), 2),
            "last_message": last_message.get("message", "لا توجد رسالة"),
            "last_time": last_message.get("time", "غير متوفر"),
            "messages_count": len(messages),
            "replied": not bool(waiting)
        })

    return {
        "count": len(result),
        "requests": result
    }


@router.get("/support-chat/{username}")
def get_admin_support_chat(
    username: str,
    admin: str = Depends(get_current_admin)
):
    users, data = load_storage()

    ensure_user_exists(username, users)

    support_chat_messages = data.get("support_chat_messages", {})
    messages = support_chat_messages.get(username, [])
    support_opened_at = data.get("support_opened_at", {})

    if username not in support_opened_at:
       support_opened_at[username] = time.time()
       data["support_opened_at"] = support_opened_at
       save_data(data)

    return {
        "username": username,
        "messages": messages[-100:],
        "waiting_reply": bool(data.get("support_waiting_reply", {}).get(username, False))
    }


@router.post("/support-reply")
def admin_support_reply(
    request: SupportReplyRequest,
    admin: str = Depends(get_current_admin)
):
    username = request.username.strip()
    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="لا يمكن إرسال رد فارغ")

    users, data = load_storage()

    ensure_user_exists(username, users)

    telegram_id = get_saved_telegram_id(data, username)

    support_chat_messages = data.get("support_chat_messages", {})
    support_chat_messages.setdefault(username, []).append({
        "sender": "support",
        "message": message,
        "time": now_str(),
        "read": False
    })

    data["support_chat_messages"] = support_chat_messages

    support_waiting_reply = data.get("support_waiting_reply", {})
    support_waiting_reply[username] = False
    data["support_waiting_reply"] = support_waiting_reply

    support_opened_at = data.get("support_opened_at", {})
    support_opened_at.pop(username, None)
    data["support_opened_at"] = support_opened_at

    add_transaction(
        data,
        username,
        "web_admin_support_reply",
        0,
        f"رد الأدمن من لوحة الويب: {message[:80]}"
    )

    save_data(data)

    telegram_sent = False

    if telegram_id:
        telegram_sent = send_telegram_message(
            telegram_id,
            f"📩 رد من الدعم:\n\n{message}"
        )

    admin_notify_text = (
          "📨 <b>تم الرد على رسالة دعم من داشبورد الأدمن</b>\n\n"
          f"👤 <b>المستخدم:</b> {username}\n"
          f"🆔 <b>Telegram ID:</b> {telegram_id or 'غير متاح'}\n"
          f"🕒 <b>الوقت:</b> {now_str()}\n\n"
          f"💬 <b>نص الرد:</b>\n{message}\n\n"
          f"📌 <b>الحالة:</b> تم إغلاق طلب الدعم من قائمة الانتظار"
    )

    send_telegram_message(
       ADMIN_ID,
       admin_notify_text
    )    

    return {
        "success": True,
        "telegram_sent": telegram_sent
    }

@router.post("/support-reply-media")
async def admin_support_reply_media(
    username: str = Form(...),
    caption: str = Form(""),
    file: UploadFile = File(...),
    admin: str = Depends(get_current_admin)
):
    users, data = load_storage()

    ensure_user_exists(username, users)

    telegram_id = get_saved_telegram_id(data, username)

    if not telegram_id:
        raise HTTPException(status_code=400, detail="لا يوجد Telegram ID لهذا المستخدم")

    file_bytes = await file.read()

    media_result = send_telegram_media(
        chat_id=telegram_id,
        file_bytes=file_bytes,
        filename=file.filename,
        caption=f"📩 رد من الدعم:\n\n{caption}" if caption else "📩 رد من الدعم"
    )

    support_chat_messages = data.get("support_chat_messages", {})

    support_chat_messages.setdefault(username, []).append({
        "sender": "support",
        "type": media_result["type"],
        "file_id": media_result["file_id"],
        "filename": media_result["filename"],
        "message": caption,
        "time": now_str(),
        "read": False
    })

    data["support_chat_messages"] = support_chat_messages

    support_waiting_reply = data.get("support_waiting_reply", {})
    support_waiting_reply[username] = False
    data["support_waiting_reply"] = support_waiting_reply

    support_opened_at = data.get("support_opened_at", {})
    support_opened_at[username] = time.time()
    data["support_opened_at"] = support_opened_at

    add_transaction(
        data,
        username,
        "web_admin_support_reply_media",
        0,
        f"رد الأدمن بملف/صورة من لوحة الويب: {caption[:80]}"
    )

    save_data(data)

    return {
        "success": True,
        "media_type": media_result["type"]
    }


def send_telegram_message(chat_id: int, text: str):
    if not BOT_TOKEN or not chat_id:
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": int(chat_id),
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=10
        )

        result = response.json()
        return bool(result.get("ok"))

    except Exception as e:
        print(f"[DELETE_USER_TELEGRAM_NOTIFY_ERROR] {e}")
        return False    

@router.delete("/delete-user/{username}")
def delete_user(
    username: str,
    admin: str = Depends(get_current_admin)
):
    users, data = load_storage()
    target_user_id = data.get("user_telegram_ids", {}).get(username)

    if username not in users:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    # --- جمع البيانات قبل الحذف (نفس البوت) ---
    telegram_id = data.get("user_telegram_ids", {}).get(username)

    entry = {
        "username": username,
        "telegram_id": telegram_id,
        "telegram_first_name": data.get("user_full_name", {}).get(username),
        "telegram_username": username,
        "full_name": data.get("user_full_name", {}).get(username),
        "residence": data.get("user_residence", {}).get(username),
        "verification_text": "موثق" if data.get("verified_users", {}).get(username) else "غير موثق",
        "status_before_delete": data.get("user_statuses", {}).get(username, "active"),
        "plan_before_delete": data.get("user_plans", {}).get(username),
        "capital_before_delete": data.get("user_deposits", {}).get(username, 0),
        "balance_before_delete": data.get("user_balance", {}).get(username, 0),
        "profit_only_before_delete": (
            float(data.get("user_balance", {}).get(username, 0)) -
            float(data.get("user_deposits", {}).get(username, 0))
        ),
        "deleted_at": now_str(),
        "pending_requests_summary": "تم الحذف من الداشبورد"
    }

    # --- إضافة للسجل (نفس البوت) ---
    deleted_accounts_log = data.get("deleted_accounts_log", [])
    deleted_accounts_log.append(entry)

    if len(deleted_accounts_log) > 1000:
        deleted_accounts_log = deleted_accounts_log[-1000:]

    data["deleted_accounts_log"] = deleted_accounts_log

    full_name = data.get("user_full_name", {}).get(username, "غير متوفر")
    residence = data.get("user_residence", {}).get(username, "غير متوفر")
    plan = data.get("user_plans", {}).get(username, "NONE")
    balance = round(float(data.get("user_balance", {}).get(username, 0)), 2)
    capital = round(float(data.get("user_deposits", {}).get(username, 0)), 2)

    profit_only = balance - capital
    if profit_only < 0:
        profit_only = 0

    verification_text = "موثق ✅" if data.get("verified_users", {}).get(username) else "غير موثق ❌"
    status_text = data.get("user_statuses", {}).get(username, "active")

    # مبدئياً بدون طلبات معلقة (نضيفها لاحقاً إذا أردت ربطها مع البوت)
    pending_requests_summary = "تم الحذف من الداشبورد"

    deleted_account_entry = {
        "username": username,
        "telegram_id": target_user_id if target_user_id else "غير متوفر",
        "telegram_first_name": "غير متوفر",
        "telegram_username": "لا يوجد",
        "full_name": full_name,
        "residence": residence,
        "verification_text": verification_text,
        "status_before_delete": status_text,
        "plan_before_delete": plan,
        "capital_before_delete": capital,
        "balance_before_delete": balance,
        "profit_only_before_delete": profit_only,
        "pending_requests_summary": pending_requests_summary,
        "deleted_at": now_str()
         }
    deleted_accounts_log = data.get("deleted_accounts_log", [])
    deleted_accounts_log.append(deleted_account_entry)

    if len(deleted_accounts_log) > 1000:
        deleted_accounts_log = deleted_accounts_log[-1000:]

    data["deleted_accounts_log"] = deleted_accounts_log

    # --- حذف المستخدم (نسخة مبسطة من البوت) ---
    users.pop(username, None)

    for key in [
        "user_balance", "user_deposits", "user_plans", "user_statuses",
        "user_telegram_ids", "user_full_name", "user_residence",
        "user_last_profit", "user_withdraw_logs", "user_deposit_logs",
        "verified_users", "user_referrer", "referral_bonus_paid",
        "support_waiting_reply", "user_wallet_address", "user_wallet_network",
        "telegram_dashboard_tokens"
    ]:
        data.get(key, {}).pop(username, None)

    # حذف جلسة تسجيل الدخول الخاصة بالمستخدم من الداشبورد/البوت
    logged_in_users = data.get("logged_in_users", {})

    if target_user_id:
       logged_in_users.pop(str(target_user_id), None)
       if str(target_user_id).isdigit():
           logged_in_users.pop(int(target_user_id), None)

    data["logged_in_users"] = logged_in_users    

    # --- حفظ ---
    db_set("users", users)
    save_data(data)
    # إرسال إشعار للمستخدم
    if target_user_id and str(target_user_id).isdigit():
        send_telegram_message(
           int(target_user_id),
           "❌ تم حذف حسابك نهائيًا بواسطة الإدارة"
      )
    # إرسال إشعار للأدمن
    admin_notify_text = (
    f"🗑 تم حذف مستخدم من داشبورد الويب\n\n"
    f"👤 اسم المستخدم: {deleted_account_entry.get('username', 'غير متوفر')}\n"
    f"🆔 Telegram ID: {deleted_account_entry.get('telegram_id', 'غير متوفر')}\n"
    f"👤 الاسم والكنية: {deleted_account_entry.get('full_name', 'غير متوفر')}\n"
    f"🏠 مكان الإقامة: {deleted_account_entry.get('residence', 'غير متوفر')}\n"
    f"🪪 التوثيق: {deleted_account_entry.get('verification_text', 'غير متوفر')}\n"
    f"📌 الحالة قبل الحذف: {deleted_account_entry.get('status_before_delete', 'غير متوفر')}\n"
    f"📦 الباقة قبل الحذف: {deleted_account_entry.get('plan_before_delete', 'غير متوفر')}\n"
    f"💰 رأس المال قبل الحذف: {deleted_account_entry.get('capital_before_delete', 0)}$\n"
    f"📈 الرصيد قبل الحذف: {deleted_account_entry.get('balance_before_delete', 0)}$\n"
    f"💵 الأرباح فقط قبل الحذف: {deleted_account_entry.get('profit_only_before_delete', 0)}$\n"
    f"🕒 وقت الحذف: {deleted_account_entry.get('deleted_at', 'غير متوفر')}\n\n"
    f"📋 الطلبات المعلقة وقت الحذف:\n"
    f"{deleted_account_entry.get('pending_requests_summary', 'غير متوفر')}"
        )

    send_telegram_message(ADMIN_ID, admin_notify_text)    

    return {
        "success": True,
        "message": f"تم حذف المستخدم {username}"
    }

@router.get("/deleted-accounts-legacy", include_in_schema=False)
def get_deleted_accounts_legacy(admin: str = Depends(get_current_admin)):
    users, data = load_storage()

    logs = data.get("deleted_accounts_log", [])

    return {
        "logs": logs[::-1]  # أحدث أولاً
    }

@router.get("/deleted-accounts")
def get_deleted_accounts(admin: str = Depends(get_current_admin)):
    users, data = load_storage()

    logs = data.get("deleted_accounts_log", [])

    if not isinstance(logs, list):
        logs = []

    return {
        "count": len(logs),
        "logs": list(reversed(logs))
    }

class EmptyRequest(BaseModel):
    pass


@router.get("/admin-notifications")
def get_admin_notifications(admin: str = Depends(get_current_admin)):
    users, data = load_storage()

    notifications = data.get("admin_notifications", [])

    if not isinstance(notifications, list):
        notifications = []

    unread_count = sum(
        1 for item in notifications
        if not item.get("read", False)
    )

    return {
        "count": len(notifications),
        "unread_count": unread_count,
        "notifications": list(reversed(notifications[-100:]))
    }


@router.post("/admin-notifications-clear")
def clear_admin_notifications(
    request: EmptyRequest,
    admin: str = Depends(get_current_admin)
):
    users, data = load_storage()

    data["admin_notifications"] = []

    save_data(data)

    return {
        "success": True
    }


@router.post("/admin-notifications-read")
def mark_admin_notifications_read(
    request: EmptyRequest,
    admin: str = Depends(get_current_admin)
):
    users, data = load_storage()

    notifications = data.get("admin_notifications", [])

    if isinstance(notifications, list):
        for item in notifications:
            item["read"] = True

    data["admin_notifications"] = notifications

    save_data(data)

    return {
        "success": True
    }

@router.delete("/support-chat/{username}")
def delete_support_chat(
    username: str,
    admin: str = Depends(get_current_admin)
):
    users, data = load_storage()

    ensure_user_exists(username, users)

    support_chat_messages = data.get("support_chat_messages", {})
    support_chat_messages.pop(username, None)

    data["support_chat_messages"] = support_chat_messages

    save_data(data)

    return {
        "success": True,
        "message": f"تم مسح محادثة الدعم للمستخدم {username}"
    }

@router.get("/telegram-media/{file_id}")
def get_admin_telegram_media(
    file_id: str,
    admin: str = Depends(get_current_admin)
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
