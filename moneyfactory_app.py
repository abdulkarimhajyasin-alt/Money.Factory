import json
import time
import asyncio
import os
import random
from urllib.parse import quote
from datetime import datetime
from zoneinfo import ZoneInfo
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv
load_dotenv()

# =========================
# الإعدادات العامة
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [5685737658]
ADMIN_ID = ADMIN_IDS[0]

# =========================
# موظفو الدعم فقط
# أضف Telegram User ID لكل موظف دعم هنا
# الموظف يبقى مستخدمًا عاديًا ولا يحصل على صلاحيات أدمن
# =========================
SUPPORT_EMPLOYEE_IDS = [5102448932]

DATA_FILE = "data.json"

BOT_USERNAME = "Moneyfactory1bot"

db_pool = None


users = {}
user_plans = {}
user_balance = {}
transactions = {}
user_deposits = {}
user_last_profit = {}
user_withdraw_logs = {}
user_deposit_logs = {}
user_states = {}
pending_deposit_requests = {}
pending_withdraw_requests = {}
REFERRAL_DATA = {}
chat_ids = []
logged_in_users = {}
pending_verification_requests = {}   # طلبات التوثيق بانتظار موافقة الأدمن
user_residence = {}                  # مكان إقامة المستخدم
user_full_name = {}                  # الاسم والكنية كما في الهوية
verified_users = {}                  # هل الحساب موثق أم لا
user_statuses = {}   # active / frozen / banned
support_blocked_users = {}   # username -> True/False
user_first_deposit_time = {}   # وقت أول إيداع مقبول
user_last_withdraw_time = {}   # وقت آخر سحب تمت الموافقة عليه
user_telegram_ids = {}   # username -> telegram user id
subscriptions_open = True   # True = الاشتراك مفتوح / False = الاشتراك متوقف
bot_maintenance_mode = False   # True = البوت متوقف للصيانة / False = البوت يعمل طبيعيًا
user_referrer = {}          # username -> referrer username
referral_bonus_paid = {}    # username -> True/False
capital_withdraw_requests = {}   # user_id -> بيانات طلب سحب رأس المال
stopped_profit_users = {}        # username -> True/False
support_waiting_reply = {}       # username -> True/False

support_employees_enabled = False   # تشغيل/إيقاف موظفي الدعم
support_claims = {}                 # username -> {"employee_id": int, "expires_at": timestamp}
support_message_copies = {}         # user_id -> نسخ رسائل الدعم المرسلة للمدير والموظفين

admin_sent_batches = {}          # batch_id -> بيانات آخر دفعات الإرسال للأدمن
admin_last_batch_id = None       # آخر batch تم إرسالها
deleted_accounts_log = []        # سجل الحسابات المحذوفة
manual_withdraw_open = {}        # username -> بيانات فتح السحب اليدوي
user_created_time = {}           # username -> وقت إنشاء الحساب
user_tree_views = {}             # view_id -> بيانات شاشة شجرة المستخدمين
user_wallet_address = {}          # username -> عنوان المحفظة المحفوظة
user_wallet_network = {}          # username -> اسم الشبكة المحفوظة
user_identity_photos = {}          # username -> صور البطاقة الشخصية front/back
user_timezone = {}                  # username -> IANA timezone مثل Europe/Vienna أو Asia/Damascus

pending_profit_capital_activation = {}  # username -> بيانات تفعيل رأس المال الجديد للربح بعد نهاية دورة السحب


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

COUNTRY_TIMEZONES = {
    "🇨🇭 سويسرا": {
        "country": "سويسرا",
        "timezone": "Europe/Zurich"
    },
    "🇮🇹 إيطاليا": {
        "country": "إيطاليا",
        "timezone": "Europe/Rome"
    },
    "🇪🇸 إسبانيا": {
        "country": "إسبانيا",
        "timezone": "Europe/Madrid"
    },
    "🇬🇷 اليونان": {
        "country": "اليونان",
        "timezone": "Europe/Athens"
    },
    "🇵🇱 بولندا": {
        "country": "بولندا",
        "timezone": "Europe/Warsaw"
    },
    "🇨🇿 التشيك": {
        "country": "التشيك",
        "timezone": "Europe/Prague"
    },
    "🇷🇴 رومانيا": {
        "country": "رومانيا",
        "timezone": "Europe/Bucharest"
    },
    "🇭🇺 هنغاريا": {
        "country": "هنغاريا",
        "timezone": "Europe/Budapest"
    },
    "🇫🇮 فنلندا": {
        "country": "فنلندا",
        "timezone": "Europe/Helsinki"
    },
    "🇶🇦 قطر": {
        "country": "قطر",
        "timezone": "Asia/Qatar"
    },
    "🇦🇹 النمسا": {
        "country": "النمسا",
        "timezone": "Europe/Vienna"
    },
    "🇩🇪 ألمانيا": {
        "country": "ألمانيا",
        "timezone": "Europe/Berlin"
    },
    "🇹🇷 تركيا": {
        "country": "تركيا",
        "timezone": "Europe/Istanbul"
    },
    "🇸🇦 السعودية": {
        "country": "السعودية",
        "timezone": "Asia/Riyadh"
    },
    "🇦🇪 الإمارات": {
        "country": "الإمارات",
        "timezone": "Asia/Dubai"
    },
    "🇮🇶 العراق": {
        "country": "العراق",
        "timezone": "Asia/Baghdad"
    },
    "🇯🇴 الأردن": {
        "country": "الأردن",
        "timezone": "Asia/Amman"
    },
    "🇸🇾 سوريا": {
        "country": "سوريا",
        "timezone": "Asia/Damascus"
    },
    "🇱🇧 لبنان": {
        "country": "لبنان",
        "timezone": "Asia/Beirut"
    },
    "🇪🇬 مصر": {
        "country": "مصر",
        "timezone": "Africa/Cairo"
    },
    "🇵🇸 فلسطين": {
        "country": "فلسطين",
        "timezone": "Asia/Gaza"
    },
    "🇳🇱 هولندا": {
        "country": "هولندا",
        "timezone": "Europe/Amsterdam"
    },
    "🇫🇷 فرنسا": {
        "country": "فرنسا",
        "timezone": "Europe/Paris"
    },
    "🇧🇪 بلجيكا": {
        "country": "بلجيكا",
        "timezone": "Europe/Brussels"
    },
    "🇸🇪 السويد": {
        "country": "السويد",
        "timezone": "Europe/Stockholm"
    },
    "🇩🇰 الدنمارك": {
        "country": "الدنمارك",
        "timezone": "Europe/Copenhagen"
    },
    "🇳🇴 النرويج": {
        "country": "النرويج",
        "timezone": "Europe/Oslo"
    },
    "🇬🇧 بريطانيا": {
        "country": "بريطانيا",
        "timezone": "Europe/London"
    },
    "🇺🇸 أمريكا - نيويورك": {
        "country": "أمريكا - نيويورك",
        "timezone": "America/New_York"
    },
    "🇨🇦 كندا - تورونتو": {
        "country": "كندا - تورونتو",
        "timezone": "America/Toronto"
    }
}

TERMS_TEXT = """📜 شروط الاستخدام وسياسة المنصة

مرحبًا بك في Money factory 💰

يرجى قراءة الشروط التالية بعناية قبل إنشاء حسابك:

━━━━━━━━━━━━━━━

1️⃣ طبيعة الخدمة
هذه المنصة مخصصة لإدارة اشتراكات واستثمارات المشتركين ضمن باقات محددة يتم تحديدها من قبل الإدارة، وليست منصة تداول مباشر أو وسيطًا ماليًا مستقلًا.

2️⃣ استثمار الأرباح
يمكن للمستخدم تحويل الأرباح المتاحة إلى رأس المال عند توفر السحب، حيث يصبح رأس المال الجديد (رأس المال + الأرباح)، ويكون هذا الخيار متاحًا لمدة ساعة واحدة فقط من لحظة إتاحة السحب.

3️⃣ مسؤولية المستخدم
يقر المستخدم بأن جميع البيانات التي يقدمها صحيحة، ويتحمل المسؤولية الكاملة عن الحفاظ على اسم المستخدم وكلمة المرور وعدم مشاركتهما مع أي طرف آخر.

4️⃣ الإيداع والسحب
- السحب (((حصراََ))) الى نفس المحفظة التي اودعت منها. 
- جميع عمليات الإيداع تخضع للمراجعة والموافقة من قبل الإدارة.
- السحب يتم وفق شروط الباقة المفعلة ودورة السحب المحددة داخل النظام.

5️⃣ الأرباح
- الأرباح تُحتسب وفق النظام الداخلي الخاص بالباقة المفعلة.
- الأرباح الظاهرة داخل الحساب  تُصبح قابلة للسحب  عند تحقق شروط السحب.

6️⃣ الحسابات
- يمنع إنشاء أكثر من حساب لنفس الشخص.
- يحق للإدارة تجميد أو حظر أو حذف أي حساب مخالف أو وهمي أو يستخدم بيانات غير صحيحة.

7️⃣ التوثيق والتحقق
- يحق للإدارة طلب توثيق الهوية أو أي معلومات إضافية قبل تفعيل الحساب أو تنفيذ بعض العمليات.
- أي بيانات أو وثائق غير صحيحة قد تؤدي إلى رفض الطلب أو إيقاف الحساب.

8️⃣ الدعم الفني
- يحق للمستخدم مراسلة الدعم ضمن حدود الاستخدام المشروع.
- يمنع إساءة استخدام الدعم أو إرسال رسائل مزعجة أو مضللة، ويحق للإدارة تقييد هذه الخدمة عند المخالفة.

9️⃣ التعديلات والإدارة
- عند اجراء تحديثات على النظام الداخلي للمنصة سيتم ابلاغ العملاء قبل مدة محددة .

🔟 تفاصيل الباقات
- تختلف الباقات فيما بينها فقط في فترة السحب، والتي تتراوح من 10 إلى 30 يوم حسب نوع الباقة.
- نسبة الربح اليومي ثابتة لجميع الباقات، وهي 2% من رأس المال.

━━━━━━━━━━━━━━━

⚠️ تنبيه مهم:
بضغطك على زر الموافقة وإكمال إنشاء الحساب، فإنك تؤكد أنك قرأت الشروط المذكورة أعلاه ووافقت عليها بالكامل.

هل توافق على شروط الاستخدام؟"""

PLAN_LEVELS = {
    "الباقة الفضية": 1,
    "الباقة الذهبية": 2,
    "باقة VIP": 3
}


# =========================
# دوال الوقت
# =========================
def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def format_timestamp(ts):
    if not ts:
        return "غير متوفر"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))
    except:
        return "غير متوفر"
    
def get_user_timezone(username):
    tz_name = user_timezone.get(username, "Europe/Vienna")

    try:
        ZoneInfo(tz_name)
        return tz_name
    except Exception:
        return "Europe/Vienna"


def format_timestamp_for_user(ts, username):
    if not ts:
        return "غير متوفر"

    try:
        tz_name = get_user_timezone(username)
        dt = datetime.fromtimestamp(float(ts), ZoneInfo(tz_name))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return format_timestamp(ts)


def get_timezone_display_text(username):
    tz_name = get_user_timezone(username)

    mapping = {
        "Europe/Zurich": "سويسرا / Zurich",
        "Europe/Rome": "إيطاليا / Rome",
        "Europe/Madrid": "إسبانيا / Madrid",
        "Europe/Athens": "اليونان / Athens",
        "Europe/Warsaw": "بولندا / Warsaw",
        "Europe/Prague": "التشيك / Prague",
        "Europe/Bucharest": "رومانيا / Bucharest",
        "Europe/Budapest": "هنغاريا / Budapest",
        "Europe/Helsinki": "فنلندا / Helsinki",
        "Asia/Qatar": "قطر / Qatar",
        "Europe/Vienna": "النمسا / Vienna",
        "Europe/Berlin": "ألمانيا / Berlin",
        "Europe/Istanbul": "تركيا / Istanbul",
        "Asia/Riyadh": "السعودية / Riyadh",
        "Asia/Dubai": "الإمارات / Dubai",
        "Asia/Baghdad": "العراق / Baghdad",
        "Asia/Amman": "الأردن / Amman",
        "Asia/Damascus": "سوريا / Damascus",
        "Asia/Beirut": "لبنان / Beirut",
        "Africa/Cairo": "مصر / Cairo",
        "Asia/Gaza": "فلسطين / Gaza",
        "Europe/Amsterdam": "هولندا / Amsterdam",
        "Europe/Paris": "فرنسا / Paris",
        "Europe/Brussels": "بلجيكا / Brussels",
        "Europe/Stockholm": "السويد / Stockholm",
        "Europe/Copenhagen": "الدنمارك / Copenhagen",
        "Europe/Oslo": "النرويج / Oslo",
        "Europe/London": "بريطانيا / London",
        "America/New_York": "أمريكا / New York",
        "America/Toronto": "كندا / Toronto",
    }

    return mapping.get(tz_name, tz_name) 

def migrate_old_users_timezones():
    changed = False

    residence_timezone_map = {}

    for country_label, country_data in COUNTRY_TIMEZONES.items():
        country_name = country_data.get("country")
        timezone_name = country_data.get("timezone")

        if country_name and timezone_name:
            residence_timezone_map[country_name] = timezone_name

    residence_aliases = {
        "سوريا ادلب": "سوريا",
        "المانيا": "ألمانيا",
        "امريكا": "أمريكا - نيويورك",
        "أمريكا": "أمريكا - نيويورك",
        "كندا": "كندا - تورونتو",
        "بريطانيا": "بريطانيا",
        "انجلترا": "بريطانيا",
        "إنجلترا": "بريطانيا",
    }

    for username in users:
        if username in user_timezone and user_timezone.get(username):
            continue

        residence = user_residence.get(username)

        if not residence:
            continue

        normalized_residence = residence_aliases.get(residence, residence)

        if normalized_residence in residence_timezone_map:
            user_timezone[username] = residence_timezone_map[normalized_residence]
            changed = True

    if changed:
        save_data()   
    
# =========================
# PostgreSQL Storage - Connection Pool
# =========================
def init_db_pool():
    global db_pool

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL غير موجود. تأكد من إضافته داخل Render Environment.")

    if db_pool is None:
        db_pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor
        )


def get_db_connection():
    global db_pool

    if db_pool is None:
        init_db_pool()

    return db_pool.getconn()


def release_db_connection(conn):
    global db_pool

    if db_pool is not None and conn is not None:
        db_pool.putconn(conn)


def close_db_pool():
    global db_pool

    if db_pool is not None:
        db_pool.closeall()
        db_pool = None


def init_db():
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_storage (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL
            );
        """)

        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"خطأ في init_db: {e}")
        raise

    finally:
        if cur:
            cur.close()
        release_db_connection(conn)


def db_get(key, default_value):
    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT value FROM bot_storage WHERE key = %s;", (key,))
        row = cur.fetchone()

        if row:
            return row["value"]

        return default_value

    except Exception as e:
        print(f"خطأ في db_get للعنصر {key}: {e}")
        return default_value

    finally:
        if cur:
            cur.close()
        release_db_connection(conn)


def db_set(key, value):
    conn = None
    cur = None

    try:
        conn = get_db_connection()
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
        print(f"خطأ في db_set للعنصر {key}: {e}")
        raise

    finally:
        if cur:
            cur.close()
        release_db_connection(conn)    
    

# =========================
# تحميل / حفظ البيانات
# =========================
def load_users():
    global users
    users = db_get("users", {})


def save_users():
    db_set("users", users)


def load_chat_ids():
    global chat_ids
    chat_ids = db_get("chat_ids", [])


def save_chat_ids():
    db_set("chat_ids", chat_ids)


def load_data():
    global user_plans, user_balance, transactions
    global user_deposits, user_last_profit
    global user_withdraw_logs, user_deposit_logs
    global pending_deposit_requests, pending_withdraw_requests
    global logged_in_users, user_statuses, support_blocked_users
    global user_telegram_ids, subscriptions_open, bot_maintenance_mode
    global pending_verification_requests, user_residence, user_full_name, verified_users
    global user_referrer, referral_bonus_paid
    global user_first_deposit_time, user_last_withdraw_time
    global capital_withdraw_requests, stopped_profit_users
    global support_waiting_reply, support_employees_enabled, support_claims, support_message_copies
    global admin_sent_batches, admin_last_batch_id
    global deleted_accounts_log
    global manual_withdraw_open
    global user_created_time
    global user_tree_views
    global user_wallet_address
    global user_wallet_network
    global user_identity_photos
    global user_timezone
    global pending_profit_capital_activation

    data = db_get("data", {})

    user_plans = data.get("user_plans", {})
    user_balance = data.get("user_balance", {})
    transactions = data.get("transactions", {})
    user_deposits = data.get("user_deposits", {})
    user_last_profit = data.get("user_last_profit", {})
    user_withdraw_logs = data.get("user_withdraw_logs", {})
    user_deposit_logs = data.get("user_deposit_logs", {})
    support_blocked_users = data.get("support_blocked_users", {})
    user_first_deposit_time = data.get("user_first_deposit_time", {})
    user_last_withdraw_time = data.get("user_last_withdraw_time", {})
    user_telegram_ids = data.get("user_telegram_ids", {})
    subscriptions_open = data.get("subscriptions_open", True)
    bot_maintenance_mode = data.get("bot_maintenance_mode", False)

    pending_verification_requests = {
        int(k): v for k, v in data.get("pending_verification_requests", {}).items()
    }

    user_residence = data.get("user_residence", {})
    user_full_name = data.get("user_full_name", {})
    verified_users = data.get("verified_users", {})
    user_referrer = data.get("user_referrer", {})
    referral_bonus_paid = data.get("referral_bonus_paid", {})

    capital_withdraw_requests = {
        int(k): v for k, v in data.get("capital_withdraw_requests", {}).items()
    }

    stopped_profit_users = data.get("stopped_profit_users", {})
    support_waiting_reply = data.get("support_waiting_reply", {})
    support_employees_enabled = data.get("support_employees_enabled", False)
    support_claims = data.get("support_claims", {})
    support_message_copies = data.get("support_message_copies", {})
    admin_sent_batches = data.get("admin_sent_batches", {})
    admin_last_batch_id = data.get("admin_last_batch_id", None)
    deleted_accounts_log = data.get("deleted_accounts_log", [])
    manual_withdraw_open = data.get("manual_withdraw_open", {})
    user_created_time = data.get("user_created_time", {})
    user_tree_views = data.get("user_tree_views", {})
    user_wallet_address = data.get("user_wallet_address", {})
    user_wallet_network = data.get("user_wallet_network", {})
    user_identity_photos = data.get("user_identity_photos", {})
    user_timezone = data.get("user_timezone", {})
    pending_profit_capital_activation = data.get("pending_profit_capital_activation", {})

    pending_deposit_requests = {
        int(k): v for k, v in data.get("pending_deposit_requests", {}).items()
    }

    pending_withdraw_requests = {
        int(k): v for k, v in data.get("pending_withdraw_requests", {}).items()
    }

    logged_in_users = {
        int(k): v for k, v in data.get("logged_in_users", {}).items()
    }

    user_statuses = data.get("user_statuses", {})


def save_data():
    data = {
        "user_plans": user_plans,
        "user_balance": user_balance,
        "transactions": transactions,
        "user_deposits": user_deposits,
        "user_last_profit": user_last_profit,
        "user_withdraw_logs": user_withdraw_logs,
        "user_deposit_logs": user_deposit_logs,
        "support_blocked_users": support_blocked_users,
        "user_first_deposit_time": user_first_deposit_time,
        "user_last_withdraw_time": user_last_withdraw_time,
        "user_telegram_ids": user_telegram_ids,
        "subscriptions_open": subscriptions_open,
        "bot_maintenance_mode": bot_maintenance_mode,
        "pending_verification_requests": {str(k): v for k, v in pending_verification_requests.items()},
        "user_residence": user_residence,
        "user_full_name": user_full_name,
        "verified_users": verified_users,
        "user_referrer": user_referrer,
        "referral_bonus_paid": referral_bonus_paid,
        "capital_withdraw_requests": {str(k): v for k, v in capital_withdraw_requests.items()},
        "stopped_profit_users": stopped_profit_users,
        "support_waiting_reply": support_waiting_reply,
        "support_employees_enabled": support_employees_enabled,
        "support_claims": support_claims,
        "support_message_copies": support_message_copies,
        "admin_sent_batches": admin_sent_batches,
        "admin_last_batch_id": admin_last_batch_id,
        "deleted_accounts_log": deleted_accounts_log,
        "manual_withdraw_open": manual_withdraw_open,
        "user_created_time": user_created_time,
        "user_tree_views": user_tree_views,
        "user_wallet_address": user_wallet_address,
        "user_wallet_network": user_wallet_network,
        "user_identity_photos": user_identity_photos,
        "user_timezone": user_timezone,
        "pending_profit_capital_activation": pending_profit_capital_activation,
        "pending_deposit_requests": {str(k): v for k, v in pending_deposit_requests.items()},
        "pending_withdraw_requests": {str(k): v for k, v in pending_withdraw_requests.items()},
        "logged_in_users": {str(k): v for k, v in logged_in_users.items()},
        "user_statuses": user_statuses,
    }

    db_set("data", data)

def is_support_blocked(username):
    return bool(support_blocked_users.get(username, False))


def get_support_status_text(username):
    return "محجوب من الدعم 🚫" if is_support_blocked(username) else "مسموح له بالدعم ✅"

# =========================
# نظام موظفي الدعم
# =========================
def is_support_employee(user_id):
    try:
        return int(user_id) in [int(x) for x in SUPPORT_EMPLOYEE_IDS]
    except:
        return False


def is_support_operator(user_id):
    try:
        return int(user_id) == int(ADMIN_ID) or is_support_employee(user_id)
    except:
        return False


def get_support_operator_text(user_id):
    if int(user_id) == int(ADMIN_ID):
        return "المدير"
    if is_support_employee(user_id):
        return "موظف دعم"
    return "غير مصرح"


def get_support_employees_status_text():
    return "مفعّل ✅" if support_employees_enabled else "متوقف ⛔"


def cleanup_expired_support_claim(username):
    claim = support_claims.get(username)

    if not claim:
        return

    expires_at = float(claim.get("expires_at", 0))

    if time.time() >= expires_at:
        support_claims.pop(username, None)
        save_data()


def has_active_support_claim(username):
    cleanup_expired_support_claim(username)
    return username in support_claims


def get_support_claim_employee_id(username):
    if not has_active_support_claim(username):
        return None

    try:
        return int(support_claims[username].get("employee_id"))
    except:
        return None


def claim_support_user(username, employee_id):
    support_claims[username] = {
        "employee_id": int(employee_id),
        "expires_at": time.time() + (15 * 60)
    }
    save_data()


def build_support_reply_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ رد على المستخدم", callback_data=f"reply_support_{user_id}")]
    ])


def get_support_recipients_for_user(username):
    recipients = [int(ADMIN_ID)]

    if support_employees_enabled:
        if has_active_support_claim(username):
            employee_id = get_support_claim_employee_id(username)
            if employee_id:
                recipients.append(int(employee_id))
        else:
            for employee_id in SUPPORT_EMPLOYEE_IDS:
                try:
                    recipients.append(int(employee_id))
                except:
                    pass

    unique_recipients = []
    for recipient_id in recipients:
        if recipient_id not in unique_recipients:
            unique_recipients.append(recipient_id)

    return unique_recipients


async def delete_support_message_from_other_employees(context, target_user_id, keep_employee_id):
    copies = support_message_copies.get(str(target_user_id), [])

    for item in copies:
        try:
            chat_id = int(item.get("chat_id"))
            message_id = int(item.get("message_id"))
            role = item.get("role", "")

            if role == "employee" and chat_id != int(keep_employee_id):
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=message_id
                )
        except Exception as e:
            print(f"تعذر حذف نسخة رسالة الدعم من موظف آخر: {e}")


async def send_support_text_to_operators(context, target_user_id, username, message_text, reply_markup):
    sent_copies = []

    for recipient_id in get_support_recipients_for_user(username):
        try:
            sent_msg = await context.bot.send_message(
                chat_id=recipient_id,
                text=message_text,
                reply_markup=reply_markup
            )

            sent_copies.append({
                "chat_id": int(recipient_id),
                "message_id": sent_msg.message_id,
                "role": "manager" if int(recipient_id) == int(ADMIN_ID) else "employee"
            })

            await asyncio.sleep(0.05)

        except Exception as e:
            print(f"خطأ في إرسال رسالة الدعم إلى {recipient_id}: {e}")

    support_message_copies[str(target_user_id)] = sent_copies
    save_data()


async def send_support_photo_to_operators(context, target_user_id, username, photo_file_id, caption_text, reply_markup):
    sent_copies = []

    for recipient_id in get_support_recipients_for_user(username):
        try:
            sent_msg = await context.bot.send_photo(
                chat_id=recipient_id,
                photo=photo_file_id,
                caption=caption_text,
                reply_markup=reply_markup
            )

            sent_copies.append({
                "chat_id": int(recipient_id),
                "message_id": sent_msg.message_id,
                "role": "manager" if int(recipient_id) == int(ADMIN_ID) else "employee"
            })

            await asyncio.sleep(0.05)

        except Exception as e:
            print(f"خطأ في إرسال صورة الدعم إلى {recipient_id}: {e}")

    support_message_copies[str(target_user_id)] = sent_copies
    save_data()

def ensure_user_defaults(username):
    if username not in user_statuses:
        user_statuses[username] = "active"


def add_transaction(username, tx_type, amount, note=""):
    transactions.setdefault(username, []).append({
        "type": tx_type,
        "amount": round(float(amount), 2),
        "note": note,
        "time": now_str()
    })
    save_data()


# =========================
# دوال مالية مساعدة
# =========================
def get_user_capital(username):
    return round(float(user_deposits.get(username, 0)), 2)

def get_saved_telegram_id(username):
    tg_id = user_telegram_ids.get(username)
    if tg_id is None:
        return None
    try:
        return int(tg_id)
    except:
        return None


def get_user_total_balance(username):
    return round(float(user_balance.get(username, 0)), 2)

def get_user_profit_only(username):
    capital = get_user_capital(username)
    balance = get_user_total_balance(username)
    profit_only = round(balance - capital, 2)
    return profit_only if profit_only > 0 else 0.0

def get_profit_capital_for_user(username):
    pending_data = pending_profit_capital_activation.get(username)

    if not pending_data:
        return get_user_capital(username)

    activate_at = float(pending_data.get("activate_at", 0))
    old_capital = round(float(pending_data.get("old_capital", 0)), 2)

    if time.time() < activate_at:
        return old_capital

    pending_profit_capital_activation.pop(username, None)
    save_data()
    return get_user_capital(username)


def get_daily_profit_amount(username):
    capital = get_profit_capital_for_user(username)
    if capital <= 0:
        return 0.0
    return round(capital * 0.02, 2)

def get_min_withdraw_amount(username):
    capital = get_user_capital(username)
    return round(capital * 0.20, 2)

def update_profit(username):
    if username not in user_deposits:
        return

    if stopped_profit_users.get(username, False):
        return

    total_capital = float(user_deposits.get(username, 0))
    if total_capital <= 0:
        return

    now = time.time()
    last_time = float(user_last_profit.get(username, now))
    days_passed = int((now - last_time) // 86400)

    if days_passed <= 0:
        return

    pending_data = pending_profit_capital_activation.get(username)
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
        user_balance[username] = round(float(user_balance.get(username, 0)) + total_profit, 2)

    user_last_profit[username] = last_time + (days_passed * 86400)

    if activated_during_update:
        pending_profit_capital_activation.pop(username, None)

    add_transaction(
        username,
        "profit",
        total_profit,
        f"إضافة أرباح {days_passed} يوم"
    )

    save_data()

def get_next_profit_time(username):
    last_time = float(user_last_profit.get(username, time.time()))
    next_time = last_time + 86400
    return format_timestamp_for_user(next_time, username)

def find_user_id_by_username(username):
    return get_saved_telegram_id(username)

def find_username_by_telegram_id(user_id):
    for username, tg_id in user_telegram_ids.items():
        try:
            if int(tg_id) == int(user_id):
                return username
        except:
            pass
    return None

def get_referrer_of_user(username):
    return user_referrer.get(username, "لا يوجد")

def get_invited_users(username):
    invited = [user for user, referrer in user_referrer.items() if referrer == username]
    return invited

def get_users_by_status(status):
    result = [u for u in users if get_user_status(u) == status]
    return sorted(result, key=lambda u: user_created_time.get(u, 0))


def get_root_users_by_status(status):
    result = []

    for username in users:
        if get_user_status(username) != status:
            continue

        referrer = user_referrer.get(username)

        # المستخدم يعتبر جذرًا إذا لم يكن لديه داعٍ حقيقي
        if referrer in [None, "", "بدون دعوة", "غير محدد"]:
            result.append(username)
        elif referrer not in users:
            result.append(username)

    return sorted(result, key=lambda u: user_created_time.get(u, 0))


def get_direct_invited_users_by_status(parent_username, status):
    invited = []

    for username, referrer in user_referrer.items():
        if referrer == parent_username and username in users:
            if get_user_status(username) == status:
                invited.append(username)

    return sorted(invited, key=lambda u: user_created_time.get(u, 0))


def get_invited_count_by_status(username, status):
    return len(get_direct_invited_users_by_status(username, status))

def get_all_root_users():
    result = []

    for username in users:
        referrer = user_referrer.get(username)

        # يعتبر جذرًا إذا دخل بدون دعوة أو كان الداعي غير موجود
        if referrer in [None, "", "بدون دعوة", "غير محدد"]:
            result.append(username)
        elif referrer not in users:
            result.append(username)

    return sorted(result, key=lambda u: user_created_time.get(u, 0))


def get_all_direct_invited_users(parent_username):
    invited = []

    for username, referrer in user_referrer.items():
        if referrer == parent_username and username in users:
            invited.append(username)

    return sorted(invited, key=lambda u: user_created_time.get(u, 0))


def get_all_invited_count(username):
    return len(get_all_direct_invited_users(username))

def build_referral_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"


def get_referrer_from_start_payload(payload, current_user_id):
    if not payload:
        return None

    if not payload.startswith("ref_"):
        return None

    try:
        inviter_id = int(payload.replace("ref_", "", 1))
    except:
        return None

    if int(inviter_id) == int(current_user_id):
        return None

    inviter_username = find_username_by_telegram_id(inviter_id)

    if inviter_username and inviter_username in users:
        return inviter_username

    return None


def get_status_badge(username):
    status = get_user_status(username)

    if status == "active":
        return "✅ نشط"
    elif status == "frozen":
        return "⚠️ مجمد"
    elif status == "banned":
        return "⛔ محظور"

    return "❓ غير معروف"

def generate_tree_view_id():
    return str(int(time.time() * 1000))


def create_tree_view(view_type, usernames, title, status=None, parent_username=None, back_view_id=None):
    view_id = generate_tree_view_id()

    user_tree_views[view_id] = {
        "view_type": view_type,
        "status": status,
        "usernames": usernames,
        "title": title,
        "parent_username": parent_username,
        "back_view_id": back_view_id
    }

    save_data()
    return view_id

def get_tree_view(view_id):
    return user_tree_views.get(view_id)


def cleanup_tree_views(max_items=1000):
    if len(user_tree_views) <= max_items:
        return

    # نحذف الأقدم بناءً على ترتيب الإدخال
    extra_count = len(user_tree_views) - max_items
    old_keys = list(user_tree_views.keys())[:extra_count]

    for key in old_keys:
        user_tree_views.pop(key, None)

    save_data()

def get_user_status(username):
    ensure_user_defaults(username)
    return user_statuses.get(username, "active")

def get_status_text(username):
    status = get_user_status(username)
    mapping = {
        "active": "نشط ✅",
        "frozen": "مجمد ماليًا ⚠️",
        "banned": "محظور ⛔"
    }
    return mapping.get(status, status)

def get_subscriptions_status_text():
    return "مفتوح ✅" if subscriptions_open else "متوقف ⛔"

def get_bot_maintenance_status_text():
    return "متوقف للصيانة ⛔" if bot_maintenance_mode else "يعمل طبيعيًا ✅"

def is_user_banned(username):
    return get_user_status(username) == "banned"

def is_user_frozen(username):
    return get_user_status(username) == "frozen"

def is_user_verified(username):
    return bool(verified_users.get(username, False))

def get_withdraw_interval_days(username):
    plan_name = user_plans.get(username)
    if not plan_name or plan_name not in PLANS:
        return None
    return PLANS[plan_name]["withdraw_days"]

def get_next_withdraw_timestamp(username):
    interval_days = get_withdraw_interval_days(username)
    if not interval_days:
        return None

    base_time = None

    # إذا يوجد سحب سابق، احسب من آخر سحب
    if username in user_last_withdraw_time:
        base_time = float(user_last_withdraw_time[username])
    # وإلا احسب من أول إيداع
    elif username in user_first_deposit_time:
        base_time = float(user_first_deposit_time[username])
    else:
        return None

    return base_time + (interval_days * 86400)

def get_next_withdraw_datetime_text(username):
    next_ts = get_next_withdraw_timestamp(username)
    if not next_ts:
        return "غير متاح"
    return format_timestamp_for_user(next_ts, username)

def get_withdraw_countdown_text(username):
    next_ts = get_next_withdraw_timestamp(username)
    if not next_ts:
        return "غير متاح"

    now = time.time()
    diff = int(next_ts - now)

    if diff <= 0:
        return "متاح الآن ✅"

    days = diff // 86400
    hours = (diff % 86400) // 3600
    minutes = (diff % 3600) // 60
    seconds = diff % 60

    return f"{days} يوم، {hours} ساعة، {minutes} دقيقة، {seconds} ثانية"

def is_withdraw_available_now(username):
    next_ts = get_next_withdraw_timestamp(username)
    if not next_ts:
        return False
    return time.time() >= next_ts

def is_manual_withdraw_open(username):
    data = manual_withdraw_open.get(username, {})
    return bool(data.get("is_open", False))

PROFIT_REINVEST_WINDOW_SECONDS = 3600  # ساعة واحدة


def get_profit_reinvest_available_until(username):
    now = time.time()

    manual_data = manual_withdraw_open.get(username)
    if manual_data and manual_data.get("is_open", False):
        opened_at = float(manual_data.get("opened_at", 0))
        until_ts = opened_at + PROFIT_REINVEST_WINDOW_SECONDS

        if now <= until_ts:
            return until_ts

        return None

    next_withdraw_ts = get_next_withdraw_timestamp(username)

    if not next_withdraw_ts:
        return None

    until_ts = float(next_withdraw_ts) + PROFIT_REINVEST_WINDOW_SECONDS

    if float(next_withdraw_ts) <= now <= until_ts:
        return until_ts

    return None


def is_profit_reinvest_available(username):
    return get_profit_reinvest_available_until(username) is not None


def get_profit_reinvest_countdown_text(username):
    until_ts = get_profit_reinvest_available_until(username)

    if not until_ts:
        return "غير متاح"

    diff = int(until_ts - time.time())

    if diff <= 0:
        return "انتهت المدة"

    minutes = diff // 60
    seconds = diff % 60

    return f"{minutes} دقيقة، {seconds} ثانية"


def build_profit_reinvest_confirm_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ موافق", callback_data="confirm_profit_reinvest"),
            InlineKeyboardButton("🔙 رجوع", callback_data="cancel_profit_reinvest")
        ]
    ])

def close_manual_withdraw_for_user(username):
    if username not in users:
        return False, "❌ المستخدم غير موجود"

    if not is_manual_withdraw_open(username):
        return False, "ℹ️ لا يوجد فتح سحب يدوي مفعل لهذا المستخدم"

    saved_data = manual_withdraw_open.get(username, {})
    original_last_withdraw_time = saved_data.get("original_last_withdraw_time", None)

    if original_last_withdraw_time is None:
        user_last_withdraw_time.pop(username, None)
    else:
        user_last_withdraw_time[username] = float(original_last_withdraw_time)

    manual_withdraw_open.pop(username, None)

    save_data()
    add_transaction(username, "admin_close_manual_withdraw", 0, "قام الأدمن بإيقاف فتح السحب وإعادة الوضع الطبيعي")

    return True, "✅ تم إيقاف فتح السحب وإعادة السحب إلى وضعه الطبيعي"

def open_withdraw_now_for_user(username):
    if username not in users:
        return False, "❌ المستخدم غير موجود"

    plan_name = user_plans.get(username)
    if plan_name in [None, "NONE"]:
        return False, "❌ لا توجد للمستخدم باقة مفعلة"

    if plan_name not in PLANS:
        return False, "❌ باقة المستخدم غير معروفة في النظام"

    if is_manual_withdraw_open(username):
        return False, "ℹ️ السحب مفتوح لهذا المستخدم بالفعل"

    interval_days = get_withdraw_interval_days(username)
    if not interval_days:
        return False, "❌ تعذر تحديد دورة السحب لهذا المستخدم"

    now = time.time()
    original_last_withdraw_time = user_last_withdraw_time.get(username, None)

    if username not in user_first_deposit_time:
        user_first_deposit_time[username] = now

    # فتح السحب الآن
    user_last_withdraw_time[username] = now - (interval_days * 86400)

    # تسجيل حالة الفتح اليدوي حتى يظهر زر الإغلاق
    manual_withdraw_open[username] = {
        "is_open": True,
        "original_last_withdraw_time": original_last_withdraw_time,
        "opened_at": now
    }

    save_data()
    add_transaction(username, "admin_open_withdraw", 0, "قام الأدمن بفتح السحب للمستخدم فورًا")

    return True, "✅ تم فتح السحب لهذا المستخدم بنجاح"

def delete_user_subscription_only(username):
    if username not in users:
        return False, "❌ المستخدم غير موجود"

    user_id_found = get_saved_telegram_id(username)

    old_plan = user_plans.get(username, "NONE")
    old_capital = get_user_capital(username)
    old_balance = get_user_total_balance(username)

    user_plans[username] = "NONE"
    user_balance[username] = 0
    user_deposits[username] = 0
    user_last_profit[username] = time.time()

    user_first_deposit_time.pop(username, None)
    user_last_withdraw_time.pop(username, None)
    stopped_profit_users.pop(username, None)
    manual_withdraw_open.pop(username, None)

    if user_id_found:
        pending_deposit_requests.pop(user_id_found, None)
        pending_withdraw_requests.pop(user_id_found, None)
        capital_withdraw_requests.pop(user_id_found, None)

    user_deposit_logs[username] = []
    user_withdraw_logs[username] = []

    add_transaction(
        username,
        "admin_delete_subscription",
        0,
        f"حذف الاشتراك بواسطة الأدمن | الباقة السابقة: {old_plan} | رأس المال السابق: {old_capital}$ | الرصيد السابق: {old_balance}$"
    )

    save_data()
    return True, "✅ تم حذف اشتراك المستخدم بنجاح"

# =========================
# واجهة بحث الأدمن
# =========================
def build_admin_user_text(username):
    ensure_user_defaults(username)
    update_profit(username)
    full_name = user_full_name.get(username, "غير متوفر")
    residence = user_residence.get(username, "غير متوفر")
    password = users.get(username, "غير متوفر")
    verified_text = "موثق ✅" if verified_users.get(username, False) else "غير موثق ❌"
    referrer_name = get_referrer_of_user(username)
    invited_users = get_invited_users(username)
    invited_count = len(invited_users)
    invited_users_text = ", ".join(invited_users) if invited_users else "لا يوجد"

    plan = user_plans.get(username, "NONE")
    capital = get_user_capital(username)
    balance = get_user_total_balance(username)
    profit_only = get_user_profit_only(username)
    deposit_count = len(user_deposit_logs.get(username, []))
    withdraw_count = len(user_withdraw_logs.get(username, []))
    tx_count = len(transactions.get(username, []))
    user_id_found = get_saved_telegram_id(username)

    has_pending_dep = "نعم" if user_id_found in pending_deposit_requests else "لا"
    has_pending_wd = "نعم" if user_id_found in pending_withdraw_requests else "لا"

    first_deposit = format_timestamp(user_first_deposit_time.get(username))
    last_withdraw = format_timestamp(user_last_withdraw_time.get(username))
    next_withdraw = get_next_withdraw_datetime_text(username)
    withdraw_countdown = get_withdraw_countdown_text(username)

    return (
        f"📋 بيانات المستخدم: {username}\n\n"
        f"🆔 Telegram ID: {user_id_found if user_id_found else 'غير متصل حالياً'}\n"
        f"🔑 كلمة المرور: {password}\n"
        f"👤 الاسم والكنية: {full_name}\n"
        f"🏠 مكان الإقامة: {residence}\n"
        f"🪪 حالة التوثيق: {verified_text}\n"
        f"📌 حالة الحساب: {get_status_text(username)}\n"
        f"📩 حالة الدعم: {get_support_status_text(username)}\n"
        f"👤 الداعي: {referrer_name}\n"
        f"👥 عدد المدعوين عن طريقه: {invited_count}\n"
        f"📋 قائمة المدعوين: {invited_users_text}\n"
        f"📦 الباقة: {plan}\n"
        f"💰 رأس المال: {capital}$\n"
        f"📈 الرصيد الحالي: {balance}$\n"
        f"💵 الأرباح فقط: {profit_only}$\n"
        f"📥 عدد الإيداعات: {deposit_count}\n"
        f"💸 عدد السحوبات: {withdraw_count}\n"
        f"📜 عدد العمليات: {tx_count}\n"
        f"🕒 أول إيداع: {first_deposit}\n"
        f"🕒 آخر سحب: {last_withdraw}\n"
        f"💸 موعد السحب القادم: {next_withdraw}\n"
        f"⌛ العد التنازلي للسحب: {withdraw_countdown}\n"
        f"📥 طلب إيداع معلق: {has_pending_dep}\n"
        f"💸 طلب سحب معلق: {has_pending_wd}\n"
        f"⏰ الربح القادم: {get_next_profit_time(username)}"
    )

def build_admin_user_keyboard(username):
    status = get_user_status(username)

    row1 = []
    row2 = []
    row3 = []
    row4 = []

    if status == "banned":
        row1.append(InlineKeyboardButton("✅ فك الحظر", callback_data=f"admin_unban_{username}"))
    else:
        row1.append(InlineKeyboardButton("⛔ حظر", callback_data=f"admin_ban_{username}"))

    if status == "frozen":
        row1.append(InlineKeyboardButton("🔓 إزالة التجميد", callback_data=f"admin_unfreeze_{username}"))
    else:
        row1.append(InlineKeyboardButton("❄️ تجميد", callback_data=f"admin_freeze_{username}"))

    if is_support_blocked(username):
        row2.append(InlineKeyboardButton("✅ فك حظر الدعم", callback_data=f"admin_unblocksupport_{username}"))
    else:
        row2.append(InlineKeyboardButton("🚫 حظر الدعم", callback_data=f"admin_blocksupport_{username}"))
     
    row2.append(InlineKeyboardButton("🪪 البطاقة الشخصية", callback_data=f"admin_identity_{username}"))

    row3.append(InlineKeyboardButton("➕ إضافة رصيد", callback_data=f"admin_addbalance_{username}"))
    row3.append(InlineKeyboardButton("➖ خصم رصيد", callback_data=f"admin_subbalance_{username}"))

    row4.append(InlineKeyboardButton("📦 تغيير الباقة", callback_data=f"admin_setplan_{username}"))
    row4.append(InlineKeyboardButton("♻️ إعادة ضبط السحب", callback_data=f"admin_resetwithdraw_{username}"))

    if is_manual_withdraw_open(username):
        withdraw_button = InlineKeyboardButton("🔒 إيقاف فتح السحب", callback_data=f"admin_closewithdraw_{username}")
    else:
        withdraw_button = InlineKeyboardButton("💸 فتح السحب", callback_data=f"admin_openwithdraw_{username}")

    row5 = [
        withdraw_button,
        InlineKeyboardButton("🔄 تحديث", callback_data=f"admin_refresh_{username}")
    ]

    row6 = [
    InlineKeyboardButton("📜 آخر العمليات", callback_data=f"admin_tx_{username}"),
    InlineKeyboardButton("📨 إرسال رسالة", callback_data=f"admin_message_{username}")
]

    row7 = [
    InlineKeyboardButton("🗑 حذف الاشتراك", callback_data=f"admin_delete_subscription_{username}")
]

    return InlineKeyboardMarkup([row1, row2, row3, row4, row5, row6, row7])

def build_delete_subscription_confirm_keyboard(username):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأكيد حذف الاشتراك", callback_data=f"admin_confirm_delete_subscription_{username}")
        ],
        [
            InlineKeyboardButton("❌ إلغاء", callback_data=f"admin_cancel_delete_subscription_{username}")
        ]
    ])

def build_user_transactions_text(username, limit=10):
    user_transactions = transactions.get(username, [])

    if not user_transactions:
        return f"📭 لا يوجد سجل عمليات للمستخدم {username}"

    last_items = user_transactions[-limit:]
    lines = [
        f"📜 آخر العمليات للمستخدم {username}",
        f"📌 الحالة: {get_status_text(username)}",
        f"📦 الباقة: {user_plans.get(username, 'NONE')}",
        "➖➖➖➖➖"
    ]

    for tx in reversed(last_items):
        tx_type = tx.get("type", "unknown")
        amount = tx.get("amount", 0)
        tx_time = tx.get("time", "بدون وقت")
        note = tx.get("note", "")

        lines.append(
            f"🔹 النوع: {tx_type}\n"
            f"💰 المبلغ: {amount}$\n"
            f"📝 ملاحظة: {note if note else '---'}\n"
            f"🕒 الوقت: {tx_time}\n"
            f"➖➖➖➖➖"
        )

    return "\n".join(lines)

def build_user_financial_history_text(username, limit=20):
    items = []

    # =========================
    # 1) الإيداعات المسجلة في السجل
    # =========================
    deposit_logs = user_deposit_logs.get(username, [])

    for dep in deposit_logs:
        items.append({
            "kind": "deposit",
            "amount": round(float(dep.get("amount", 0)), 2),
            "time": dep.get("time", "بدون وقت"),
            "status": dep.get("status", "approved"),
            "note": dep.get("note", "")
        })

    # =========================
    # 2) السحوبات المسجلة في السجل
    # =========================
    withdraw_logs = user_withdraw_logs.get(username, [])

    for wd in withdraw_logs:
        items.append({
            "kind": "withdraw",
            "amount": round(float(wd.get("amount", 0)), 2),
            "time": wd.get("time", "بدون وقت"),
            "status": wd.get("status", "unknown"),
            "note": wd.get("note", "")
        })

    # =========================
    # 3) طلبات الإيداع المعلقة حاليًا
    # =========================
    user_id = get_saved_telegram_id(username)

    if user_id and user_id in pending_deposit_requests:
        req = pending_deposit_requests[user_id]

        items.append({
            "kind": "deposit",
            "amount": round(float(req.get("amount", 0)), 2),
            "time": req.get("time", now_str()),
            "status": "pending",
            "note": f"طلب إيداع قيد المراجعة | النوع: {req.get('type', 'new_deposit')} | الباقة: {req.get('plan', 'غير معروف')}"
        })

    # =========================
    # 4) طلبات سحب الأرباح المعلقة حاليًا
    # =========================
    if user_id and user_id in pending_withdraw_requests:
        req = pending_withdraw_requests[user_id]

        items.append({
            "kind": "withdraw",
            "amount": round(float(req.get("amount", 0)), 2),
            "time": req.get("time", now_str()),
            "status": "pending",
            "note": f"طلب سحب أرباح قيد المراجعة | الباقة: {req.get('plan', 'غير معروف')}"
        })

    # =========================
    # 5) طلب سحب رأس المال وإيقاف الربح
    # =========================
    if user_id and user_id in capital_withdraw_requests:
        req = capital_withdraw_requests[user_id]

        amount = round(float(req.get("amount", 0)), 2)
        request_time = format_timestamp(req.get("request_time"))
        due_time = format_timestamp(req.get("due_time"))
        countdown = get_capital_withdraw_countdown_text(username)

        items.append({
            "kind": "capital_withdraw",
            "amount": amount,
            "time": request_time,
            "status": "pending",
            "note": (
                f"طلب سحب رأس المال وإيقاف الربح\n"
                f"⏰ موعد الاستحقاق: {due_time}\n"
                f"⌛ الوقت المتبقي: {countdown}"
            )
        })

    # =========================
    # إذا لا يوجد أي شيء
    # =========================
    if not items:
        return "📭 لا يوجد لديك سجل عمليات حتى الآن"

    # =========================
    # ترتيب العمليات حسب الوقت
    # =========================
    def sort_key(item):
        return item.get("time", "")

    items = sorted(items, key=sort_key)[-limit:]

    lines = [
        "📜 سجل العمليات المالية",
        f"👤 المستخدم: {username}",
        "➖➖➖➖➖"
    ]

    for item in reversed(items):
        kind = item.get("kind")
        amount = item.get("amount", 0)
        tx_time = item.get("time", "بدون وقت")
        status = item.get("status", "unknown")
        note = item.get("note", "")

        status_text = {
            "approved": "تمت الموافقة ✅",
            "rejected": "مرفوض ❌",
            "pending": "قيد الانتظار ⏳",
            "unknown": "غير معروف"
        }.get(status, status)

        if kind == "deposit":
            lines.append(
                f"📥 إيداع\n"
                f"💰 المبلغ: {amount}$\n"
                f"📌 الحالة: {status_text}\n"
                f"🕒 الوقت: {tx_time}\n"
                f"📝 ملاحظة: {note if note else '---'}\n"
                f"➖➖➖➖➖"
            )

        elif kind == "withdraw":
            lines.append(
                f"💸 سحب أرباح\n"
                f"💰 المبلغ: {amount}$\n"
                f"📌 الحالة: {status_text}\n"
                f"🕒 الوقت: {tx_time}\n"
                f"📝 ملاحظة: {note if note else '---'}\n"
                f"➖➖➖➖➖"
            )

        elif kind == "capital_withdraw":
            lines.append(
                f"🏦 سحب رأس المال وإيقاف الربح\n"
                f"💰 المبلغ: {amount}$\n"
                f"📌 الحالة: {status_text}\n"
                f"🕒 وقت الطلب: {tx_time}\n"
                f"📝 التفاصيل:\n{note}\n"
                f"➖➖➖➖➖"
            )

    return "\n".join(lines)

def build_my_plan_text(username, user_id):
    ensure_user_defaults(username)
    update_profit(username)

    plan = user_plans.get(username, "لم يتم الاشتراك")
    capital = get_user_capital(username)
    balance = get_user_total_balance(username)
    profit_only = get_user_profit_only(username)
    daily_profit = get_daily_profit_amount(username)
    min_withdraw = get_min_withdraw_amount(username)
    verification_text = "تم التحقق ✅" if verified_users.get(username, False) else "غير موثق ❌"

    withdraw_verification_warning = ""
    if not is_user_verified(username):
        withdraw_verification_warning = (
            "⚠️ تنبيه مهم:\n"
            "حسابك غير موثق، ولن تستطيع سحب أي مبلغ حتى يتم توثيق الحساب.\n"
            "اضغط على زر 🪪 توثيق الحساب وابدأ التوثيق الآن.\n"
        )

    if plan in [None, "NONE"]:
        return "❌ لا توجد لديك باقة مفعلة حالياً"

    pending_dep = "نعم" if user_id in pending_deposit_requests else "لا"
    pending_wd = "نعم" if user_id in pending_withdraw_requests else "لا"

    next_withdraw_date = get_next_withdraw_datetime_text(username)
    withdraw_countdown = get_withdraw_countdown_text(username)

    capital_request = capital_withdraw_requests.get(user_id)
    capital_withdraw_text = "لا يوجد"
    profit_status_text = "يعمل ✅"

    pending_profit_data = pending_profit_capital_activation.get(username)
    profit_capital_text = f"{get_profit_capital_for_user(username)}$"

    delayed_profit_text = ""

    if pending_profit_data:
        activate_at = float(pending_profit_data.get("activate_at", 0))
        old_capital_for_profit = round(float(pending_profit_data.get("old_capital", 0)), 2)
        new_capital_for_profit = round(float(pending_profit_data.get("new_capital", capital)), 2)

        if time.time() < activate_at:
            delayed_profit_text = (
                f"⏳ ملاحظة الإيداع الجديد:\n"
                f"الأرباح الحالية تُحتسب مؤقتًا على رأس المال القديم: {old_capital_for_profit}$\n"
                f"وسيبدأ احتسابها على رأس المال الجديد: {new_capital_for_profit}$\n"
                f"بعد تاريخ: {format_timestamp_for_user(activate_at, username)}\n"
            )
        else:
            pending_profit_capital_activation.pop(username, None)
            save_data()

    if capital_request:
        capital_withdraw_text = get_capital_withdraw_countdown_text(username)
        profit_status_text = "متوقف ⛔"

    return (
    f"📦 باقتك الحالية: {plan}\n"
    f"📌 حالة الحساب: {get_status_text(username)} | {verification_text}\n"
    f"{withdraw_verification_warning}"
    f"💰 رأس المال: {capital}$\n"
    f"📊 رأس المال المعتمد حاليًا لحساب الأرباح: {profit_capital_text}\n"
    f"📈 الرصيد الحالي: {balance}$\n"
    f"💵 الأرباح القابلة للسحب: {profit_only}$\n"
    f"🪙 ربحك اليومي الحالي: {daily_profit}$\n"
    f"{delayed_profit_text}"
    f"📉 الحد الأدنى لسحب الأرباح: {min_withdraw}$\n"
    f"📌 طريقة حساب الحد الأدنى: 20% من رأس المال المودع\n"
    f"📊 حالة الربح: {profit_status_text}\n"
    f"🌍 توقيت الحساب: {get_timezone_display_text(username)}\n"
    f"⏰ موعد الربح القادم: {get_next_profit_time(username)}\n"
    f"💸 موعد السحب القادم: {next_withdraw_date}\n"
    f"⌛ العد التنازلي للسحب: {withdraw_countdown}\n"
    f"🏦 عداد سحب رأس المال: {capital_withdraw_text}\n"
    f"📥 طلب إيداع معلق: {pending_dep}\n"
    f"💸 طلب سحب معلق: {pending_wd}"
)

def build_my_plan_keyboard(username=None):
    buttons = []

    if username and is_profit_reinvest_available(username):
        buttons.append([
            InlineKeyboardButton("🔁 استثمار الأرباح", callback_data="profit_reinvest")
        ])

    buttons.append([
        InlineKeyboardButton("🔄 تحديث العد التنازلي", callback_data="refresh_my_countdown")
    ])

    buttons.append([
        InlineKeyboardButton("📦 تغيير الباقة الحالية", callback_data="change_current_plan")
    ])

    return InlineKeyboardMarkup(buttons)


def build_promo_plans_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("الباقة الفضية", callback_data="promo_plan::الباقة الفضية"),
            InlineKeyboardButton("الباقة الذهبية", callback_data="promo_plan::الباقة الذهبية")
        ],
        [
            InlineKeyboardButton("باقة VIP", callback_data="promo_plan::باقة VIP")
        ]
    ])


def build_subscriber_reassurance_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 باقتي", callback_data="promo_my_plan")
        ]
    ])

def build_capital_withdraw_confirm_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأكيد", callback_data="confirm_capital_withdraw"),
            InlineKeyboardButton("❌ إلغاء", callback_data="cancel_capital_withdraw")
        ]
    ])

def build_data_entry_back_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔙 رجوع", callback_data="data_entry_back")
        ]
    ])

def build_delete_account_confirm_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأكيد حذف الحساب", callback_data="confirm_delete_my_account"),
            InlineKeyboardButton("🔙 رجوع", callback_data="cancel_delete_my_account")
        ]
    ])

def build_admin_delete_user_confirm_keyboard(username):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ موافقة", callback_data=f"admin_confirm_delete_user::{username}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"admin_cancel_delete_user::{username}")
        ]
    ])

def build_admin_set_plan_keyboard(username):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("الباقة الفضية", callback_data=f"admin_chooseplan::{username}::silver"),
            InlineKeyboardButton("الباقة الذهبية", callback_data=f"admin_chooseplan::{username}::gold")
        ],
        [
            InlineKeyboardButton("باقة VIP", callback_data=f"admin_chooseplan::{username}::vip")
        ]
    ])    
    
def build_user_tree_keyboard(view_id):
    view = get_tree_view(view_id)

    if not view:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_filter_menu")]
        ])

    status = view["status"]
    usernames = view["usernames"]
    back_view_id = view.get("back_view_id")

    buttons = []

    for username in usernames:
        invited_count = get_invited_count_by_status(username, status)
        button_text = f"{username} ({invited_count})"
        callback_data = f"treeuser::{view_id}::{username}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    if back_view_id:
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"treeback::{back_view_id}")])
    else:
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_filter_menu")])

    return InlineKeyboardMarkup(buttons)

def build_all_users_tree_keyboard(view_id):
    view = get_tree_view(view_id)

    if not view:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin_menu")]
        ])

    usernames = view["usernames"]
    back_view_id = view.get("back_view_id")

    buttons = []

    for username in usernames:
        status_badge = get_status_badge(username)
        children_count = get_all_invited_count(username)
        button_text = f"{username} | {status_badge} | {children_count}"
        callback_data = f"alltreeuser::{view_id}::{username}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    if back_view_id:
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"alltreeback::{back_view_id}")])
    else:
        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin_menu")])

    return InlineKeyboardMarkup(buttons)

def get_capital_withdraw_countdown_text(username):
    target_user_id = get_saved_telegram_id(username)
    if not target_user_id:
        return "غير متاح"

    request = capital_withdraw_requests.get(target_user_id)
    if not request:
        return "لا يوجد طلب"

    due_ts = float(request.get("due_time", 0))
    now = time.time()
    diff = int(due_ts - now)

    if diff <= 0:
        return "انتهت المدة ✅"

    days = diff // 86400
    hours = (diff % 86400) // 3600
    minutes = (diff % 3600) // 60
    seconds = diff % 60

    return f"{days} يوم، {hours} ساعة، {minutes} دقيقة، {seconds} ثانية"

def has_active_capital_withdraw_request(username):
    user_id = get_saved_telegram_id(username)

    if not user_id:
        return False

    return user_id in capital_withdraw_requests

def build_capital_withdraw_requests_text():
    if not capital_withdraw_requests:
        return "📭 لا توجد طلبات سحب رأس مال معلقة حالياً"

    lines = ["🏦 طلبات سحب رأس المال المعلقة:\n"]

    for user_id, request in capital_withdraw_requests.items():
        username = request.get("username", "غير معروف")
        amount = round(float(request.get("amount", 0)), 2)
        request_time = format_timestamp(request.get("request_time"))
        due_time = format_timestamp(request.get("due_time"))
        admin_notified = "نعم ✅" if request.get("admin_notified", False) else "لا ❌"
        wallet = request.get("wallet", "غير محفوظة")
        network = request.get("network", "غير محفوظة")

        now = time.time()
        diff = int(float(request.get("due_time", 0)) - now)

        if diff <= 0:
            countdown_text = "انتهت المدة ✅"
        else:
            days = diff // 86400
            hours = (diff % 86400) // 3600
            minutes = (diff % 3600) // 60
            seconds = diff % 60
            countdown_text = f"{days} يوم، {hours} ساعة، {minutes} دقيقة، {seconds} ثانية"

        lines.append(
            f"👤 المستخدم: {username}\n"
            f"🆔 ID: {user_id}\n"
            f"💰 المبلغ المطلوب: {amount}$\n"
            f"🕒 وقت الطلب: {request_time}\n"
            f"⏰ موعد الاستحقاق: {due_time}\n"
            f"⌛ الوقت المتبقي: {countdown_text}\n"
            f"💼 محفظة الإيداع: {wallet}\n"
            f"🌐 الشبكة: {network}\n"
            f"📨 تم إشعار الأدمن: {admin_notified}\n"
            f"➖➖➖➖➖"
        )

    return "\n".join(lines)

async def check_capital_withdraw_requests(context: ContextTypes.DEFAULT_TYPE):
    if not capital_withdraw_requests:
        return

    changed = False

    for user_id, request in list(capital_withdraw_requests.items()):
        if request.get("admin_notified", False):
            continue

        due_ts = float(request.get("due_time", 0))
        if due_ts <= 0:
            continue

        if time.time() >= due_ts:
            username = request.get("username", "غير معروف")
            amount = request.get("amount", 0)
            wallet = request.get("wallet", "غير محفوظة")
            network = request.get("network", "غير محفوظة")

            try:
                admin_markup = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✅ تم دفع سحب رأس المال",
                            callback_data=f"capital_paid_{user_id}"
                        )
                    ]
                ])

                await context.bot.send_message(
                     chat_id=ADMIN_ID,
                     text=(
                            f"⏰ تنبيه سحب رأس المال\n\n"
                            f"قام {username}\n بطلب سحب {amount}$ منذ عشرة أيام وحان الدفع الآن\n\n"
                            f"💼 عنوان محفظة الإيداع: {wallet}\n"
                            f"🌐 الشبكة: {network}"
                                   ),
                     reply_markup=admin_markup
                                                )
                capital_withdraw_requests[user_id]["admin_notified"] = True
                changed = True
            except Exception as e:
                print(f"خطأ في إرسال تنبيه سحب رأس المال للأدمن: {e}")

    if changed:
        save_data()

async def auto_update_all_profits(context: ContextTypes.DEFAULT_TYPE):
    changed = False

    for username in list(users.keys()):
        try:
            old_balance = round(float(user_balance.get(username, 0)), 2)

            update_profit(username)

            new_balance = round(float(user_balance.get(username, 0)), 2)

            if new_balance != old_balance:
                changed = True

        except Exception as e:
            print(f"خطأ أثناء تحديث الأرباح للمستخدم {username}: {e}")

    if changed:
        save_data()

async def send_unverified_account_reminders(context: ContextTypes.DEFAULT_TYPE):
    for username in list(users.keys()):
        try:
            # تجاهل الحسابات الموثقة
            if verified_users.get(username, False):
                continue

            # تجاهل الحسابات المحظورة
            if is_user_banned(username):
                continue

            user_id = get_saved_telegram_id(username)

            # إذا لا يوجد Telegram ID محفوظ لا يمكن إرسال الرسالة
            if not user_id:
                continue

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "⚠️ تنبيه هام\n\n"
                    "حسابك غير موثق حتى الآن.\n\n"
                    "بالتالي لن تستطيع سحب أي مبلغ من المنصة حتى يتم توثيق الحساب.\n\n"
                    "اضغط فورًا على زر:\n"
                    "🪪 توثيق الحساب\n\n"
                    "وابدأ عملية التوثيق الآن."
                ),
                reply_markup=main_menu_keyboard()
            )

            await asyncio.sleep(0.05)

        except Exception as e:
            print(f"خطأ في إرسال تنبيه التوثيق للمستخدم {username}: {e}")


NON_SUBSCRIBER_PROMO_MESSAGES = [
    (
        "🚀 بداية رأس المال تبدأ بخطوة واحدة\n\n"
        "لم تقم بتفعيل أي باقة حتى الآن.\n"
        "اختر الباقة المناسبة لك وابدأ بناء أرباحك اليومية خطوة بخطوة."
    ),
    (
        "💰 اجعل المال يعمل لصالحك\n\n"
        "يمكنك البدء برأس مال بسيط حسب الباقة المناسبة لك.\n"
        "كل يوم تأخير يعني فرصة أرباح ضائعة."
    ),
    (
        "📈 فرصة الاشتراك ما زالت أمامك\n\n"
        "فعّل باقتك وابدأ متابعة أرباحك اليومية من داخل حسابك.\n"
        "الاستمرارية هي سر بناء رأس المال."
    ),
    (
        "🏭 Money factory بانتظار تفعيلك\n\n"
        "اختر باقتك الآن وابدأ رحلة صناعة المال وبناء رأس مال للمستقبل."
    ),
    (
        "🔥 لا تترك حسابك بدون باقة\n\n"
        "فعّل اشتراكك واستفد من نظام الأرباح اليومية حسب الباقة التي تناسبك."
    )
]


SUBSCRIBER_REASSURANCE_MESSAGES = [
    (
        "💰 رأس مالك يعمل يوميًا\n\n"
        "أرباحك تُحتسب تلقائيًا حسب باقتك الحالية.\n"
        "تابع باقتك بانتظام وشاهد نمو رصيدك خطوة بخطوة."
    ),
    (
        "📈 الاستمرارية تصنع الفرق\n\n"
        "كل يوم يمر يعني خطوة جديدة في بناء رأس المال.\n"
        "نظام الأرباح مستمر حسب شروط باقتك."
    ),
    (
        "🏭 صناعة المال تحتاج صبرًا واستمرارًا\n\n"
        "حسابك مفعل، ورأس مالك يعمل ضمن النظام.\n"
        "تابع أرباحك من زر باقتي."
    ),
    (
        "✅ تذكير تطميني\n\n"
        "باقتك مفعلة، وأرباحك اليومية يتم احتسابها تلقائيًا.\n"
        "استمر في المتابعة لبناء رصيد أقوى مع الوقت."
    ),
    (
        "🔐 رأس مالك هو بداية الطريق\n\n"
        "كل متابعة لحسابك تقربك أكثر من هدفك المالي.\n"
        "افتح باقتك وراجع أرباحك الحالية."
    )
]


async def send_periodic_motivation_messages(context: ContextTypes.DEFAULT_TYPE):
    if bot_maintenance_mode:
        return

    for username in list(users.keys()):
        try:
            if is_user_banned(username):
                continue

            user_id = get_saved_telegram_id(username)
            if not user_id:
                continue

            plan = user_plans.get(username, "NONE")

            if plan in [None, "NONE"]:
                message_text = random.choice(NON_SUBSCRIBER_PROMO_MESSAGES)

                await context.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=build_promo_plans_keyboard()
                )

            elif plan in PLANS:
                update_profit(username)
                message_text = random.choice(SUBSCRIBER_REASSURANCE_MESSAGES)

                await context.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    reply_markup=build_subscriber_reassurance_keyboard()
                )

            await asyncio.sleep(0.05)

        except Exception as e:
            print(f"خطأ في إرسال الرسائل التحفيزية/التطمينية للمستخدم {username}: {e}")

def get_upgrade_plans(current_plan):
    current_level = PLAN_LEVELS.get(current_plan, 0)

    return [
        plan_name
        for plan_name in PLANS.keys()
        if PLAN_LEVELS.get(plan_name, 0) > current_level
    ]

def get_plan_by_capital_amount(amount):
    amount = float(amount)

    for plan_name, plan_data in PLANS.items():
        min_deposit = float(plan_data["min_deposit"])
        max_deposit = plan_data["max_deposit"]

        if max_deposit is None:
            if amount >= min_deposit:
                return plan_name
        else:
            if min_deposit <= amount <= float(max_deposit):
                return plan_name

    return None

def build_change_plan_keyboard(current_plan):
    upgrade_plans = get_upgrade_plans(current_plan)
    buttons = []

    if not upgrade_plans:
        buttons.append([InlineKeyboardButton("❌ لا يوجد باقات أعلى", callback_data="no_upgrade_available")])
    else:
        for plan_name in upgrade_plans:
            buttons.append([InlineKeyboardButton(plan_name, callback_data=f"select_new_plan::{plan_name}")])

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="change_plan_back_home")])

    return InlineKeyboardMarkup(buttons)

def build_plan_change_confirm_keyboard(target_plan):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 إيداع", callback_data=f"start_plan_change_deposit::{target_plan}"),
            InlineKeyboardButton("🔙 رجوع", callback_data="change_plan_back_home")
        ]
    ])

def build_plan_features_text(plan_name):
    if plan_name not in PLANS:
        return "❌ الباقة غير موجودة"

    plan = PLANS[plan_name]

    return (
        f"📦 تفاصيل {plan_name}\n\n"
        f"✅ اسم الباقة: {plan['name']}\n"
        f"💰 الحد الأدنى للإيداع: {plan['min_deposit']}$\n"
        f"💰 الحد الأعلى للإيداع: {'بدون حد أعلى' if plan['max_deposit'] is None else str(plan['max_deposit']) + '$'}\n"
        f"💸 الحد الأدنى للسحب: 20% من رأس المال المودع\n"
        f"📈 نسبة الربح: {plan['profit']}\n"
        f"⏳ موعد السحب: {plan['withdraw_time']}\n\n"
        f"📌 شروط الاشتراك:\n"
        f"- يجب أن يكون مبلغ الإيداع ابتداءً من {plan['min_deposit']}$"
        f"{' بدون حد أعلى' if plan['max_deposit'] is None else ' وحتى ' + str(plan['max_deposit']) + '$'}\n"
        f"- لا يمكن الاشتراك بأكثر من باقة في نفس الحساب\n"
        f"- جميع طلبات الإيداع تخضع لمراجعة الإدارة\n"
        f"- السحب يتم حسب دورة السحب الخاصة بالباقة بعد تحقق الشروط"
    )

def build_plan_action_keyboard(plan_name):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ اشتراك", callback_data=f"subscribe_plan::{plan_name}")
        ],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data="plan_details_back_home")
        ]
    ])

def get_required_upgrade_amount(username, target_plan):
    current_balance = get_user_total_balance(username)
    target_min = PLANS[target_plan]["min_deposit"]
    required = round(target_min - current_balance, 2)
    return required if required > 0 else 0.0

def delete_user_completely(user_id, username):
    # حذف بيانات الحساب الأساسية
    users.pop(username, None)
    user_plans.pop(username, None)
    user_balance.pop(username, None)
    transactions.pop(username, None)
    user_deposits.pop(username, None)
    user_last_profit.pop(username, None)
    user_withdraw_logs.pop(username, None)
    user_deposit_logs.pop(username, None)
    user_statuses.pop(username, None)
    support_blocked_users.pop(username, None)
    user_first_deposit_time.pop(username, None)
    user_last_withdraw_time.pop(username, None)
    user_telegram_ids.pop(username, None)
    user_residence.pop(username, None)
    user_full_name.pop(username, None)
    verified_users.pop(username, None)
    user_referrer.pop(username, None)
    referral_bonus_paid.pop(username, None)
    stopped_profit_users.pop(username, None)
    support_waiting_reply.pop(username, None)
    manual_withdraw_open.pop(username, None)
    user_created_time.pop(username, None)
    user_wallet_address.pop(username, None)
    user_wallet_network.pop(username, None)
    user_identity_photos.pop(username, None)
    user_timezone.pop(username, None)

    # إزالة أي مستخدمين كان هذا الشخص داعيًا لهم
    for invited_username, referrer_username in list(user_referrer.items()):
        if referrer_username == username:
            user_referrer.pop(invited_username, None)

    # حذف تسجيل الدخول الحالي
    logged_in_users.pop(user_id, None)

    # حذف الطلبات المعلقة المرتبطة بـ user_id
    pending_deposit_requests.pop(user_id, None)
    pending_withdraw_requests.pop(user_id, None)
    capital_withdraw_requests.pop(user_id, None)
    pending_verification_requests.pop(user_id, None)

    # حذف أي بيانات إحالة مؤقتة أثناء التسجيل
    REFERRAL_DATA.pop(user_id, None)

    # حذف أي state نشطة
    user_states.pop(user_id, None)

    save_users()
    save_data()

def get_delete_account_warning_text(user_id, username):
    warnings = []

    if user_id in pending_deposit_requests:
        warnings.append("📥 لديك طلب إيداع معلق بانتظار المراجعة.")

    if user_id in pending_withdraw_requests:
        warnings.append("💸 لديك طلب سحب أرباح معلق بانتظار المراجعة.")

    if user_id in capital_withdraw_requests:
        warnings.append("🏦 لديك طلب سحب رأس مال معلق ولم ينتهِ بعد.")

    if not warnings:
        return ""

    return (
        "\n\n⚠️ تنبيه إضافي قبل الحذف:\n"
        + "\n".join(warnings)
        + "\n\nعند حذف الحساب سيتم حذف هذه الطلبات أيضًا نهائيًا من داخل البوت."
    )    

def get_pending_requests_summary_for_admin(user_id):
    lines = []

    deposit_request = pending_deposit_requests.get(user_id)
    if deposit_request:
        lines.append(
            f"📥 طلب إيداع معلق:\n"
            f"• الباقة: {deposit_request.get('plan', 'غير معروف')}\n"
            f"• المبلغ: {deposit_request.get('amount', 0)}$"
        )

    withdraw_request = pending_withdraw_requests.get(user_id)
    if withdraw_request:
        lines.append(
            f"💸 طلب سحب أرباح معلق:\n"
            f"• الباقة: {withdraw_request.get('plan', 'غير معروف')}\n"
            f"• المبلغ: {withdraw_request.get('amount', 0)}$\n"
            f"• وقت الطلب: {withdraw_request.get('time', 'غير متوفر')}"
        )

    capital_request = capital_withdraw_requests.get(user_id)
    if capital_request:
        lines.append(
            f"🏦 طلب سحب رأس مال معلق:\n"
            f"• المبلغ: {round(float(capital_request.get('amount', 0)), 2)}$\n"
            f"• وقت الطلب: {format_timestamp(capital_request.get('request_time'))}\n"
            f"• موعد الاستحقاق: {format_timestamp(capital_request.get('due_time'))}"
        )

    if not lines:
        return "لا توجد عليه طلبات معلقة وقت حذف الحساب."

    return "\n\n".join(lines)

def add_deleted_account_log(entry):
    deleted_accounts_log.append(entry)

    # للحفاظ على حجم السجل معقولًا، نحتفظ بآخر 1000 عملية حذف فقط
    if len(deleted_accounts_log) > 1000:
        del deleted_accounts_log[:-1000]

    save_data()

def build_deleted_accounts_log_text(limit=10):
    if not deleted_accounts_log:
        return "📭 لا يوجد أي سجل لحسابات محذوفة حتى الآن"

    last_items = deleted_accounts_log[-limit:]

    lines = [
        f"🗑 سجل الحسابات المحذوفة (آخر {len(last_items)} عملية)\n",
        "➖➖➖➖➖"
    ]

    for item in reversed(last_items):
        lines.append(
            f"👤 اسم المستخدم: {item.get('username', 'غير متوفر')}\n"
            f"🆔 Telegram ID: {item.get('telegram_id', 'غير متوفر')}\n"
            f"🙍 الاسم الأول: {item.get('telegram_first_name', 'غير متوفر')}\n"
            f"📱 يوزر تيليغرام: {item.get('telegram_username', 'لا يوجد')}\n"
            f"👤 الاسم والكنية: {item.get('full_name', 'غير متوفر')}\n"
            f"🏠 مكان الإقامة: {item.get('residence', 'غير متوفر')}\n"
            f"🪪 التوثيق: {item.get('verification_text', 'غير متوفر')}\n"
            f"📌 الحالة قبل الحذف: {item.get('status_before_delete', 'غير متوفر')}\n"
            f"📦 الباقة قبل الحذف: {item.get('plan_before_delete', 'غير متوفر')}\n"
            f"💰 رأس المال قبل الحذف: {item.get('capital_before_delete', 0)}$\n"
            f"📈 الرصيد قبل الحذف: {item.get('balance_before_delete', 0)}$\n"
            f"💵 الأرباح فقط قبل الحذف: {item.get('profit_only_before_delete', 0)}$\n"
            f"🕒 وقت الحذف: {item.get('deleted_at', 'غير متوفر')}\n"
            f"📋 الطلبات المعلقة وقت الحذف:\n{item.get('pending_requests_summary', 'غير متوفر')}\n"
            f"➖➖➖➖➖"
        )

    return "\n".join(lines)    


# =========================
# لوحات المفاتيح
# =========================

def country_selection_keyboard():
    country_list = list(COUNTRY_TIMEZONES.keys())

    sorted_countries = sorted(
        country_list,
        key=lambda country_label: COUNTRY_TIMEZONES[country_label]["country"]
    )

    keyboard = [[country_label] for country_label in sorted_countries]

    keyboard.append(["🔙 رجوع"])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def country_confirm_keyboard():
    keyboard = [
        ["✅ تأكيد الدولة"],
        ["🔙 رجوع"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_country_choice_text(country_label):
    data = COUNTRY_TIMEZONES.get(country_label)

    if not data:
        return "❌ الدولة المختارة غير صحيحة"

    return (
        f"🌍 الدولة المختارة: {data['country']}\n\n"
        f"هل تريد تأكيد هذه الدولة؟\n\n"
        f"✅ عند التأكيد سيتم اعتماد الدولة كتوقيت حسابك أيضًا."
    )

def main_menu_keyboard():
    keyboard = [
        ["الصفحة الرئيسية"],
        ["باقة VIP","الباقة الذهبية", "الباقة الفضية"],
        ["باقتي","👥 دعوة صديق"],
        ["➕ إيداع جديد","💸 سحب الأرباح"],
        ["🏦 سحب رأس المال وإيقاف الربح", "🪪 توثيق الحساب"],
        ["📜 سجل العمليات", "🔐 تغيير كلمة المرور"],
        ["🗑 حذف حسابي", "📩 مراسلة الدعم"],
        ["🚪 تسجيل خروج"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def auth_keyboard():
    keyboard = [
        ["تسجيل دخول"],
        ["إنشاء حساب جديد"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def admin_keyboard():
    support_employee_button = (
        "⛔ إيقاف موظفي الدعم"
        if support_employees_enabled
        else "👨‍💼 تشغيل موظفي الدعم"
    )

    keyboard = [
        ["📥 طلبات الإيداع", "💸 طلبات السحب"],
        ["🏦 طلبات سحب رأس المال", "🗑 سجل الحسابات المحذوفة"],
        ["👥 عدد المستخدمين", "📊 ملخص مالي"],
        ["📌 حالة الاشتراك", "⛔ إيقاف/تشغيل الاشتراك"],
        ["🛠 حالة البوت", "⏯ إيقاف/تشغيل البوت"],
        ["📢 إرسال رسالة للجميع", "📨 إرسال رسالة حسب الباقة"],
        ["📂 فلترة المستخدمين", "📈 إحصائيات متقدمة"],
        ["🔍 بحث عن مستخدم", "🗑 حذف مستخدم"],
        [support_employee_button],
        ["🔙 رجوع"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_cancel_keyboard():
    keyboard = [
        ["🔙 إلغاء الإرسال"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True) 

def is_admin_media_send_step(user_id):
    if user_id != ADMIN_ID:
        return False

    state = user_states.get(user_id)
    if not isinstance(state, dict):
        return False

    return state.get("step") in [
        "admin_send_broadcast",
        "admin_send_private_message",
        "admin_send_plan_message",
        "admin_reply_support"
    ]  

def create_admin_batch(batch_type, target_label):
    global admin_last_batch_id

    batch_id = str(int(time.time() * 1000))
    admin_sent_batches[batch_id] = {
        "type": batch_type,
        "target": target_label,
        "messages": [],
        "created_at": time.time()
    }
    admin_last_batch_id = batch_id
    save_data()
    return batch_id


def add_message_to_batch(batch_id, chat_id, message_id):
    if batch_id not in admin_sent_batches:
        return

    admin_sent_batches[batch_id]["messages"].append({
        "chat_id": chat_id,
        "message_id": message_id
    })
    save_data()


def build_delete_last_batch_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 حذف آخر إرسال من المستخدمين", callback_data="delete_last_admin_batch")]
    ])

def build_bot_maintenance_keyboard():
    if bot_maintenance_mode:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تشغيل البوت", callback_data="admin_disable_maintenance")]
        ])

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⛔ إيقاف البوت للصيانة", callback_data="admin_enable_maintenance")]
    ])

def get_batch_type_text(batch_type):
    mapping = {
        "support_reply": "رد دعم نصي",
        "support_reply_photo": "رد دعم بصورة",
        "support_reply_document": "رد دعم بملف",

        "private_message": "رسالة خاصة نصية",
        "private_message_photo": "رسالة خاصة بصورة",
        "private_message_document": "رسالة خاصة بملف",

        "plan_message": "رسالة حسب الباقة نصية",
        "plan_message_photo": "رسالة حسب الباقة بصورة",
        "plan_message_document": "رسالة حسب الباقة بملف",

        "broadcast": "إرسال جماعي نصي",
        "broadcast_photo": "إرسال جماعي بصورة",
        "broadcast_document": "إرسال جماعي بملف",
    }
    return mapping.get(batch_type, batch_type)


def get_batch_target_text(target_label):
    if not target_label:
        return "غير معروف"

    if target_label == "all_users":
        return "جميع المستخدمين"

    if target_label.startswith("user:"):
        username = target_label.replace("user:", "", 1)
        return f"المستخدم: {username}"

    if target_label.startswith("plan:"):
        plan_name = target_label.replace("plan:", "", 1)
        return f"مشتركو {plan_name}"

    if target_label.startswith("user_id:"):
        user_id = target_label.replace("user_id:", "", 1)
        return f"المستخدم بالمعرّف: {user_id}"

    return target_label

#==========================
#اوامر تعديل الرصيد يدويا 
#==========================

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❌ استخدم:\n/addbalance username amount")
        return

    username = context.args[0]

    try:
        amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ المبلغ غير صالح")
        return

    if username not in users:
        await update.message.reply_text("❌ المستخدم غير موجود")
        return

    if amount <= 0:
        await update.message.reply_text("❌ يجب أن يكون المبلغ أكبر من صفر")
        return

    user_balance[username] = round(float(user_balance.get(username, 0)) + amount, 2)
    save_data()
    add_transaction(username, "admin_add_balance", amount, "إضافة رصيد يدوي بواسطة الأدمن")

    user_id_found = find_user_id_by_username(username)
    if user_id_found:
        try:
            await context.bot.send_message(
                chat_id=user_id_found,
                text=f"✅ تمت إضافة {amount}$ إلى رصيدك بواسطة الإدارة"
            )
        except:
            pass

    await update.message.reply_text(
        f"✅ تمت إضافة {amount}$ إلى رصيد المستخدم {username}\n"
        f"📈 الرصيد الحالي: {user_balance[username]}$"
    )


async def subtract_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❌ استخدم:\n/subbalance username amount")
        return

    username = context.args[0]

    try:
        amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ المبلغ غير صالح")
        return

    if username not in users:
        await update.message.reply_text("❌ المستخدم غير موجود")
        return

    if amount <= 0:
        await update.message.reply_text("❌ يجب أن يكون المبلغ أكبر من صفر")
        return

    current_balance = float(user_balance.get(username, 0))
    new_balance = round(current_balance - amount, 2)

    if new_balance < 0:
        new_balance = 0

    deducted = round(current_balance - new_balance, 2)
    user_balance[username] = new_balance
    save_data()
    add_transaction(username, "admin_subtract_balance", deducted, "خصم رصيد يدوي بواسطة الأدمن")

    user_id_found = find_user_id_by_username(username)
    if user_id_found:
        try:
            await context.bot.send_message(
                chat_id=user_id_found,
                text=f"⚠️ تم خصم {deducted}$ من رصيدك بواسطة الإدارة"
            )
        except:
            pass

    await update.message.reply_text(
        f"✅ تمت عملية الخصم من المستخدم {username}\n"
        f"💸 المبلغ المخصوم: {deducted}$\n"
        f"📈 الرصيد الحالي: {user_balance[username]}$"
    )

#===========================
#امر تغيير الباقة من قبل الادمن 
#============================
async def set_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ استخدم:\n"
            "/setplan username silver\n"
            "/setplan username gold\n"
            "/setplan username vip"
        )
        return

    username = context.args[0]
    plan_code = context.args[1].lower()

    if username not in users:
        await update.message.reply_text("❌ المستخدم غير موجود")
        return

    plan_map = {
        "silver": "الباقة الفضية",
        "gold": "الباقة الذهبية",
        "vip": "باقة VIP"
    }

    if plan_code not in plan_map:
        await update.message.reply_text("❌ الباقة غير صحيحة. استخدم: silver أو gold أو vip")
        return

    new_plan = plan_map[plan_code]
    old_plan = user_plans.get(username, "NONE")

    user_plans[username] = new_plan

    # إعادة ضبط دورة السحب من وقت التعديل
    now = time.time()
    if username not in user_first_deposit_time:
        user_first_deposit_time[username] = now
    user_last_withdraw_time[username] = now

    save_data()
    add_transaction(username, "admin_set_plan", 0, f"تغيير الباقة من {old_plan} إلى {new_plan}")

    user_id_found = find_user_id_by_username(username)
    if user_id_found:
        try:
            await context.bot.send_message(
                chat_id=user_id_found,
                text=(
                    f"✅ تم تعديل باقتك بواسطة الإدارة\n"
                    f"📦 الباقة الجديدة: {new_plan}\n"
                    f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}"
                )
            )
        except:
            pass

    await update.message.reply_text(
        f"✅ تم تغيير باقة المستخدم {username}\n"
        f"📦 القديمة: {old_plan}\n"
        f"📦 الجديدة: {new_plan}\n"
        f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}"
    )

#=========================
#اعادة ضبط موعد السحب 
#=========================
async def reset_withdraw_cycle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if not context.args:
        await update.message.reply_text("❌ استخدم:\n/resetwithdraw username")
        return

    username = context.args[0]

    if username not in users:
        await update.message.reply_text("❌ المستخدم غير موجود")
        return

    now = time.time()

    if username not in user_first_deposit_time:
        user_first_deposit_time[username] = now

    user_last_withdraw_time[username] = now
    save_data()
    add_transaction(username, "admin_reset_withdraw_cycle", 0, "إعادة ضبط دورة السحب بواسطة الأدمن")

    user_id_found = find_user_id_by_username(username)
    if user_id_found:
        try:
            await context.bot.send_message(
                chat_id=user_id_found,
                text=(
                    f"♻️ تم إعادة ضبط دورة السحب الخاصة بك بواسطة الإدارة\n"
                    f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}"
                )
            )
        except:
            pass

    await update.message.reply_text(
        f"✅ تم إعادة ضبط موعد السحب للمستخدم {username}\n"
        f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}"
    )


# =========================
# /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = update.message.chat_id

    # =========================
    # استقبال رابط الإحالة من /start
    # مثال الرابط:
    # https://t.me/Moneyfactory1bot?start=ref_123456789
    # =========================
    if context.args:
        payload = context.args[0]
        referrer_username = get_referrer_from_start_payload(payload, user_id)

        existing_username = find_username_by_telegram_id(user_id)

        if referrer_username and not existing_username:
            REFERRAL_DATA[user_id] = referrer_username

    if user_id in logged_in_users:
       username = logged_in_users[user_id]
       user_telegram_ids[username] = user_id
       save_data()

    if user_id not in chat_ids:
        chat_ids.append(user_id)
        save_chat_ids()

        username_text = f"@{user.username}" if user.username else "لا يوجد"
        referral_text = REFERRAL_DATA.get(user_id, "لا يوجد")

        msg = (
            f"🚀 مستخدم جديد دخل البوت\n\n"
            f"👤 الاسم: {user.first_name}\n"
            f"🔗 اليوزر: {username_text}\n"
            f"🆔 ID: {user.id}\n"
            f"🌐 اللغة: {user.language_code}\n"
            f"👥 دخل عبر دعوة: {referral_text}\n"
            f"📊 عدد المستخدمين: {len(chat_ids)}"
        )

        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=msg)
        except Exception as e:
            print(f"خطأ في إرسال رسالة للأدمن: {e}")

    await update.message.reply_text("اختر خيار:", reply_markup=auth_keyboard())


# =========================
# /k
# =========================
async def k(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("اختر خيار:", reply_markup=auth_keyboard())


# =========================
# /ana
# =========================
async def ana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = logged_in_users.get(user_id)

    if not username:
        await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
        return

    if is_user_banned(username):
        await update.message.reply_text("⛔ هذا الحساب محظور، يرجى التواصل مع الإدارة")
        return

    await update.message.reply_text(
        "مرحبا بك في مصنع المال 💰\nاختر إحدى الخيارات:",
        reply_markup=main_menu_keyboard()
    )


# =========================
# /admin
# =========================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية الوصول إلى لوحة الأدمن")
        return

    await update.message.reply_text(
         f"🛠 لوحة تحكم الأدمن\n"
         f"📌 حالة الاشتراك العامة: {get_subscriptions_status_text()}\n"
         f"🛠 حالة البوت: {get_bot_maintenance_status_text()}\n"
         f"اختر أحد الخيارات:",
        reply_markup=admin_keyboard()
         )


# =========================
# /send
# =========================
async def send_to_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    message = " ".join(context.args).strip()

    if not message:
        await update.message.reply_text("❗ اكتب الرسالة بعد الأمر")
        return

    success = 0

    for uid in chat_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            success += 1
            await asyncio.sleep(0.05)
        except:
            pass

    await update.message.reply_text(f"✅ تم إرسال الرسالة إلى {success} مستخدم")

async def notify_all_users(context: ContextTypes.DEFAULT_TYPE, message_text: str):
    success = 0
    failed = 0

    for uid in list(chat_ids):
        try:
            await context.bot.send_message(chat_id=uid, text=message_text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"تعذر إرسال إشعار الصيانة إلى {uid}: {e}")
            failed += 1

    return success, failed    


# =========================
# /approve اليدوي
# =========================
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if len(context.args) == 0:
        await update.message.reply_text("❌ استخدم:\n/approve user_id")
        return

    try:
        user_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ ID غير صالح")
        return

    request = pending_deposit_requests.get(user_id)

    if not request:
        await update.message.reply_text("❌ لا يوجد طلب إيداع لهذا المستخدم")
        return

    username = request["username"]
    ensure_user_defaults(username)

    if user_plans.get(username) not in [None, "NONE"]:
        await update.message.reply_text("❌ هذا المستخدم لديه باقة مفعلة بالفعل")
        return

    if is_user_frozen(username) or is_user_banned(username):
        await update.message.reply_text("❌ لا يمكن تفعيل إيداع لهذا المستخدم لأن حسابه غير نشط")
        return

    deposit_amount = round(float(request["amount"]), 2)

    user_balance[username] = deposit_amount
    user_deposits[username] = deposit_amount
    user_last_profit[username] = time.time()
    user_plans[username] = request["plan"]

    if username not in user_first_deposit_time:
        user_first_deposit_time[username] = time.time()

    user_deposit_logs.setdefault(username, []).append({
        "amount": deposit_amount,
        "time": now_str()
    })

    add_transaction(username, "deposit_approved", deposit_amount, f"تفعيل {request['plan']}")

    # هدية الإحالة لأول إيداع فقط
    referrer_username = user_referrer.get(username)
    bonus_already_paid = referral_bonus_paid.get(username, False)

    if referrer_username and not bonus_already_paid:
        bonus_amount = round(deposit_amount * 0.20, 2)

        user_balance[referrer_username] = round(
            float(user_balance.get(referrer_username, 0)) + bonus_amount, 2
        )

        add_transaction(
            referrer_username,
            "referral_bonus",
            bonus_amount,
            f"هدية أول إيداع من المستخدم {username}"
        )

        referral_bonus_paid[username] = True

        referrer_user_id = get_saved_telegram_id(referrer_username)
        if referrer_user_id:
            try:
                await context.bot.send_message(
                    chat_id=referrer_user_id,
                    text=(
                        f"🎉 مبروك! حصلت على هدية إحالة\n\n"
                        f"👤 المستخدم المدعو: {username}\n"
                        f"💰 قيمة أول إيداع: {deposit_amount}$\n"
                        f"🎁 قيمة الهدية: {bonus_amount}$"
                    )
                )
            except:
                pass

    pending_deposit_requests.pop(user_id, None)
    save_data()

    home_keyboard = ReplyKeyboardMarkup(
         [["الصفحة الرئيسية"]],
         resize_keyboard=True
            )

    await context.bot.send_message(
    chat_id=user_id,
    text="✅ تم تفعيل باقتك بنجاح 🎉\nاضغط على زر الصفحة الرئيسية في الأسفل",
    reply_markup=home_keyboard
          )

    await update.message.reply_text("✅ تمت الموافقة على الإيداع")


# =========================
# /userinfo للأدمن
# =========================
async def userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if not context.args:
        await update.message.reply_text("❌ استخدم:\n/userinfo اسم_المستخدم")
        return

    username = context.args[0]

    if username not in users:
        await update.message.reply_text("❌ هذا المستخدم غير موجود")
        return

    await update.message.reply_text(
        build_admin_user_text(username),
        reply_markup=build_admin_user_keyboard(username)
    )


# =========================
# أوامر الأدمن النصية
# =========================
async def resetpass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if len(context.args) < 2:
        await update.message.reply_text("❌ استخدم:\n/resetpass username newpassword")
        return

    username = context.args[0]
    new_password = context.args[1]

    if username not in users:
        await update.message.reply_text("❌ المستخدم غير موجود")
        return

    old_password = users[username]
    users[username] = new_password
    save_users()

    add_transaction(username, "admin_reset_password", 0, f"تغيير كلمة المرور بواسطة الأدمن من {old_password} إلى {new_password}")

    user_id_found = find_user_id_by_username(username)
    if user_id_found:
        try:
            await context.bot.send_message(
                chat_id=user_id_found,
                text=(
                    "🔐 تم تغيير كلمة المرور الخاصة بحسابك بواسطة الإدارة\n\n"
                    f"👤 اسم المستخدم: {username}\n"
                    f"🔑 كلمة المرور الجديدة: {new_password}"
                )
            )
        except:
            pass

    await update.message.reply_text(
        f"✅ تم تغيير كلمة مرور المستخدم {username}\n"
        f"🔑 القديمة: {old_password}\n"
        f"🔑 الجديدة: {new_password}"
    )


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if not context.args:
        await update.message.reply_text("❌ استخدم:\n/ban username")
        return

    username = context.args[0]
    result = await apply_admin_status_action(context, username, "ban")
    await update.message.reply_text(result)


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if not context.args:
        await update.message.reply_text("❌ استخدم:\n/unban username")
        return

    username = context.args[0]
    result = await apply_admin_status_action(context, username, "unban")
    await update.message.reply_text(result)


async def freeze_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if not context.args:
        await update.message.reply_text("❌ استخدم:\n/freeze username")
        return

    username = context.args[0]
    result = await apply_admin_status_action(context, username, "freeze")
    await update.message.reply_text(result)


async def unfreeze_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if not context.args:
        await update.message.reply_text("❌ استخدم:\n/unfreeze username")
        return

    username = context.args[0]
    result = await apply_admin_status_action(context, username, "unfreeze")
    await update.message.reply_text(result)


# =========================
# منطق إجراءات حالة المستخدم
# =========================
async def apply_admin_status_action(context, username, action):
    if username not in users:
        return "❌ المستخدم غير موجود"

    ensure_user_defaults(username)
    user_id_found = find_user_id_by_username(username)

    if action == "ban":
        if get_user_status(username) == "banned":
            return f"ℹ️ المستخدم {username} محظور بالفعل"
        user_statuses[username] = "banned"
        save_data()
        add_transaction(username, "ban", 0, "تم حظر الحساب بواسطة الأدمن")
        if user_id_found:
            try:
                await context.bot.send_message(chat_id=user_id_found, text="⛔ تم حظر حسابك، يرجى التواصل مع الإدارة")
            except:
                pass
        return f"✅ تم حظر المستخدم {username}"

    if action == "unban":
        if get_user_status(username) != "banned":
            return f"ℹ️ المستخدم {username} ليس محظورًا حاليًا"
        user_statuses[username] = "active"
        save_data()
        add_transaction(username, "unban", 0, "تم فك الحظر بواسطة الأدمن")
        if user_id_found:
            try:
                await context.bot.send_message(chat_id=user_id_found, text="✅ تم فك الحظر عن حسابك وأصبح نشطًا من جديد")
            except:
                pass
        return f"✅ تم فك الحظر عن المستخدم {username}"

    if action == "freeze":
        if get_user_status(username) == "frozen":
            return f"ℹ️ المستخدم {username} مجمد بالفعل"
        if get_user_status(username) == "banned":
            return f"❌ لا يمكن تجميد {username} لأنه محظور حاليًا"
        user_statuses[username] = "frozen"
        save_data()
        add_transaction(username, "freeze", 0, "تم تجميد الحساب ماليًا بواسطة الأدمن")
        if user_id_found:
            try:
                await context.bot.send_message(chat_id=user_id_found, text="⚠️ تم تجميد العمليات المالية في حسابك مؤقتًا")
            except:
                pass
        return f"✅ تم تجميد المستخدم {username} ماليًا"

    if action == "unfreeze":
        if get_user_status(username) != "frozen":
            return f"ℹ️ المستخدم {username} ليس مجمدًا حاليًا"
        user_statuses[username] = "active"
        save_data()
        add_transaction(username, "unfreeze", 0, "تم فك التجميد بواسطة الأدمن")
        if user_id_found:
            try:
                await context.bot.send_message(chat_id=user_id_found, text="✅ تم فك التجميد عن حسابك وأصبحت العمليات المالية متاحة")
            except:
                pass
        return f"✅ تم فك تجميد المستخدم {username}"

    return "❌ إجراء غير معروف"

# =========================
# حماية خطوات إدخال البيانات من أزرار القائمة
# =========================
def get_main_reply_button_texts():
    buttons = set()

    for row in main_menu_keyboard().keyboard:
        for button in row:
            buttons.add(button.text if hasattr(button, "text") else str(button))

    for row in auth_keyboard().keyboard:
        for button in row:
            buttons.add(button.text if hasattr(button, "text") else str(button))

    for row in admin_keyboard().keyboard:
        for button in row:
            buttons.add(button.text if hasattr(button, "text") else str(button))

    buttons.update(PLANS.keys())

    buttons.update({
        "✅ موافق",
        "❌ إلغاء",
        "دعوة من صديق",
        "بدون دعوة",
        "🔙 رجوع",
        "🔙 إلغاء الإرسال"
    })

    return buttons


def is_user_in_data_entry_state(user_id):
    state = user_states.get(user_id)

    if not state:
        return False

    # حالات نصية أثناء التسجيل
    if state in [
        "accept_terms",
        "ask_referral",
        "referral_username",
        "register_username",
        "register_residence",
        "login_username"
    ]:
        return True

    if not isinstance(state, dict):
        return False

    step = state.get("step")

    data_entry_steps = [
        # تسجيل / دخول
        "register_full_name",
        "register_username",
        "register_password",
        "login_password",

        # التوثيق
        "verify_full_name",
        "verify_residence",
        "verify_id_front",
        "verify_id_back",

        # تغيير كلمة المرور
        "change_password_old",
        "change_password_new",
        "change_password_confirm",

        # الدعم
        "support_message",

        # السحب
        "withdraw_enter_amount",
        "withdraw_enter_wallet",
        "withdraw_enter_network",

        # إيداع / تغيير باقة
        "enter_amount",
        "topup_enter_amount",
        "plan_change_enter_amount",
        "send_proof",
        "send_topup_proof",
        "send_plan_change_proof",

        # الأدمن
        "admin_search_user",
        "admin_delete_user_search",
        "admin_reply_support",
        "admin_send_broadcast",
        "admin_send_private_message",
        "admin_send_plan_message",
        "admin_add_balance_input",
        "admin_sub_balance_input",
        "admin_add_wallet_address",
        "admin_add_wallet_network",
    ]

    return step in data_entry_steps


def get_data_entry_warning_text(user_id):
    state = user_states.get(user_id)

    if isinstance(state, dict):
        step = state.get("step")
    else:
        step = state

    if step in ["verify_full_name"]:
        return (
            "⚠️ أنت الآن داخل عملية توثيق الحساب.\n\n"
            "يرجى إدخال الاسم والكنية كما هو موضح في البطاقة الشخصية، "
            "أو اضغط 🔙 رجوع لإلغاء الخطوة والعودة."
        )

    if step in ["verify_residence"]:
        return (
            "⚠️ أنت الآن داخل عملية توثيق الحساب.\n\n"
            "يرجى إدخال مكان الإقامة (الدولة)، "
            "أو اضغط 🔙 رجوع لإلغاء الخطوة والعودة."
        )

    if step in ["verify_id_front"]:
        return (
            "⚠️ أنت الآن داخل عملية توثيق الحساب.\n\n"
            "يرجى إرسال صورة الوجه الأمامي للهوية الشخصية، "
            "أو اضغط 🔙 رجوع لإلغاء الخطوة والعودة."
        )

    if step in ["verify_id_back"]:
        return (
            "⚠️ أنت الآن داخل عملية توثيق الحساب.\n\n"
            "يرجى إرسال صورة الوجه الخلفي للهوية الشخصية، "
            "أو اضغط 🔙 رجوع لإلغاء الخطوة والعودة."
        )

    if step in ["withdraw_enter_amount", "withdraw_enter_wallet", "withdraw_enter_network"]:
        return (
            "⚠️ لديك عملية سحب قيد الإدخال.\n\n"
            "يرجى إكمال البيانات المطلوبة أو اضغط 🔙 رجوع للعودة."
        )

    if step in ["change_password_old", "change_password_new", "change_password_confirm"]:
        return (
            "⚠️ أنت الآن داخل عملية تغيير كلمة المرور.\n\n"
            "يرجى إكمال الخطوة المطلوبة أو اضغط 🔙 رجوع للعودة."
        )

    if step == "support_message":
        return (
            "⚠️ أنت الآن داخل مراسلة الدعم.\n\n"
            "اكتب رسالتك أو أرسل صورة، أو اضغط 🔙 رجوع للعودة."
        )

    if step in ["enter_amount", "topup_enter_amount", "plan_change_enter_amount"]:
        return (
            "⚠️ لديك عملية إيداع أو اشتراك قيد الإدخال.\n\n"
            "يرجى إدخال المبلغ المطلوب أو اضغط 🔙 رجوع للعودة."
        )

    if step in ["send_proof", "send_topup_proof", "send_plan_change_proof"]:
        return (
            "⚠️ بانتظار إثبات الدفع.\n\n"
            "يرجى إرسال صورة إثبات الدفع أو اضغط 🔙 رجوع للعودة."
        )

    if step in [
        "admin_search_user",
        "admin_delete_user_search",
        "admin_reply_support",
        "admin_send_broadcast",
        "admin_send_private_message",
        "admin_send_plan_message",
        "admin_add_balance_input",
        "admin_sub_balance_input",
        "admin_add_wallet_address",
        "admin_add_wallet_network",
    ]:
        return (
            "⚠️ أنت الآن داخل عملية إدارية قيد الإدخال.\n\n"
            "يرجى إكمال المطلوب أو اضغط 🔙 إلغاء الإرسال للعودة."
        )

    return (
        "⚠️ لديك عملية قيد الإدخال حاليًا.\n\n"
        "يرجى إكمال الخطوة المطلوبة أو اضغط 🔙 رجوع للعودة."
    )


async def block_menu_buttons_during_data_entry(update: Update, context, user_id, text):
    if not is_user_in_data_entry_state(user_id):
        return False

    state = user_states.get(user_id)

    if isinstance(state, dict):
        step = state.get("step")
    else:
        step = state

    # =========================
    # أزرار مسموحة حسب الحالة الحالية
    # =========================
    allowed_by_state = {
        "accept_terms": ["✅ موافق", "❌ إلغاء"],
        "ask_referral": ["دعوة من صديق", "بدون دعوة", "🔙 رجوع"],
    }

    if step in allowed_by_state and text in allowed_by_state[step]:
        return False

    # السماح بزر الرجوع والإلغاء العام
    if text in ["🔙 رجوع", "🔙 إلغاء الإرسال"]:
        return False

    # نحجب فقط أزرار القوائم، أما النص العادي نتركه للحالة الحالية
    if text not in get_main_reply_button_texts():
        return False

    # حذف رسالة التحذير السابقة إن وجدت
    last_msg_id = context.user_data.get("last_warning_msg_id")

    if last_msg_id:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
        except Exception as e:
            print(f"تعذر حذف رسالة التحذير السابقة: {e}")

    sent_msg = await update.message.reply_text(
        get_data_entry_warning_text(user_id),
        reply_markup=build_data_entry_back_keyboard()
    )

    context.user_data["last_warning_msg_id"] = sent_msg.message_id

    return True

async def go_back_from_data_entry_state(user_id, context):
    username = logged_in_users.get(user_id)
    state = user_states.get(user_id)

    if not state:
        await context.bot.send_message(
            chat_id=user_id,
            text="🏠 تم الرجوع إلى الصفحة الرئيسية",
            reply_markup=main_menu_keyboard() if username else auth_keyboard()
        )
        return

    step = state.get("step") if isinstance(state, dict) else state

    # =========================
    # رجوع خطوات توثيق الحساب
    # =========================
    if step == "verify_full_name":
        user_states.pop(user_id, None)
        await context.bot.send_message(
            chat_id=user_id,
            text="🏠 تم الرجوع إلى الصفحة الرئيسية",
            reply_markup=main_menu_keyboard()
        )
        return

    if step == "verify_residence":
        user_states[user_id] = {
            "step": "verify_full_name"
        }
        await context.bot.send_message(
            chat_id=user_id,
            text="أدخل الاسم والكنية كما هو موضح في البطاقة الشخصية:",
            reply_markup=main_menu_keyboard()
        )
        return
    
    if step == "confirm_residence":
        old_full_name = state.get("full_name", "")

        user_states[user_id] = {
            "step": "verify_residence",
            "full_name": old_full_name
        }

        await context.bot.send_message(
            chat_id=user_id,
            text="🌍 اختر دولة الإقامة من القائمة:",
            reply_markup=country_selection_keyboard()
        )
        return

    if step == "verify_id_front":
       old_full_name = state.get("full_name", "")

       user_states[user_id] = {
        "step": "verify_residence",
        "full_name": old_full_name
            }

       await context.bot.send_message(
        chat_id=user_id,
        text="🌍 اختر دولة الإقامة من القائمة:",
        reply_markup=country_selection_keyboard()
         )
       return

    if step == "verify_id_back":
        old_full_name = state.get("full_name", "")
        old_residence = state.get("residence", "")
        old_timezone = state.get("timezone", "Europe/Vienna")

        user_states[user_id] = {
            "step": "verify_id_front",
            "full_name": old_full_name,
            "residence": old_residence,
            "timezone": old_timezone
             }

        await context.bot.send_message(
            chat_id=user_id,
            text="📷 قم الآن برفع صورة واضحة للوجه الأمامي للهوية الشخصية:",
            reply_markup=main_menu_keyboard()
        )
        return

    # =========================
    # رجوع عام لباقي حالات الإدخال
    # =========================
    user_states.pop(user_id, None)

    await context.bot.send_message(
        chat_id=user_id,
        text="🏠 تم الرجوع إلى الصفحة الرئيسية",
        reply_markup=main_menu_keyboard() if username else auth_keyboard()
    )

# =========================
# معالجة الرسائل
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global support_employees_enabled

    user = update.message.from_user
    user_id = user.id
    text = update.message.text.strip() if update.message.text else ""

    if user_id == ADMIN_ID and text in ["👨‍💼 تشغيل موظفي الدعم", "⛔ إيقاف موظفي الدعم"]:
        support_employees_enabled = not support_employees_enabled
        save_data()

        await update.message.reply_text(
            f"✅ تم تحديث حالة موظفي الدعم\n\n"
            f"👨‍💼 الحالة الحالية: {get_support_employees_status_text()}",
            reply_markup=admin_keyboard()
        )
        return

    if bot_maintenance_mode and user_id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ البوت متوقف مؤقتًا للصيانة\n\n"
            "تقوم الإدارة حالياً بإجراء تحديثات على النظام.\n"
            "يرجى المحاولة لاحقًا."
        )
        return

    tg_username = f"@{user.username}" if user.username else "لا يوجد يوزر نيم ❌"

    if await block_menu_buttons_during_data_entry(update, context, user_id, text):
      return
    
    # =========================
    # إلغاء عمليات الإرسال/الرد للأدمن
    # =========================
    if is_support_operator(user_id) and text == "🔙 إلغاء الإرسال":
        current_state = user_states.get(user_id)

        cancellable_steps = [
            "admin_send_broadcast",
            "admin_send_private_message",
            "admin_send_plan_message",
            "admin_reply_support"
        ]

        if isinstance(current_state, dict) and current_state.get("step") in cancellable_steps:
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "✅ تم إلغاء عملية الإرسال",
                reply_markup=admin_keyboard() if user_id == ADMIN_ID else main_menu_keyboard()
            )
            return
        # =========================
    # رجوع داخل خطوات التسجيل
    # =========================
    if text == "🔙 رجوع":
        state = user_states.get(user_id)

        if isinstance(state, dict) and state.get("step") in [
              "verify_full_name",
              "verify_residence",
              "confirm_residence",
              "verify_id_front",
              "verify_id_back"
               ]:
            await go_back_from_data_entry_state(user_id, context)
            return

        # الرجوع من شاشة اختيار طريقة الوصول
        if state == "ask_referral":
            user_states.pop(user_id, None)
            REFERRAL_DATA.pop(user_id, None)
            await update.message.reply_text(
                "تم الرجوع.",
                reply_markup=auth_keyboard()
            )
            return
        
        elif state == "accept_terms":
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "تم الرجوع.",
                reply_markup=auth_keyboard()
            )
            return

        # الرجوع من إدخال اسم المستخدم الداعي
        elif state == "referral_username":
            user_states[user_id] = "ask_referral"
            keyboard = [
                ["دعوة من صديق"],
                ["بدون دعوة"],
                ["🔙 رجوع"]
            ]
            await update.message.reply_text(
                "كيف وصلت إلينا؟",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return

        # الرجوع من إدخال مكان الإقامة
        elif state == "register_residence":
            if user_id in REFERRAL_DATA:
                if REFERRAL_DATA[user_id] == "بدون دعوة":
                    user_states[user_id] = "ask_referral"
                    keyboard = [
                        ["دعوة من صديق"],
                        ["بدون دعوة"],
                        ["🔙 رجوع"]
                    ]
                    await update.message.reply_text(
                        "كيف وصلت إلينا؟",
                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                    )
                    return
                else:
                    user_states[user_id] = "referral_username"
                    await update.message.reply_text(
                        "أدخل اسم المستخدم الشخص الذي دعاك:",
                        reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
                    )
                    return

        # الرجوع من إدخال الاسم الكامل
        elif isinstance(state, dict) and state.get("step") == "register_full_name":
            user_states[user_id] = "register_residence"
            await update.message.reply_text(
                "أدخل مكان الإقامة:",
                reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
            )
            return

        # الرجوع من إدخال اسم المستخدم
        elif state == "register_username":
             user_states[user_id] = "ask_referral"
             keyboard = [
                ["دعوة من صديق"],
                 ["بدون دعوة"],
                ["🔙 رجوع"]
                     ]
             await update.message.reply_text(
                   "كيف وصلت إلينا؟",
                   reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                 )
             return

        # الرجوع من إدخال كلمة المرور
        elif isinstance(state, dict) and state.get("step") == "register_password":
              user_states[user_id] = "register_username"

              await update.message.reply_text(
                      "أدخل اسم المستخدم:",
                       reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
                        )
              return
        
                # =========================
        # الرجوع داخل خطوات سحب الأرباح
        # =========================

        # الرجوع من خطوة إدخال مبلغ السحب
        elif isinstance(state, dict) and state.get("step") == "withdraw_enter_amount":
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "تم الرجوع.",
                reply_markup=main_menu_keyboard()
            )
            return

        # الرجوع من خطوة إدخال عنوان المحفظة
        elif isinstance(state, dict) and state.get("step") == "withdraw_enter_wallet":
            max_profit = state.get("max_profit")
            plan_name = state.get("plan_name")

            username = logged_in_users.get(user_id)
            if not username:
                user_states.pop(user_id, None)
                await update.message.reply_text(
                    "يجب تسجيل الدخول أولاً ❌",
                    reply_markup=auth_keyboard()
                )
                return

            if max_profit is None:
                update_profit(username)
                max_profit = get_user_profit_only(username)

            user_states[user_id] = {
                "step": "withdraw_enter_amount",
                "max_profit": max_profit,
                "plan_name": plan_name
            }

            await update.message.reply_text(
                f"💸 الأرباح المتاحة للسحب: {max_profit}$\n"
                f"💰 أدخل المبلغ الذي تريد سحبه:",
                reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
            )
            return

        # الرجوع من خطوة إدخال الشبكة
        elif isinstance(state, dict) and state.get("step") == "withdraw_enter_network":
            user_states[user_id] = {
                "step": "withdraw_enter_wallet",
                "amount": state["amount"],
                "plan_name": state["plan_name"],
                "max_profit": state.get("max_profit")
            }

            await update.message.reply_text(
                "💼 أدخل عنوان المحفظة التي تريد السحب إليها:",
                reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
            )
            return
        
        # الرجوع من خطوات توثيق الحساب
        elif isinstance(state, dict) and state.get("step") in [
            "verify_full_name",
            "verify_residence",
            "verify_id_front",
            "verify_id_back"
        ]:
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "تم الرجوع.",
                reply_markup=main_menu_keyboard()
            )
            return

        # إذا لم يكن داخل التسجيل، لا نفعل شيئًا هنا    

    if text == "إنشاء حساب جديد":
       existing_username = find_username_by_telegram_id(user_id)

       if existing_username:
          full_name = user_full_name.get(existing_username, "غير متوفر")

          await update.message.reply_text(
             f"❌ لا يمكنك إنشاء أكثر من حساب \n\n"
             f"❌ حسابك الحالي هو : \n\n"
             f"👤 الاسم والكنية: {full_name}\n\n"
             f"🧾 اسم المستخدم: {existing_username}\n\n"
             f"يمكنك تسجيل الدخول من خلال زر تسجيل دخول"
          )
          return

       user_states[user_id] = "accept_terms"

       keyboard = [
           ["✅ موافق"],
           ["❌ إلغاء"]
       ]
       reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

       await update.message.reply_text(
           TERMS_TEXT,
           reply_markup=reply_markup
        )
       return
    
    elif user_states.get(user_id) == "accept_terms":
        if text == "✅ موافق":
            auto_referrer = REFERRAL_DATA.get(user_id)

            if auto_referrer and auto_referrer in users and auto_referrer != find_username_by_telegram_id(user_id):
                user_states[user_id] = "register_username"

                await update.message.reply_text(
                    f"✅ تم اعتماد دعوتك تلقائيًا عن طريق المستخدم:\n"
                    f"{auto_referrer}\n\n"
                    f"أدخل اسم المستخدم:",
                    reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
                )
                return

            user_states[user_id] = "ask_referral"

            keyboard = [
                ["دعوة من صديق"],
                ["بدون دعوة"],
                ["🔙 رجوع"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                "كيف وصلت إلينا؟",
                reply_markup=reply_markup
            )
            return

        elif text == "❌ إلغاء":
            user_states.pop(user_id, None)

            await update.message.reply_text(
                "تم إلغاء عملية إنشاء الحساب",
                reply_markup=auth_keyboard()
            )
            return

        else:
            await update.message.reply_text("يرجى اختيار ✅ موافق أو ❌ إلغاء فقط")
            return

    elif user_states.get(user_id) == "ask_referral":
        if text == "دعوة من صديق":
          user_states[user_id] = "referral_username"
          await update.message.reply_text(
              "أدخل اسم المستخدم الشخص الذي دعاك:",
              reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
          )
          return

        elif text == "بدون دعوة":
          REFERRAL_DATA[user_id] = "بدون دعوة"
          user_states[user_id] = "register_username"
          await update.message.reply_text("أدخل اسم المستخدم:",
              reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
          )
          return

        else:
          await update.message.reply_text("اختر أحد الخيارين فقط")
          return

    elif user_states.get(user_id) == "referral_username":
       ref_username = text.strip()

       if ref_username not in users:
        await update.message.reply_text("❌ اسم المستخدم الذي أدخلته غير موجود داخل النظام")
        return

       existing_username = find_username_by_telegram_id(user_id)
       if existing_username and ref_username == existing_username:
        await update.message.reply_text("❌ لا يمكنك إدخال اسمك أنت كداعٍ")
        return

       REFERRAL_DATA[user_id] = ref_username
       user_states[user_id] = "register_username"
       await update.message.reply_text("أدخل اسم المستخدم:",
           reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
            )
       return
    
    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "register_full_name":
      full_name = text.strip()

      if len(full_name) < 5:
          await update.message.reply_text("❌ يرجى إدخال الاسم والكنية بشكل صحيح كما في الهوية")
          return

      user_states[user_id] = {
          "step": "register_username",
          "residence": user_states[user_id]["residence"],
          "full_name": full_name
      }
      await update.message.reply_text(
          "أدخل اسم المستخدم:",
          reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
      )
      return

    elif user_states.get(user_id) == "register_username":
       username = text.strip()

       if username in users:
        await update.message.reply_text("اسم المستخدم موجود بالفعل ❌")
        return

       for req in pending_verification_requests.values():
        if req.get("username") == username:
            await update.message.reply_text("اسم المستخدم محجوز ضمن طلب توثيق قيد المراجعة ❌")
            return

       user_states[user_id] = {
        "step": "register_password",
        "username": username
       }

       await update.message.reply_text(
        "أدخل كلمة المرور:",
        reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
       )
       return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "register_password":
       username = user_states[user_id]["username"]
       password = text.strip()

       if username in users:
           await update.message.reply_text("اسم المستخدم موجود مسبقًا ❌")
           return

       if len(password) < 3:
           await update.message.reply_text("❌ كلمة المرور قصيرة جدًا، اجعلها 3 أحرف أو أكثر")
           return

       users[username] = password
       user_telegram_ids[username] = user_id
       user_plans[username] = "NONE"
       user_balance[username] = 0
       transactions[username] = []
       user_withdraw_logs[username] = []
       user_deposit_logs[username] = []
       user_deposits[username] = 0
       user_last_profit[username] = time.time()
       user_statuses[username] = "active"
       verified_users[username] = False
       user_created_time[username] = time.time()

       referral_value = REFERRAL_DATA.get(user_id, "غير محدد")
       if referral_value not in ["غير محدد", "بدون دعوة", "", None]:
           referrer_username = referral_value.strip()
           if referrer_username in users and referrer_username != username:
               user_referrer[username] = referrer_username

       referral_bonus_paid[username] = False

       save_users()
       save_data()

       try:
            tg_first_name = user.first_name if user.first_name else "غير متوفر"
            tg_username_text = f"@{user.username}" if user.username else "لا يوجد"
            referral_text = REFERRAL_DATA.get(user_id, "غير محدد")

            await context.bot.send_message(
                 chat_id=ADMIN_ID,
                 text=(
                    f"🆕 تم إنشاء حساب جديد\n\n"
                    f"👤 الاسم في تيليغرام: {tg_first_name}\n"
                    f"📱 يوزر تيليغرام: {tg_username_text}\n"
                    f"🆔 Telegram ID: {user_id}\n\n"
                    f"🧾 اسم المستخدم داخل البوت: {username}\n"
                    f"🔑 كلمة المرور: {password}\n"
                    f"📌 طريقة الوصول: {referral_text}\n"
                    f"🪪 حالة التوثيق: غير موثق ❌\n"
                    f"📦 الباقة: NONE\n"
                    f"💰 الرصيد: 0$\n"
                    f"🕒 وقت إنشاء الحساب: {now_str()}"
                     )
                )
       except Exception as e:
            print(f"خطأ في إرسال إشعار إنشاء الحساب للأدمن: {e}")

       user_states.pop(user_id, None)

       await update.message.reply_text(
           "✅ تم إنشاء الحساب بنجاح\n\n"
           f"🧾 اسم المستخدم: {username}\n"
           f"🔑 كلمة المرور: {password}\n\n"
           "يمكنك الآن تسجيل الدخول.\n"
           "بعد تسجيل الدخول يمكنك توثيق حسابك من زر: 🪪 توثيق الحساب",
           reply_markup=auth_keyboard()
       )
       return

    elif text == "تسجيل دخول":
        user_states[user_id] = "login_username"
        await update.message.reply_text("أدخل اسم المستخدم:")
        return

    elif user_states.get(user_id) == "login_username":
        user_states[user_id] = {
            "step": "login_password",
            "username": text
        }
        await update.message.reply_text("أدخل كلمة المرور:")
        return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "login_password":
        username = user_states[user_id]["username"]
        password = text

        if username in users and users[username] == password:
            ensure_user_defaults(username)

            if is_user_banned(username):
                user_states.pop(user_id, None)
                await update.message.reply_text("⛔ هذا الحساب محظور، يرجى التواصل مع الإدارة")
                return

            logged_in_users[user_id] = username
            user_telegram_ids[username] = user_id
            save_data()
            user_states.pop(user_id, None)

            extra_msg = ""
            if is_user_frozen(username):
                extra_msg = "\n⚠️ حسابك مجمد ماليًا حاليًا، ولا يمكنك الإيداع أو السحب حتى تفك الإدارة التجميد."

            tg_first_name = user.first_name if user.first_name else "مستخدم"

            await update.message.reply_text(
                 f"👋 أهلاً بك {tg_first_name}{extra_msg}\n\n"
                 f"💎 عميلنا العزيز:\n\n"
                 f"عندما يقوم مشترك جديد بالاشتراك في المنصة عن طريق اسم المستخدم الخاص بك،\n"
                 f"سيتم إضافة بونص 20% 🎁 إلى رصيدك.\n\n"
                 f"📌 اسم المستخدم الخاص بك:\n"
                 f"{username}\n\n"
                 f"🔗 شاركه مع أصدقائك للاستفادة من نظام الإحالة.\n\n"
                 f"نتمنى لك تجربة موفقة 🚀"
                      )
            await update.message.reply_text("للاشتراك اختر احدى الباقات في الاسفل \n\nواتبع الخطوات بدقة لاتمام اشتراكك بنجاح \n\nاذا كنت مشترك لدينا يمكنك الانتقال فورا الى باقتي للدخول الى باقتك",
                                            reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
        return
    
    elif text == "👥 دعوة صديق":
        username = logged_in_users.get(user_id)

        if not username:
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
            return

        if is_user_banned(username):
            await update.message.reply_text("⛔ هذا الحساب محظور")
            return

        invite_link = build_referral_link(user_id)

        share_text = (
            "انضم إلى منصة Money factory عبر رابط دعوتي.\n\n"
            "بعد الدخول إلى البوت اضغط إنشاء حساب جديد، ثم وافق على شروط الاستخدام، "
            "وسيتم تسجيلك تلقائيًا ضمن دعوتي.\n\n"
            f"رابط الدعوة:\n{invite_link}"
        )

        telegram_share_url = (
            f"https://t.me/share/url?"
            f"url={quote(invite_link)}&"
            f"text={quote(share_text)}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📤 مشاركة عبر تيليغرام", url=telegram_share_url)
            ],
        ])

        await update.message.reply_text(
            f"👥 رابط دعوتك الخاص\n\n"
            f"عند دخول أي صديق من هذا الرابط وإنشاء حساب جديد، "
            f"سيتم تسجيله تلقائيًا تحت اسمك داخل نظام الإحالات.\n\n"
            f"🔗 رابط الدعوة:\n"
            f"{invite_link}\n\n"
            f"📌 اسم المستخدم الخاص بك داخل البوت:\n"
            f"{username}\n\n"
            f"🎁 عند أول إيداع للمشترك الجديد، ستحصل على بونص 20% من قيمة إيداعه.",
            reply_markup=keyboard
        )
        return

    elif text == "🔐 تغيير كلمة المرور":
        username = logged_in_users.get(user_id)

        if not username:
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
            return

        if is_user_banned(username):
            await update.message.reply_text("⛔ هذا الحساب محظور")
            return

        user_states[user_id] = {
            "step": "change_password_old"
        }
        await update.message.reply_text("أدخل كلمة المرور الحالية:")
        return
    
    elif text == "🗑 حذف حسابي":
        username = logged_in_users.get(user_id)

        if not username:
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
            return

        if is_user_banned(username):
            await update.message.reply_text("⛔ هذا الحساب محظور")
            return

        extra_warning = get_delete_account_warning_text(user_id, username)

        await update.message.reply_text(
            "⚠️ تنبيه هام جدًا!!\n\n"
            "سيتم حذف حسابك بما فيه جميع بياناتك نهائيًا، "
            "ولن تستطيع الوصول إليها مجددًا."
            f"{extra_warning}\n\n"
            "إذا كنت متأكدًا اضغط على تأكيد حذف الحساب، "
            "أو اضغط رجوع للتراجع.",
            reply_markup=build_delete_account_confirm_keyboard()
        )
        return
    
    elif text == "🪪 توثيق الحساب":
       username = logged_in_users.get(user_id)

       if not username:
           await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
           return

       if is_user_banned(username):
           await update.message.reply_text("⛔ هذا الحساب محظور")
           return

       if verified_users.get(username, False):
           await update.message.reply_text("✅ حسابك موثق بالفعل")
           return

       if user_id in pending_verification_requests:
           await update.message.reply_text("⏳ لديك طلب توثيق قيد المراجعة بالفعل")
           return

       user_states[user_id] = {
           "step": "verify_full_name"
       }

       await update.message.reply_text("أدخل الاسم والكنية كما هو موضح في البطاقة الشخصية:")
       return
    
    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "verify_full_name":
       full_name = text.strip()

       if len(full_name) < 5:
           await update.message.reply_text("❌ يرجى إدخال الاسم والكنية بشكل صحيح")
           return

       user_states[user_id] = {
            "step": "verify_residence",
            "full_name": full_name
             }

       await update.message.reply_text(
              "🌍 اختر دولة الإقامة من القائمة:",
                 reply_markup=country_selection_keyboard()
               )
       return


    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "verify_residence":
        country_label = text.strip()

        if country_label not in COUNTRY_TIMEZONES:
           await update.message.reply_text(
               "❌ يرجى اختيار الدولة من الأزرار الظاهرة فقط.",
               reply_markup=country_selection_keyboard()
           )
           return

        selected_country_data = COUNTRY_TIMEZONES[country_label]

        user_states[user_id] = {
           "step": "confirm_residence",
           "full_name": user_states[user_id]["full_name"],
           "country_label": country_label,
           "residence": selected_country_data["country"],
           "timezone": selected_country_data["timezone"]
              }

        await update.message.reply_text(
           get_country_choice_text(country_label),
           reply_markup=country_confirm_keyboard()
                )
        return
    
    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "confirm_residence":
      state = user_states[user_id]

      if text == "🔙 رجوع":
        user_states[user_id] = {
            "step": "verify_residence",
            "full_name": state["full_name"]
        }

        await update.message.reply_text(
            "🌍 اختر دولة الإقامة من القائمة:",
            reply_markup=country_selection_keyboard()
        )
        return

      if text != "✅ تأكيد الدولة":
        await update.message.reply_text(
            "❌ اختر أحد الأزرار:\n✅ تأكيد الدولة\n🔙 رجوع",
            reply_markup=country_confirm_keyboard()
        )
        return

      user_states[user_id] = {
        "step": "verify_id_front",
        "full_name": state["full_name"],
        "residence": state["residence"],
        "timezone": state["timezone"]
          }

      await update.message.reply_text(
        "✅ تم اعتماد دولة الإقامة بنجاح\n\n"
        f"🌍 الدولة: {state['residence']}\n\n"
        "📷 قم الآن برفع صورة واضحة للوجه الأمامي للهوية الشخصية:",
        reply_markup=main_menu_keyboard()
           )
      return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "change_password_old":
        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("انتهت الجلسة، سجّل الدخول مجددًا عبر /k")
            return

        old_password_entered = text
        real_password = users.get(username)

        if old_password_entered != real_password:
            await update.message.reply_text("❌ كلمة المرور الحالية غير صحيحة")
            return

        user_states[user_id] = {
            "step": "change_password_new",
            "old_password": real_password
        }
        await update.message.reply_text("أدخل كلمة المرور الجديدة:")
        return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "change_password_new":
        if len(text) < 3:
            await update.message.reply_text("❌ كلمة المرور الجديدة قصيرة جدًا، اجعلها 3 أحرف أو أكثر")
            return

        user_states[user_id] = {
            "step": "change_password_confirm",
            "old_password": user_states[user_id]["old_password"],
            "new_password": text
        }
        await update.message.reply_text("أعد إدخال كلمة المرور الجديدة للتأكيد:")
        return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "change_password_confirm":
        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("انتهت الجلسة، سجّل الدخول مجددًا عبر /k")
            return

        old_password = user_states[user_id]["old_password"]
        new_password = user_states[user_id]["new_password"]
        confirm_password = text

        if confirm_password != new_password:
            await update.message.reply_text("❌ التأكيد غير مطابق لكلمة المرور الجديدة")
            return

        users[username] = new_password
        save_users()

        add_transaction(username, "user_change_password", 0, f"قام المستخدم بتغيير كلمة المرور من {old_password} إلى {new_password}")

        user_states.pop(user_id, None)

        await update.message.reply_text("✅ تم تغيير كلمة المرور بنجاح")

        plan = user_plans.get(username, "NONE")
        capital = get_user_capital(username)
        balance = get_user_total_balance(username)
        profit_only = get_user_profit_only(username)

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🔐 قام المستخدم بتغيير كلمة المرور\n\n"
                    f"👤 اسم المستخدم: {username}\n"
                    f"🔑 كلمة المرور القديمة: {old_password}\n"
                    f"🔑 كلمة المرور الجديدة: {new_password}\n"
                    f"📌 حالة الحساب: {get_status_text(username)}\n"
                    f"📦 الباقة: {plan}\n"
                    f"💰 رأس المال: {capital}$\n"
                    f"📈 الرصيد الحالي: {balance}$\n"
                    f"💵 الأرباح فقط: {profit_only}$\n"
                    f"🕒 الوقت: {now_str()}"
                )
            )
        except Exception as e:
            print(f"خطأ في إرسال إشعار تغيير كلمة المرور للأدمن: {e}")

        return
        # -------------------------
    # مراسلة الدعم
    # -------------------------
    elif text == "📩 مراسلة الدعم":
         username = logged_in_users.get(user_id)

         if not username:
             await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
             return

         if is_support_blocked(username):
             await update.message.reply_text("🚫 تم منعك من مراسلة الدعم")
             return

         if support_waiting_reply.get(username, False) and not has_active_support_claim(username):
             await update.message.reply_text(
                 "⏳ لا يمكنك إرسال رسالة جديدة إلى الدعم الآن\n"
                 "لقد أرسلت رسالة بالفعل وبانتظار رد الإدارة"
             )
             return

         user_states[user_id] = {
              "step": "support_message"
              }

         await update.message.reply_text(
                "📩 اكتب الآن رسالتك إلى الدعم الفني أو أرسل صورة.\n"
                "سيتم إرسالها مباشرة إلى الإدارة."
                )
         return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "support_message":
        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("انتهت الجلسة، سجّل الدخول مجددًا عبر /k")
            return

        if is_support_blocked(username):
            user_states.pop(user_id, None)
            await update.message.reply_text("🚫 تم منعك من مراسلة الدعم")
            return

        if support_waiting_reply.get(username, False) and not has_active_support_claim(username):
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "⏳ لا يمكنك إرسال رسالة جديدة إلى الدعم الآن\n"
                "لقد أرسلت رسالة بالفعل وبانتظار رد الإدارة"
            )
            return

        support_text = text.strip()

        if not support_text:
            await update.message.reply_text("❌ لا يمكن إرسال رسالة فارغة")
            return

        ensure_user_defaults(username)
        update_profit(username)

        tg_name = user.first_name if user.first_name else "غير متوفر"
        tg_username_text = f"@{user.username}" if user.username else "لا يوجد"
        plan = user_plans.get(username, "NONE")
        balance = get_user_total_balance(username)
        capital = get_user_capital(username)
        profit_only = get_user_profit_only(username)

        try:
            support_keyboard = build_support_reply_keyboard(user_id)

            support_message_text = (
              f"📩 رسالة دعم جديدة\n\n"
              f"👤 الاسم داخل البوت: {username}\n"
              f"🙍 الاسم الأول: {tg_name}\n"
              f"📱 يوزر تيليغرام: {tg_username_text}\n"
              f"🆔 Telegram ID: {user_id}\n"
              f"📌 حالة الحساب: {get_status_text(username)}\n"
              f"📦 الباقة: {plan}\n"
              f"💰 رأس المال: {capital}$\n"
              f"📈 الرصيد الحالي: {balance}$\n"
              f"💵 الأرباح فقط: {profit_only}$\n"
              f"🕒 الوقت: {now_str()}\n"
              f"📝 النوع: نص\n\n"
              f"📝 محتوى الرسالة:\n{support_text}"
                )

            await send_support_text_to_operators(
                context=context,
                target_user_id=user_id,
                username=username,
                message_text=support_message_text,
                reply_markup=support_keyboard
                  )

            add_transaction(username, "support_message", 0, f"أرسل رسالة دعم نصية: {support_text[:80]}")
            support_waiting_reply[username] = True
            save_data()

            user_states.pop(user_id, None)

            await update.message.reply_text("✅ تم إرسال رسالتك إلى الدعم بنجاح")
        except Exception as e:
            print(f"خطأ في إرسال رسالة الدعم: {e}")
            await update.message.reply_text("❌ حدث خطأ أثناء إرسال الرسالة، حاول مرة أخرى")
        return
    
    elif text == "🚪 تسجيل خروج":
        if user_id in logged_in_users:
            logged_in_users.pop(user_id, None)
            save_data()
            await update.message.reply_text(
                "✅ تم تسجيل الخروج بنجاح",
                reply_markup=auth_keyboard()
            )
        else:
            await update.message.reply_text("❌ أنت غير مسجل الدخول حالياً")
        return

    elif text == "📥 طلبات الإيداع":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        if not pending_deposit_requests:
            await update.message.reply_text("📭 لا توجد طلبات إيداع معلقة حالياً")
            return

        lines = ["📥 طلبات الإيداع المعلقة:\n"]
        for req_user_id, req in pending_deposit_requests.items():
            user_status = get_status_text(req["username"])
            lines.append(
                f"👤 المستخدم: {req['username']}\n"
                f"🆔 ID: {req_user_id}\n"
                f"📌 الحالة: {user_status}\n"
                f"📦 الباقة: {req['plan']}\n"
                f"💰 المبلغ: {req['amount']}$\n"
                f"➖➖➖➖➖"
            )

        await update.message.reply_text("\n".join(lines))
        return

    elif text == "💸 طلبات السحب":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        if not pending_withdraw_requests:
            await update.message.reply_text("📭 لا توجد طلبات سحب معلقة حالياً")
            return

        lines = ["💸 طلبات السحب المعلقة:\n"]
        for req_user_id, req in pending_withdraw_requests.items():
            user_status = get_status_text(req["username"])
            lines.append(
                f"👤 المستخدم: {req['username']}\n"
                f"🆔 ID: {req_user_id}\n"
                f"📌 الحالة: {user_status}\n"
                f"📦 الباقة: {req['plan']}\n"
                f"💰 مبلغ السحب: {req['amount']}$\n"
                f"🕒 وقت الطلب: {req['time']}\n"
                f"➖➖➖➖➖"
            )

        await update.message.reply_text("\n".join(lines))
        return
    
    elif text == "🏦 طلبات سحب رأس المال":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        await update.message.reply_text(build_capital_withdraw_requests_text())
        return
    
    elif text == "🗑 سجل الحسابات المحذوفة":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        await update.message.reply_text(build_deleted_accounts_log_text())
        return

    elif text == "👥 عدد المستخدمين":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        root_users = get_all_root_users()
        total_users = len(users)

        if not root_users:
            await update.message.reply_text(
                f"👥 شجرة جميع المستخدمين\n"
                f"📊 العدد الكلي للمستخدمين: {total_users}\n\n"
                f"📭 لا توجد جذور متاحة حاليًا"
            )
            return

        view_id = create_tree_view(
            view_type="all_users_tree",
            usernames=root_users,
            title=(
                f"👥 شجرة جميع المستخدمين\n"
                f"📊 العدد الكلي للمستخدمين: {total_users}\n\n"
                f"اختر جذرًا لعرض أبنائه:"
            ),
            status=None,
            parent_username=None,
            back_view_id=None
        )
        cleanup_tree_views()

        await update.message.reply_text(
            (
                f"👥 شجرة جميع المستخدمين\n"
                f"📊 العدد الكلي للمستخدمين: {total_users}\n\n"
                f"اختر جذرًا لعرض أبنائه:"
            ),
            reply_markup=build_all_users_tree_keyboard(view_id)
        )
        return

    elif text == "📊 ملخص مالي":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        total_capital = round(sum(float(v) for v in user_deposits.values()), 2)
        total_balances = round(sum(float(v) for v in user_balance.values()), 2)
        total_pending_deposits = round(sum(float(req["amount"]) for req in pending_deposit_requests.values()), 2)
        total_pending_withdraws = round(sum(float(req["amount"]) for req in pending_withdraw_requests.values()), 2)

        await update.message.reply_text(
            f"📊 الملخص المالي:\n\n"
            f"💰 إجمالي رأس المال: {total_capital}$\n"
            f"📈 إجمالي الأرصدة الحالية: {total_balances}$\n"
            f"📥 إجمالي الإيداعات المعلقة: {total_pending_deposits}$\n"
            f"💸 إجمالي السحوبات المعلقة: {total_pending_withdraws}$"
        )
        return
    

    elif text == "📢 إرسال رسالة للجميع":
      if user_id != ADMIN_ID:
          await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
          return

      user_states[user_id] = {"step": "admin_send_broadcast"}
      await update.message.reply_text(
          "📢 اكتب الآن الرسالة التي تريد إرسالها إلى جميع المستخدمين:\n\n"
          "للتراجع اضغط: 🔙 إلغاء الإرسال",
          reply_markup=admin_cancel_keyboard()
      )
      return
    
    elif text == "🛠 حالة البوت":
      if user_id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
        return

      await update.message.reply_text(
        f"🛠 حالة البوت الحالية: {get_bot_maintenance_status_text()}"
      )
      return

    elif text == "⏯ إيقاف/تشغيل البوت":
      if user_id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
        return

      await update.message.reply_text(
        f"🛠 حالة البوت الحالية: {get_bot_maintenance_status_text()}\n"
        f"اختر الإجراء المطلوب:",
        reply_markup=build_bot_maintenance_keyboard()
      )
      return
    
    elif text == "📌 حالة الاشتراك":
      if user_id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
        return

      await update.message.reply_text(
        f"📌 الحالة العامة للاشتراك: {get_subscriptions_status_text()}"
          )
      return
    
    elif text == "⛔ إيقاف/تشغيل الاشتراك":
      if user_id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
        return

      keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⛔ إيقاف الاشتراك", callback_data="admin_close_subscriptions"),
            InlineKeyboardButton("✅ تشغيل الاشتراك", callback_data="admin_open_subscriptions")
        ]
       ])

      await update.message.reply_text(
        f"📌 الحالة الحالية: {get_subscriptions_status_text()}\nاختر الإجراء المطلوب:",
        reply_markup=keyboard
       )
      return
    
    elif text == "📂 فلترة المستخدمين":
      if user_id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
        return

      active_count = sum(1 for u in users if get_user_status(u) == "active")
      frozen_count = sum(1 for u in users if get_user_status(u) == "frozen")
      banned_count = sum(1 for u in users if get_user_status(u) == "banned")

      keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ النشطون ({active_count})", callback_data="filter_users_active")],
        [InlineKeyboardButton(f"⚠️ المجمدون ({frozen_count})", callback_data="filter_users_frozen")],
        [InlineKeyboardButton(f"⛔ المحظورون ({banned_count})", callback_data="filter_users_banned")]
      ])

      await update.message.reply_text(
        "اختر نوع المستخدمين الذين تريد عرضهم:",
        reply_markup=keyboard
      )
      return   

    elif text == "📨 إرسال رسالة حسب الباقة":
      if user_id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
        return

      keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("الفضية", callback_data="msg_plan_الباقة الفضية"),
            InlineKeyboardButton("الذهبية", callback_data="msg_plan_الباقة الذهبية"),
            InlineKeyboardButton("VIP", callback_data="msg_plan_باقة VIP")
        ]
       ])

      await update.message.reply_text(
        "اختر الباقة التي تريد إرسال الرسالة إلى مشتركيها:",
        reply_markup=keyboard
       )
      return  
    
    elif text == "📈 إحصائيات متقدمة":
      if user_id != ADMIN_ID:
          await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
          return

      total_users = len(users)
      active_count = sum(1 for s in user_statuses.values() if s == "active")
      frozen_count = sum(1 for s in user_statuses.values() if s == "frozen")
      banned_count = sum(1 for s in user_statuses.values() if s == "banned")

      silver_count = sum(1 for p in user_plans.values() if p == "الباقة الفضية")
      gold_count = sum(1 for p in user_plans.values() if p == "الباقة الذهبية")
      vip_count = sum(1 for p in user_plans.values() if p == "باقة VIP")
      no_plan_count = sum(1 for p in user_plans.values() if p in [None, "NONE"])

      total_capital = round(sum(float(v) for v in user_deposits.values()), 2)
      total_balances = round(sum(float(v) for v in user_balance.values()), 2)
      total_profit_only = round(total_balances - total_capital, 2)
      if total_profit_only < 0:
        total_profit_only = 0

      await update.message.reply_text(
          f"📈 الإحصائيات المتقدمة\n\n"
          f"👥 إجمالي المستخدمين: {total_users}\n"
          f"✅ النشطون: {active_count}\n"
          f"⚠️ المجمدون: {frozen_count}\n"
          f"⛔ المحظورون: {banned_count}\n\n"
          f"📦 مشتركو الفضية: {silver_count}\n"
          f"🥇 مشتركو الذهبية: {gold_count}\n"
          f"💎 مشتركو VIP: {vip_count}\n"
          f"📭 بدون باقة: {no_plan_count}\n\n"
          f"💰 إجمالي رأس المال: {total_capital}$\n"
          f"📈 إجمالي الأرصدة: {total_balances}$\n"
          f"💵 إجمالي الأرباح فقط: {total_profit_only}$\n\n"
          f"📌 حالة الاشتراك العامة: {get_subscriptions_status_text()}"
           )
      return

    elif text == "🔍 بحث عن مستخدم":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        user_states[user_id] = {"step": "admin_search_user"}
        await update.message.reply_text("أرسل الآن اسم المستخدم الذي تريد البحث عنه:")
        return
    
    elif text == "🗑 حذف مستخدم":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        user_states[user_id] = {"step": "admin_delete_user_search"}
        await update.message.reply_text("أرسل الآن اسم المستخدم الذي تريد حذف حسابه:")
        return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_search_user":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        username = text
        user_states.pop(user_id, None)

        if username not in users:
            await update.message.reply_text("❌ هذا المستخدم غير موجود")
            return

        await update.message.reply_text(
            build_admin_user_text(username),
            reply_markup=build_admin_user_keyboard(username)
        )
        return
    
    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_delete_user_search":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ هذا الخيار خاص بالأدمن فقط")
            return

        username = text.strip()
        user_states.pop(user_id, None)

        if username not in users:
            await update.message.reply_text("❌ هذا المستخدم غير موجود")
            return

        full_name = user_full_name.get(username, "غير متوفر")
        status_text = get_status_text(username)
        plan = user_plans.get(username, "NONE")
        capital = get_user_capital(username)
        balance = get_user_total_balance(username)
        profit_only = get_user_profit_only(username)

        await update.message.reply_text(
            f"⚠️ تأكيد حذف المستخدم\n\n"
            f"👤 اسم المستخدم: {username}\n"
            f"👤 الاسم والكنية: {full_name}\n"
            f"📌 الحالة: {status_text}\n"
            f"📦 الباقة: {plan}\n"
            f"💰 رأس المال: {capital}$\n"
            f"📈 الرصيد الحالي: {balance}$\n"
            f"💵 الأرباح فقط: {profit_only}$\n\n"
            f"هل أنت متأكد من حذف هذا الحساب نهائيًا؟",
            reply_markup=build_admin_delete_user_confirm_keyboard(username)
        )
        return
        # -------------------------
    # رد الأدمن على المستخدم
    # -------------------------
    elif is_support_operator(user_id) and isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_reply_support":
        reply_text = text.strip()

        if not reply_text:
            await update.message.reply_text("❌ لا يمكن إرسال رد فارغ")
            return

        target_user_id = user_states[user_id]["target_user_id"]

        target_username = logged_in_users.get(target_user_id)
        if not target_username:
            # محاولة عكسية لإيجاد اسم المستخدم
            for uname in users:
                found_id = find_user_id_by_username(uname)
                if found_id == target_user_id:
                    target_username = uname
                    break

        try:
            batch_id = create_admin_batch("support_reply", f"user_id:{target_user_id}")

            sent_msg = await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"📩 رد من الدعم:\n\n"
                    f"{reply_text}"
                )
            )

            add_message_to_batch(batch_id, target_user_id, sent_msg.message_id)

            if target_username:
               operator_text = get_support_operator_text(user_id)

               add_transaction(
                   target_username,
                   "support_reply",
                   0,
                   f"رد {operator_text} ID {user_id}: {reply_text[:80]}"
                )

               support_waiting_reply.pop(target_username, None)
               save_data()

               if is_support_employee(user_id):
                  try:
                       employee_name = user_full_name.get(
                         logged_in_users.get(user_id, ""),
                         "غير موثق"
                       )

                       await context.bot.send_message(
                          chat_id=ADMIN_ID,
                          text=(
                            f"👨‍💼 رد موظف دعم على المستخدم\n\n"
                            f"👤 المستخدم: {target_username}\n"
                            f"🆔 User ID: {target_user_id}\n"
                            f"👨‍💼 موظف الدعم: {employee_name} ({user_id})\n"
                            f"🆔 ID: {user_id}\n"
                            f"🕒 الوقت: {now_str()}\n\n"
                            f"📝 الرد:\n{reply_text}"
                            )
                             )
                  except Exception as e:
                       print(f"خطأ في إرسال إشعار رد موظف الدعم للمدير: {e}")

            user_states.pop(user_id, None)

            await update.message.reply_text(
                "✅ تم إرسال الرد إلى المستخدم بنجاح",
                reply_markup=admin_keyboard() if user_id == ADMIN_ID else main_menu_keyboard()
            )

            await update.message.reply_text(
                "يمكنك حذف آخر إرسال إذا أردت:",
                reply_markup=build_delete_last_batch_keyboard()
            )
        except Exception as e:
            print(f"خطأ في إرسال رد الدعم: {e}")
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "❌ تعذر إرسال الرد إلى المستخدم",
                reply_markup=admin_keyboard() if user_id == ADMIN_ID else main_menu_keyboard()
            )
        return
    
    elif user_id == ADMIN_ID and isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_add_wallet_address":
        wallet_address = text.strip()
        if not wallet_address:
            await update.message.reply_text("❌ أدخل عنوان محفظة صحيح")
            return

        user_states[user_id] = {
            "step": "admin_add_wallet_network",
            "target_user_id": user_states[user_id]["target_user_id"],
            "target_username": user_states[user_id]["target_username"],
            "wallet_address": wallet_address
        }

        await update.message.reply_text(
            "🌐 أدخل الآن اسم الشبكة",
            reply_markup=admin_cancel_keyboard()
        )
        return

    elif user_id == ADMIN_ID and isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_add_wallet_network":
        network_name = text.strip()
        if not network_name:
            await update.message.reply_text("❌ أدخل اسم شبكة صحيح")
            return

        username = user_states[user_id]["target_username"]
        wallet_address = user_states[user_id]["wallet_address"]

        user_wallet_address[username] = wallet_address
        user_wallet_network[username] = network_name
        save_data()

        user_states.pop(user_id, None)

        await update.message.reply_text(
            f"✅ تم حفظ عنوان المحفظة بنجاح للمستخدم {username}\n\n"
            f"💼 العنوان: {wallet_address}\n"
            f"🌐 الشبكة: {network_name}",
            reply_markup=admin_keyboard()
        )
        return
    
        # -------------------------
    # إدخال الأدمن لإضافة رصيد
    # -------------------------
    elif user_id == ADMIN_ID and isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_add_balance_input":
        username = user_states[user_id]["target_username"]

        try:
            amount = float(text)
        except:
            await update.message.reply_text("❌ أدخل مبلغًا صحيحًا")
            return

        if username not in users:
            user_states.pop(user_id, None)
            await update.message.reply_text("❌ المستخدم غير موجود")
            return

        if amount <= 0:
            await update.message.reply_text("❌ يجب أن يكون المبلغ أكبر من صفر")
            return

        user_balance[username] = round(float(user_balance.get(username, 0)) + amount, 2)
        save_data()
        add_transaction(username, "admin_add_balance", amount, "إضافة رصيد يدوي بواسطة الأدمن")

        user_states.pop(user_id, None)

        user_id_found = find_user_id_by_username(username)
        if user_id_found:
            try:
                await context.bot.send_message(
                    chat_id=user_id_found,
                    text=f"✅ تمت إضافة {amount}$ إلى رصيدك بواسطة الإدارة"
                )
            except:
                pass

        await update.message.reply_text(
            f"✅ تمت إضافة {amount}$ إلى رصيد المستخدم {username}\n\n"
            f"{build_admin_user_text(username)}",
            reply_markup=build_admin_user_keyboard(username)
        )
        return

    # -------------------------
    # إدخال الأدمن لخصم رصيد
    # -------------------------
    elif user_id == ADMIN_ID and isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_sub_balance_input":
        username = user_states[user_id]["target_username"]

        try:
            amount = float(text)
        except:
            await update.message.reply_text("❌ أدخل مبلغًا صحيحًا")
            return

        if username not in users:
            user_states.pop(user_id, None)
            await update.message.reply_text("❌ المستخدم غير موجود")
            return

        if amount <= 0:
            await update.message.reply_text("❌ يجب أن يكون المبلغ أكبر من صفر")
            return

        current_balance = float(user_balance.get(username, 0))
        new_balance = round(current_balance - amount, 2)

        if new_balance < 0:
            new_balance = 0

        deducted = round(current_balance - new_balance, 2)
        user_balance[username] = new_balance
        save_data()
        add_transaction(username, "admin_subtract_balance", deducted, "خصم رصيد يدوي بواسطة الأدمن")

        user_states.pop(user_id, None)

        user_id_found = find_user_id_by_username(username)
        if user_id_found:
            try:
                await context.bot.send_message(
                    chat_id=user_id_found,
                    text=f"⚠️ تم خصم {deducted}$ من رصيدك بواسطة الإدارة"
                )
            except:
                pass

        await update.message.reply_text(
            f"✅ تمت عملية الخصم من المستخدم {username}\n"
            f"💸 المبلغ المخصوم: {deducted}$\n\n"
            f"{build_admin_user_text(username)}",
            reply_markup=build_admin_user_keyboard(username)
        )
        return
    
        # -------------------------
    # إرسال رسالة خاصة من الأدمن إلى مستخدم
    # -------------------------
    elif user_id == ADMIN_ID and isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_send_private_message":
        username = user_states[user_id]["target_username"]
        message_text = text.strip()

        if not message_text:
              await update.message.reply_text("❌ لا يمكن إرسال رسالة فارغة")
              return

        if username not in users:
              user_states.pop(user_id, None)
              await update.message.reply_text("❌ المستخدم غير موجود")
              return

        target_user_id = get_saved_telegram_id(username)

        if not target_user_id:
              user_states.pop(user_id, None)
              await update.message.reply_text("❌ لا يوجد Telegram ID محفوظ لهذا المستخدم بعد")
              return

        try:
            batch_id = create_admin_batch("private_message", f"user:{username}")

            sent_msg = await context.bot.send_message(
              chat_id=target_user_id,
              text=(
                f"📨 رسالة من الإدارة:\n\n"
                f"{message_text}"
                  )
            )

            add_message_to_batch(batch_id, target_user_id, sent_msg.message_id)

            add_transaction(username, "admin_private_message", 0, f"أرسل الأدمن رسالة خاصة: {message_text[:80]}")
            user_states.pop(user_id, None)

            await update.message.reply_text(
                  f"✅ تم إرسال الرسالة إلى المستخدم {username}",
                  reply_markup=admin_keyboard()
                )

            await update.message.reply_text(
                "يمكنك حذف آخر إرسال إذا أردت:",
                reply_markup=build_delete_last_batch_keyboard()
            )
        except Exception as e:
              print(f"خطأ في إرسال الرسالة الخاصة: {e}")
              user_states.pop(user_id, None)
              await update.message.reply_text(
                  "❌ تعذر إرسال الرسالة إلى المستخدم، ربما لم يبدأ البوت بعد أو قام بحظره",
                  reply_markup=admin_keyboard()
              )
        return 
    
    elif user_id == ADMIN_ID and isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_send_plan_message":
      plan_name = user_states[user_id]["target_plan"]
      message_text = text.strip()

      if not message_text:
          await update.message.reply_text("❌ لا يمكن إرسال رسالة فارغة")
          return

      target_users = [u for u, p in user_plans.items() if p == plan_name]
      sent_count = 0
      batch_id = create_admin_batch("plan_message", f"plan:{plan_name}")

      for username in target_users:
          target_user_id = get_saved_telegram_id(username)
          if not target_user_id:
              continue

          try:
                sent_msg = await context.bot.send_message(
                  chat_id=target_user_id,
                  text=f"📨 رسالة من الإدارة لمشتركي {plan_name}:\n\n{message_text}"
              )
                add_message_to_batch(batch_id, target_user_id, sent_msg.message_id)
                sent_count += 1
          except:
              pass

      user_states.pop(user_id, None)

      await update.message.reply_text(
        f"✅ تم إرسال الرسالة إلى {sent_count} مستخدم من مشتركي {plan_name}",
        reply_markup=admin_keyboard()
         )

      await update.message.reply_text(
        "يمكنك حذف آخر إرسال إذا أردت:",
        reply_markup=build_delete_last_batch_keyboard()
      )
      return
    
    elif user_id == ADMIN_ID and isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "admin_send_broadcast":
      message_text = text.strip()

      if not message_text:
          await update.message.reply_text("❌ لا يمكن إرسال رسالة فارغة")
          return

      success = 0
      failed = 0
      batch_id = create_admin_batch("broadcast", "all_users")

      for uid in chat_ids:
          try:
              sent_msg = await context.bot.send_message(
                  chat_id=uid,
                  text=message_text
                  )
              add_message_to_batch(batch_id, uid, sent_msg.message_id)
              success += 1
              await asyncio.sleep(0.05)
          except:
              failed += 1

      user_states.pop(user_id, None)

      await update.message.reply_text(
          f"✅ تم إرسال الرسالة الجماعية بنجاح\n\n"
          f"📨 عدد الناجحين: {success}\n"
          f"❌ عدد الذين تعذر الإرسال لهم: {failed}",
          reply_markup=admin_keyboard()
      )

      await update.message.reply_text(
          "يمكنك حذف آخر إرسال إذا أردت:",
          reply_markup=build_delete_last_batch_keyboard()
      )
      return

    elif text == "🔙 رجوع":
        user_states.pop(user_id, None)

        username = logged_in_users.get(user_id)

        if user_id == ADMIN_ID:
            await update.message.reply_text("تم الرجوع.", reply_markup=admin_keyboard())
        elif username:
            await update.message.reply_text("تم الرجوع.", reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text("اختر خيار:", reply_markup=auth_keyboard())
        return

    elif text == "الصفحة الرئيسية":
        username = logged_in_users.get(user_id)

        if not username:
             await update.message.reply_text(
            "يجب تسجيل الدخول أولاً ❌",
            reply_markup=auth_keyboard()
            )
             return

        if is_user_banned(username):
            await update.message.reply_text("⛔ هذا الحساب محظور، يرجى التواصل مع الإدارة")
            return

        await update.message.reply_text(
        "🏠 أهلاً بك في الصفحة الرئيسية\nاختر من القائمة في الأسفل ما تريد:",
        reply_markup=main_menu_keyboard()
         )
        return    

    elif text in PLANS:
        username = logged_in_users.get(user_id)

        if not username:
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
            return

        if not subscriptions_open:
            await update.message.reply_text(
                "⛔ الاشتراك في الباقات متوقف حاليًا من قبل الإدارة.\nيرجى المحاولة لاحقًا."
            )
            return

        ensure_user_defaults(username)

        if is_user_banned(username):
            await update.message.reply_text("⛔ حسابك محظور")
            return

        if is_user_frozen(username):
            await update.message.reply_text("⚠️ حسابك مجمد ماليًا، ولا يمكن طلب إيداع جديد حاليًا")
            return
        
        if has_active_capital_withdraw_request(username):
            await update.message.reply_text(
                "⛔ لا يمكنك تنفيذ أي إيداع أو اشتراك جديد حاليًا\n\n"
                "لديك طلب سحب رأس مال قيد الانتظار.\n"
                f"⌛ الوقت المتبقي: {get_capital_withdraw_countdown_text(username)}"
            )
            return

        if user_plans.get(username) not in [None, "NONE"]:
            await update.message.reply_text("❌ لديك باقة مفعلة بالفعل ولا يمكنك الاشتراك بأكثر من باقة")
            return

        if user_plans.get(username) not in [None, "NONE"]:
            await update.message.reply_text("❌ لديك باقة مفعلة بالفعل ولا يمكنك الاشتراك بأكثر من باقة")
            return

        if user_id in pending_deposit_requests:
            await update.message.reply_text("⏳ لديك طلب إيداع معلق بالفعل بانتظار مراجعة الإدارة")
            return

        await update.message.reply_text(
            build_plan_features_text(text),
            reply_markup=build_plan_action_keyboard(text)
        )
        return
    
    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "plan_change_enter_amount":
      username = logged_in_users.get(user_id)

      if not username:
          user_states.pop(user_id, None)
          await update.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
          return
      
      if has_active_capital_withdraw_request(username):
          user_states.pop(user_id, None)
          await update.message.reply_text(
              "⛔ تم إلغاء عملية تغيير الباقة\n\n"
              "لديك طلب سحب رأس مال قيد الانتظار، ولا يمكنك تغيير الباقة حتى تتم معالجة الطلب.",
              reply_markup=main_menu_keyboard()
          )
          return

      try:
          amount = float(text)
      except:
          await update.message.reply_text("❌ أدخل مبلغًا صحيحًا بالأرقام فقط")
          return

      target_plan = user_states[user_id]["target_plan"]
      required_amount = float(user_states[user_id]["required_amount"])
      target_max_deposit = PLANS[target_plan]["max_deposit"]

      if target_max_deposit is not None and amount > target_max_deposit:
         await update.message.reply_text(
              f"❌ الحد الأعلى للإيداع في {target_plan} هو {target_max_deposit}$"
                  )
         return

      if amount < required_amount:
          await update.message.reply_text(
              f"❌ الحد الأدنى المطلوب لتغيير الباقة إلى {target_plan} هو {required_amount}$"
          )
          return

      user_states[user_id] = {
          "step": "send_plan_change_proof",
          "target_plan": target_plan,
          "amount": amount
      }

      await update.message.reply_text(
          f"💰 مبلغ الإيداع الذي اخترته لتغيير الباقة: {amount}$\n\n"
          f"يرجى الآن تحويل المبلغ إلى عنوان المحفظة التالي، مع اختيار الشبكة: TRC20"
      )
      await update.message.reply_text("عنوان المحفظة:")
      await update.message.reply_text("TFuFGGiWGUFB4Z1sCSZiVfjkxhUWJmZ6nQ")
      await update.message.reply_text("📸 بعد التحويل، قم بأخذ لقطة شاشة لإشعار الإرسال وأرسل لنا إثبات الدفع")
      return
    
    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "topup_enter_amount":
        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
            return
        
        if has_active_capital_withdraw_request(username):
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "⛔ تم إلغاء عملية الإيداع الجديد\n\n"
                "لديك طلب سحب رأس مال قيد الانتظار، ولا يمكنك الإيداع حتى تتم معالجة الطلب.",
                reply_markup=main_menu_keyboard()
            )
            return

        try:
            amount = float(text)
        except:
            await update.message.reply_text("❌ أدخل مبلغًا صحيحًا بالأرقام فقط")
            return

        if amount <= 0:
            await update.message.reply_text("❌ يجب أن يكون مبلغ الإيداع أكبر من صفر")
            return

        current_plan = user_states[user_id]["current_plan"]

        if current_plan not in PLANS:
            user_states.pop(user_id, None)
            await update.message.reply_text("❌ باقتك الحالية غير معروفة داخل النظام", reply_markup=main_menu_keyboard())
            return

        current_capital = get_user_capital(username)
        final_capital = round(current_capital + amount, 2)

        current_plan_data = PLANS[current_plan]
        current_max_deposit = current_plan_data["max_deposit"]

        suitable_plan = get_plan_by_capital_amount(final_capital)

        # إذا كان رأس المال النهائي خرج من حدود الباقة الحالية
        if current_max_deposit is not None and final_capital > float(current_max_deposit):
            if suitable_plan and suitable_plan != current_plan:
                await update.message.reply_text(
                    f"⚠️ لا يمكن إضافة هذا الإيداع ضمن باقتك الحالية\n\n"
                    f"📦 باقتك الحالية: {current_plan}\n"
                    f"💰 رأس مالك الحالي: {current_capital}$\n"
                    f"➕ مبلغ الإيداع الجديد: {amount}$\n"
                    f"📈 رأس المال بعد الإيداع: {final_capital}$\n\n"
                    f"✅ هذا الرصيد يؤهلك للانضمام إلى:\n"
                    f"📦 {suitable_plan}\n\n"
                    f"يرجى استخدام خيار:\n"
                    f"📦 تغيير الباقة الحالية\n"
                    f"من داخل صفحة باقتي.",
                    reply_markup=main_menu_keyboard()
                )
                user_states.pop(user_id, None)
                return

            await update.message.reply_text(
                f"❌ المبلغ الجديد يتجاوز حدود باقتك الحالية\n\n"
                f"📦 باقتك الحالية: {current_plan}\n"
                f"📈 رأس المال بعد الإيداع: {final_capital}$"
            )
            user_states.pop(user_id, None)
            return

        # في حال VIP لا يوجد حد أعلى
        user_states[user_id] = {
            "step": "send_topup_proof",
            "amount": amount,
            "current_plan": current_plan,
            "final_capital": final_capital
        }

        await update.message.reply_text(
            f"✅ الإيداع الجديد مناسب لباقتك الحالية\n\n"
            f"📦 الباقة: {current_plan}\n"
            f"💰 رأس المال الحالي: {current_capital}$\n"
            f"➕ مبلغ الإيداع الجديد: {amount}$\n"
            f"📈 رأس المال بعد الموافقة: {final_capital}$\n\n"
            f"يرجى تحويل المبلغ إلى عنوان المحفظة التالي على شبكة TRC20:"
        )

        await update.message.reply_text("TFuFGGiWGUFB4Z1sCSZiVfjkxhUWJmZ6nQ")

        await update.message.reply_text(
            "📸 بعد التحويل، قم بإرسال صورة إثبات الدفع"
        )
        return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "enter_amount":
        try:
            amount = int(text)
        except:
            await update.message.reply_text("❌ أدخل مبلغًا صحيحًا بالأرقام فقط")
            return

        plan_key = user_states[user_id]["plan"]
        plan = PLANS[plan_key]

        max_deposit = plan["max_deposit"]

        if amount < plan["min_deposit"] or (max_deposit is not None and amount > max_deposit):
           max_text = "بدون حد أعلى" if max_deposit is None else f"{max_deposit}$"

           await update.message.reply_text(
               f"❌ المبلغ يجب أن يكون ابتداءً من {plan['min_deposit']}$ وحتى {max_text}"
            )
           return

        user_states[user_id]["amount"] = amount
        user_states[user_id]["step"] = "send_proof"

        await update.message.reply_text(
               f"💰 قم بتحويل {amount} USDT إلى عنوان المحفظة التالي:\n"
               
                  )
        await update.message.reply_text("TFuFGGiWGUFB4Z1sCSZiVfjkxhUWJmZ6nQ")
        await update.message.reply_text(
            "🌐 على الشبكة: TRC20"
            
        )

        await update.message.reply_text("📸  بعد التحويل قم بأخذ لقطة شاشة لإشعار الإرسال وأرسل لنا إثبات الدفع")
        return

    elif text == "باقتي":
        username = logged_in_users.get(user_id)

        if not username:
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
            return

        text_message = build_my_plan_text(username, user_id)

        if text_message == "❌ لا توجد لديك باقة مفعلة حالياً":
            await update.message.reply_text(text_message)
            return

        await update.message.reply_text(
            text_message,
            reply_markup=build_my_plan_keyboard(username)
        )
        return

    elif text == "📜 سجل العمليات":
        username = logged_in_users.get(user_id)

        if not username:
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
            return

        await update.message.reply_text(build_user_financial_history_text(username))
        return
    
    elif text == "➕ إيداع جديد":
        username = logged_in_users.get(user_id)

        if not username:
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
            return

        ensure_user_defaults(username)

        if is_user_banned(username):
            await update.message.reply_text("⛔ حسابك محظور")
            return

        if is_user_frozen(username):
            await update.message.reply_text("⚠️ حسابك مجمد ماليًا، ولا يمكنك تنفيذ إيداع جديد حاليًا")
            return
        
        if has_active_capital_withdraw_request(username):
            await update.message.reply_text(
                "⛔ لا يمكنك تنفيذ إيداع جديد حاليًا\n\n"
                "لديك طلب سحب رأس مال قيد الانتظار.\n"
                f"⌛ الوقت المتبقي: {get_capital_withdraw_countdown_text(username)}\n\n"
                "بعد تنفيذ طلب سحب رأس المال وإغلاق الباقة، يمكنك الاشتراك من جديد."
            )
            return

        current_plan = user_plans.get(username, "NONE")

        if current_plan in [None, "NONE"]:
            await update.message.reply_text(
                "❌ لا توجد لديك باقة مفعلة حاليًا\n\n"
                "لإضافة رصيد يجب أن تكون مشتركًا في باقة أولًا."
            )
            return

        if current_plan not in PLANS:
            await update.message.reply_text("❌ باقتك الحالية غير معروفة داخل النظام")
            return

        if user_id in pending_deposit_requests:
            await update.message.reply_text("⏳ لديك طلب إيداع معلق بالفعل بانتظار مراجعة الإدارة")
            return

        current_capital = get_user_capital(username)
        current_balance = get_user_total_balance(username)
        current_plan_data = PLANS[current_plan]

        max_deposit = current_plan_data["max_deposit"]
        max_text = "بدون حد أعلى" if max_deposit is None else f"{max_deposit}$"

        user_states[user_id] = {
            "step": "topup_enter_amount",
            "current_plan": current_plan
        }

        await update.message.reply_text(
            f"➕ إيداع جديد فوق رصيدك الحالي\n\n"
            f"📦 باقتك الحالية: {current_plan}\n"
            f"💰 رأس مالك الحالي: {current_capital}$\n"
            f"📈 رصيدك الحالي: {current_balance}$\n\n"
            f"📌 حدود باقتك الحالية:\n"
            f"من {current_plan_data['min_deposit']}$ إلى {max_text}\n\n"
            f"💵 أدخل مبلغ الإيداع الجديد:",
            reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
        )
        return

    elif text == "🏦 سحب رأس المال وإيقاف الربح":
        username = logged_in_users.get(user_id)

        if not username:
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
            return

        ensure_user_defaults(username)

        if is_user_banned(username):
            await update.message.reply_text("⛔ حسابك محظور")
            return

        if is_user_frozen(username):
            await update.message.reply_text("⚠️ حسابك مجمد ماليًا، ولا يمكن تنفيذ هذه العملية حاليًا")
            return
        
        if not is_user_verified(username):
            await update.message.reply_text(
                "⛔ لا يمكنك طلب سحب رأس المال حاليًا\n\n"
                "حسابك غير موثق حتى الآن.\n"
                "يجب توثيق الحساب أولًا قبل السماح بأي عملية سحب.\n\n"
                "اضغط على زر:\n"
                "🪪 توثيق الحساب\n\n"
                "وابدأ عملية التوثيق الآن.",
                reply_markup=main_menu_keyboard()
            )
            return

        if user_plans.get(username) in [None, "NONE"]:
            await update.message.reply_text("❌ لا توجد لديك باقة مفعلة حالياً")
            return

        if user_id in capital_withdraw_requests:
            await update.message.reply_text(
                "⏳ لديك بالفعل طلب سحب رأس المال قيد الانتظار\n"
                f"⌛ الوقت المتبقي: {get_capital_withdraw_countdown_text(username)}"
            )
            return

        update_profit(username)

        total_amount = get_user_total_balance(username)

        if total_amount <= 0:
            await update.message.reply_text("❌ لا يوجد لديك رصيد متاح لهذه العملية")
            return

        await update.message.reply_text(
            f"⚠️ تأكيد عملية سحب رأس المال وإيقاف الربح\n\n"
            f"عند التأكيد سيتم إيقاف احتساب الأرباح على رأس مالك\n"
            f"وستحصل على كامل رصيدك الحالي: {total_amount}$\n\n"
            f"هل تريد المتابعة؟",
            reply_markup=build_capital_withdraw_confirm_keyboard()
        )
        return    

    elif text == "💸 سحب الأرباح":
        username = logged_in_users.get(user_id)

        if not username:
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
            return

        ensure_user_defaults(username)

        if is_user_banned(username):
            await update.message.reply_text("⛔ حسابك محظور")
            return

        if is_user_frozen(username):
            await update.message.reply_text("⚠️ حسابك مجمد ماليًا، ولا يمكن تنفيذ السحب حاليًا")
            return
        
        if not is_user_verified(username):
            await update.message.reply_text(
                "⛔ لا يمكنك سحب الأرباح حاليًا\n\n"
                "حسابك غير موثق حتى الآن.\n"
                "يجب توثيق الحساب أولًا قبل السماح بأي عملية سحب.\n\n"
                "اضغط على زر:\n"
                "🪪 توثيق الحساب\n\n"
                "وابدأ عملية التوثيق الآن.",
                reply_markup=main_menu_keyboard()
            )
            return

        if user_plans.get(username) in [None, "NONE"]:
            await update.message.reply_text("❌ لا توجد لديك باقة مفعلة حالياً")
            return

        if user_id in pending_withdraw_requests:
            await update.message.reply_text("⏳ لديك طلب سحب قيد المراجعة بالفعل")
            return

        update_profit(username)

        plan_name = user_plans.get(username)
        capital = get_user_capital(username)
        min_withdraw = get_min_withdraw_amount(username)
        profit_only = get_user_profit_only(username)
        if not is_withdraw_available_now(username):
         await update.message.reply_text(
            f"❌ لم يحن موعد السحب بعد\n"
            f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}\n"
            f"⌛ الوقت المتبقي: {get_withdraw_countdown_text(username)}"
          )
         return

        if profit_only <= 0:
            await update.message.reply_text("❌ لا يوجد لديك أرباح متاحة للسحب حالياً")
            return

        if profit_only < min_withdraw:
            await update.message.reply_text(
                f"❌ لا يمكنك طلب السحب حالياً لأن أرباحك أقل من الحد الأدنى للسحب\n\n"
                f"💰 رأس مالك: {capital}$\n"
                f"📉 الحد الأدنى للسحب: {min_withdraw}$\n"
                f"📈 الأرباح المتاحة: {profit_only}$\n\n"
                f"📌 الحد الأدنى للسحب يساوي 20% من رأس المال"
            )
            return

        user_states[user_id] = {
            "step": "withdraw_enter_amount",
            "max_profit": profit_only,
            "plan_name": plan_name
        }

        await update.message.reply_text(
            f"💸 الأرباح المتاحة للسحب: {profit_only}$\n"
            f"💰 أدخل المبلغ الذي تريد سحبه:",
            reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
        )
        return

    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "withdraw_enter_amount":
        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
            return
        
        if not is_user_verified(username):
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "⛔ تم إلغاء عملية السحب\n\n"
                "حسابك غير موثق حتى الآن.\n"
                "يجب توثيق الحساب أولًا قبل السماح بأي عملية سحب.",
                reply_markup=main_menu_keyboard()
            )
            return

        try:
            amount = float(text)
        except:
            await update.message.reply_text("❌ أدخل مبلغًا صحيحًا بالأرقام فقط")
            return

        username = logged_in_users.get(user_id)
        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
            return

        plan_name = user_states[user_id]["plan_name"]
        max_profit = float(user_states[user_id]["max_profit"])

        capital = get_user_capital(username)
        min_withdraw = get_min_withdraw_amount(username)

        if amount <= 0:
            await update.message.reply_text("❌ يجب أن يكون مبلغ السحب أكبر من صفر")
            return

        if amount > max_profit:
            await update.message.reply_text(
                f"❌ المبلغ الذي أدخلته أكبر من الأرباح المتاحة\n\n"
                f"📈 الأرباح المتاحة: {max_profit}$"
            )
            return

        if amount < min_withdraw:
            await update.message.reply_text(
                f"❌ المبلغ الذي أدخلته أقل من الحد الأدنى للسحب\n\n"
                f"💰 رأس مالك: {capital}$\n"
                f"📉 الحد الأدنى للسحب: {min_withdraw}$\n"
                f"📥 المبلغ الذي أدخلته: {amount}$\n\n"
                f"📌 الحد الأدنى للسحب يساوي 20% من رأس المال"
            )
            return

        user_states[user_id] = {
            "step": "withdraw_enter_wallet",
            "amount": amount,
            "plan_name": plan_name,
            "max_profit": max_profit
        }

        await update.message.reply_text(
            "💼 أدخل عنوان المحفظة التي تريد السحب إليها:",
            reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
        )
        return
    
    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "withdraw_enter_wallet":

        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
            return

        if not is_user_verified(username):
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "⛔ تم إلغاء عملية السحب\n\n"
                "حسابك غير موثق حتى الآن.\n"
                "يجب توثيق الحساب أولًا قبل السماح بأي عملية سحب.",
                reply_markup=main_menu_keyboard()
            )
            return

        wallet_address = text.strip()

        if not wallet_address:
            await update.message.reply_text("❌ أدخل عنوان محفظة صحيح")
            return

        user_states[user_id] = {
            "step": "withdraw_enter_network",
            "amount": user_states[user_id]["amount"],
            "plan_name": user_states[user_id]["plan_name"],
            "wallet_address": wallet_address
        }

        await update.message.reply_text(
            "🌐 أدخل اسم الشبكة:",
            reply_markup=ReplyKeyboardMarkup([["🔙 رجوع"]], resize_keyboard=True)
        )
        return
    
    elif isinstance(user_states.get(user_id), dict) and user_states[user_id].get("step") == "withdraw_enter_network":
        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
            return
        
        if not is_user_verified(username):
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "⛔ تم إلغاء عملية السحب\n\n"
                "حسابك غير موثق حتى الآن.\n"
                "يجب توثيق الحساب أولًا قبل السماح بأي عملية سحب.",
                reply_markup=main_menu_keyboard()
            )
            return

        network_name = text.strip()

        if not network_name:
            await update.message.reply_text("❌ أدخل اسم شبكة صحيح")
            return

        amount = float(user_states[user_id]["amount"])
        plan_name = user_states[user_id]["plan_name"]
        wallet_address = user_states[user_id]["wallet_address"]

        saved_wallet = user_wallet_address.get(username, "غير محفوظ")
        saved_network = user_wallet_network.get(username, "غير محفوظ")

        wallets_match = "المحافظ متطابقة ✅" if wallet_address == saved_wallet else "المحافظ غير متطابقة ⚠️"

        pending_withdraw_requests[user_id] = {
            "username": username,
            "amount": amount,
            "plan": plan_name,
            "time": now_str(),
            "type": "profit_only",
            "withdraw_wallet_address": wallet_address,
            "withdraw_wallet_network": network_name,
            "saved_wallet_address": saved_wallet,
            "saved_wallet_network": saved_network,
            "wallets_match_result": wallets_match
        }
        save_data()

        keyboard = [
            [
                InlineKeyboardButton("✅ موافقة", callback_data=f"approve_withdraw_{user_id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_withdraw_{user_id}")
            ]
        ]
        admin_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"💸 طلب سحب أرباح جديد\n\n"
                f"👤 المستخدم: {username}\n"
                f"🆔 ID: {user_id}\n"
                f"📌 الحالة: {get_status_text(username)}\n"
                f"📦 الباقة: {plan_name}\n"
                f"💰 مبلغ السحب: {amount}$\n"
                f"🕒 وقت الطلب: {pending_withdraw_requests[user_id]['time']}\n\n"
                f"💼 عنوان المحفظة المدخل للسحب: {wallet_address}\n"
                f"🌐 الشبكة المدخلة للسحب: {network_name}\n\n"
                f"🏦 محفظة الإيداع المحفوظة: {saved_wallet}\n"
                f"🌐 شبكة الإيداع المحفوظة: {saved_network}\n\n"
                f"{wallets_match}"
            ),
            reply_markup=admin_markup
        )

        user_states.pop(user_id, None)

        await update.message.reply_text(
            "✅ تم إرسال طلب سحب الأرباح إلى الإدارة، بانتظار المراجعة",
            reply_markup=main_menu_keyboard()
        )
        return
    
    else:
        await update.message.reply_text("الرجاء اختيار أمر صحيح من القائمة أو استخدام /ana")    


# =========================
# معالجة الصور
# =========================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state = user_states.get(user_id)

    if bot_maintenance_mode and user_id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ البوت متوقف مؤقتًا للصيانة\n\n"
            "تقوم الإدارة حالياً بإجراء تحديثات على النظام.\n"
            "يرجى المحاولة لاحقًا."
        )
        return

    # اسمح للأدمن بالإرسال حتى بدون state عادي
    if not state:
        if is_admin_media_send_step(user_id):
           pass
        else:
           await update.message.reply_text("❌ لا توجد عملية حالية لاستقبال صورة")
           return
    
        # =========================
    # صور الأدمن (رد دعم / للجميع / حسب الباقة / لمستخدم محدد)
    # =========================
    if is_admin_media_send_step(user_id):
        admin_state = user_states.get(user_id)
        caption_text = update.message.caption.strip() if update.message.caption else ""

        # 1) رد على الدعم
        if admin_state.get("step") == "admin_reply_support":
            target_user_id = admin_state["target_user_id"]

            try:
                batch_id = create_admin_batch("support_reply_photo", f"user_id:{target_user_id}")

                sent_msg = await context.bot.send_photo(
                    chat_id=target_user_id,
                    photo=update.message.photo[-1].file_id,
                    caption=f"📩 رد من الدعم:\n\n{caption_text}" if caption_text else "📩 رد من الدعم"
                )

                add_message_to_batch(batch_id, target_user_id, sent_msg.message_id)

                target_username = logged_in_users.get(target_user_id)
                if not target_username:
                    for uname in users:
                        found_id = find_user_id_by_username(uname)
                        if found_id == target_user_id:
                            target_username = uname
                            break

                if target_username:
                    add_transaction(
                        target_username,
                        "admin_support_reply_photo",
                        0,
                        f"رد الأدمن بصورة: {caption_text[:80] if caption_text else 'بدون نص'}"
                    )
                    support_waiting_reply.pop(target_username, None)
                    save_data()

                user_states.pop(user_id, None)

                await update.message.reply_text(
                    "✅ تم إرسال الصورة إلى المستخدم بنجاح",
                    reply_markup=admin_keyboard()
                )

                await update.message.reply_text(
                    "يمكنك حذف آخر إرسال إذا أردت:",
                    reply_markup=build_delete_last_batch_keyboard()
                )
            except Exception as e:
                print(f"خطأ في إرسال صورة رد الدعم: {e}")
                user_states.pop(user_id, None)
                await update.message.reply_text(
                    "❌ تعذر إرسال الصورة إلى المستخدم",
                    reply_markup=admin_keyboard()
                )
            return

        # 2) رسالة خاصة لمستخدم محدد
        if admin_state.get("step") == "admin_send_private_message":
            username = admin_state["target_username"]

            if username not in users:
                user_states.pop(user_id, None)
                await update.message.reply_text("❌ المستخدم غير موجود", reply_markup=admin_keyboard())
                return

            target_user_id = get_saved_telegram_id(username)
            if not target_user_id:
                user_states.pop(user_id, None)
                await update.message.reply_text("❌ لا يوجد Telegram ID محفوظ لهذا المستخدم بعد", reply_markup=admin_keyboard())
                return

            try:
                batch_id = create_admin_batch("private_message_photo", f"user:{username}")

                sent_msg = await context.bot.send_photo(
                    chat_id=target_user_id,
                    photo=update.message.photo[-1].file_id,
                    caption=f"📨 رسالة من الإدارة:\n\n{caption_text}" if caption_text else "📨 رسالة من الإدارة"
                )

                add_message_to_batch(batch_id, target_user_id, sent_msg.message_id)

                add_transaction(
                    username,
                    "admin_private_message_photo",
                    0,
                    f"أرسل الأدمن صورة خاصة: {caption_text[:80] if caption_text else 'بدون نص'}"
                )

                user_states.pop(user_id, None)

                await update.message.reply_text(
                    f"✅ تم إرسال الصورة إلى المستخدم {username}",
                    reply_markup=admin_keyboard()
                )

                await update.message.reply_text(
                    "يمكنك حذف آخر إرسال إذا أردت:",
                    reply_markup=build_delete_last_batch_keyboard()
                )

            except Exception as e:
                print(f"خطأ في إرسال الصورة الخاصة: {e}")
                user_states.pop(user_id, None)
                await update.message.reply_text(
                    "❌ تعذر إرسال الصورة إلى المستخدم",
                    reply_markup=admin_keyboard()
                )
            return

        # 3) رسالة حسب الباقة
        if admin_state.get("step") == "admin_send_plan_message":
            plan_name = admin_state["target_plan"]
            target_users = [u for u, p in user_plans.items() if p == plan_name]
            sent_count = 0
            batch_id = create_admin_batch("plan_message_photo", f"plan:{plan_name}")

            for username in target_users:
                target_user_id = get_saved_telegram_id(username)
                if not target_user_id:
                    continue

                try:
                    sent_msg = await context.bot.send_photo(
                        chat_id=target_user_id,
                        photo=update.message.photo[-1].file_id,
                        caption=f"📨 رسالة من الإدارة لمشتركي {plan_name}:\n\n{caption_text}" if caption_text else f"📨 رسالة من الإدارة لمشتركي {plan_name}"
                    )
                    add_message_to_batch(batch_id, target_user_id, sent_msg.message_id)
                    sent_count += 1
                except:
                    pass

            user_states.pop(user_id, None)

            await update.message.reply_text(
                f"✅ تم إرسال الصورة إلى {sent_count} مستخدم من مشتركي {plan_name}",
                reply_markup=admin_keyboard()
            )

            await update.message.reply_text(
                "يمكنك حذف آخر إرسال إذا أردت:",
                reply_markup=build_delete_last_batch_keyboard()
            )
            return

        # 4) رسالة جماعية للجميع
        if admin_state.get("step") == "admin_send_broadcast":
            success = 0
            failed = 0
            batch_id = create_admin_batch("broadcast_photo", "all_users")

            for uid in chat_ids:
                try:
                    sent_msg = await context.bot.send_photo(
                        chat_id=uid,
                        photo=update.message.photo[-1].file_id,
                        caption=caption_text if caption_text else ""
                    )
                    add_message_to_batch(batch_id, uid, sent_msg.message_id)
                    success += 1
                    await asyncio.sleep(0.05)
                except:
                    failed += 1

            user_states.pop(user_id, None)

            await update.message.reply_text(
                f"✅ تم إرسال الصورة الجماعية بنجاح\n\n"
                f"📨 عدد الناجحين: {success}\n"
                f"❌ عدد الذين تعذر الإرسال لهم: {failed}",
                reply_markup=admin_keyboard()
            )

            await update.message.reply_text(
                "يمكنك حذف آخر إرسال إذا أردت:",
                reply_markup=build_delete_last_batch_keyboard()
            )
            return
        
        
        # =========================
    # توثيق الحساب بعد التسجيل - الوجه الأمامي
    # =========================
    if isinstance(state, dict) and state.get("step") == "verify_id_front":
        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("انتهت الجلسة، سجّل الدخول مجددًا عبر /k")
            return

        if verified_users.get(username, False):
            user_states.pop(user_id, None)
            await update.message.reply_text("✅ حسابك موثق بالفعل")
            return

        front_id_file_id = update.message.photo[-1].file_id

        user_states[user_id] = {
          "step": "verify_id_back",
          "full_name": state["full_name"],
           "residence": state["residence"],
          "timezone": state.get("timezone", "Europe/Vienna"),
          "front_id_file_id": front_id_file_id
            }

        await update.message.reply_text(
            "✅ تم استلام صورة الوجه الأمامي للهوية\n\n"
            "📷 الآن قم برفع صورة واضحة للوجه الخلفي للهوية الشخصية:"
        )
        return

    # =========================
    # توثيق الحساب بعد التسجيل - الوجه الخلفي ثم إرسال الطلب للأدمن
    # =========================
    if isinstance(state, dict) and state.get("step") == "verify_id_back":
        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("انتهت الجلسة، سجّل الدخول مجددًا عبر /k")
            return

        if verified_users.get(username, False):
            user_states.pop(user_id, None)
            await update.message.reply_text("✅ حسابك موثق بالفعل")
            return

        full_name = state["full_name"]
        residence = state["residence"]
        timezone = state.get("timezone", "Europe/Vienna")
        front_id_file_id = state["front_id_file_id"]
        back_id_file_id = update.message.photo[-1].file_id

        pending_verification_requests[user_id] = {
            "username": username,
            "full_name": full_name,
            "residence": residence,
            "timezone": timezone,
            "telegram_first_name": update.message.from_user.first_name,
            "telegram_username": f"@{update.message.from_user.username}" if update.message.from_user.username else "لا يوجد",
            "telegram_id": user_id,
            "front_id_file_id": front_id_file_id,
            "back_id_file_id": back_id_file_id,
            "time": now_str(),
            "type": "account_verification"
        }
        user_identity_photos[username] = {
           "front_id_file_id": front_id_file_id,
           "back_id_file_id": back_id_file_id,
           "updated_at": now_str()
         }


        save_data()

        verification_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ موافقة", callback_data=f"approve_verification_{user_id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_verification_{user_id}")
            ]
        ])

        try:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=front_id_file_id,
                caption=(
                    f"🪪 طلب توثيق حساب\n\n"
                    f"👤 اسم المستخدم: {username}\n"
                    f"👤 الاسم والكنية: {full_name}\n"
                    f"🏠 مكان الإقامة: {residence}\n"
                    f"📱 يوزر تيليغرام: {pending_verification_requests[user_id]['telegram_username']}\n"
                    f"🆔 Telegram ID: {user_id}\n"
                    f"🕒 الوقت: {now_str()}\n\n"
                    f"📷 صورة الوجه الأمامي للهوية"
                )
            )

            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=back_id_file_id,
                caption="📷 صورة الوجه الخلفي للهوية",
                reply_markup=verification_keyboard
            )

            user_states.pop(user_id, None)

            await update.message.reply_text(
                "✅ تم إرسال طلب التوثيق إلى الإدارة، بانتظار المراجعة"
            )

        except Exception as e:
            print(f"خطأ في إرسال طلب التوثيق للأدمن: {e}")
            pending_verification_requests.pop(user_id, None)
            save_data()
            await update.message.reply_text("❌ حدث خطأ أثناء إرسال طلب التوثيق، حاول مرة أخرى")

        return
    # =========================
    # صورة ضمن مراسلة الدعم
    # =========================
    if isinstance(state, dict) and state.get("step") == "support_message":
        username = logged_in_users.get(user_id)

        if not username:
            user_states.pop(user_id, None)
            await update.message.reply_text("انتهت الجلسة، سجّل الدخول مجددًا عبر /k")
            return

        if is_support_blocked(username):
            user_states.pop(user_id, None)
            await update.message.reply_text("🚫 تم منعك من مراسلة الدعم")
            return

        if support_waiting_reply.get(username, False) and not has_active_support_claim(username):
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "⏳ لا يمكنك إرسال رسالة جديدة إلى الدعم الآن\n"
                "لقد أرسلت رسالة بالفعل وبانتظار رد الإدارة"
            )
            return

        ensure_user_defaults(username)
        update_profit(username)

        tg_name = update.message.from_user.first_name if update.message.from_user.first_name else "غير متوفر"
        tg_username_text = f"@{update.message.from_user.username}" if update.message.from_user.username else "لا يوجد"
        plan = user_plans.get(username, "NONE")
        balance = get_user_total_balance(username)
        capital = get_user_capital(username)
        profit_only = get_user_profit_only(username)

        support_caption = update.message.caption.strip() if update.message.caption else "بدون نص"

        try:
            support_keyboard = build_support_reply_keyboard(user_id)

            support_caption_text = (
                f"📩 رسالة دعم جديدة\n\n"
                f"👤 الاسم داخل البوت: {username}\n"
                f"🙍 الاسم الأول: {tg_name}\n"
                f"📱 يوزر تيليغرام: {tg_username_text}\n"
                f"🆔 Telegram ID: {user_id}\n"
                f"📌 حالة الحساب: {get_status_text(username)}\n"
                f"📦 الباقة: {plan}\n"
                f"💰 رأس المال: {capital}$\n"
                f"📈 الرصيد الحالي: {balance}$\n"
                f"💵 الأرباح فقط: {profit_only}$\n"
                f"🕒 الوقت: {now_str()}\n"
                f"🖼 النوع: صورة\n\n"
                f"📝 النص المرفق:\n{support_caption}"
                        )

            await send_support_photo_to_operators(
               context=context,
               target_user_id=user_id,
               username=username,
               photo_file_id=update.message.photo[-1].file_id,
               caption_text=support_caption_text,
               reply_markup=support_keyboard
                   )

            add_transaction(username, "support_message_photo", 0, f"أرسل صورة للدعم: {support_caption[:80]}")
            support_waiting_reply[username] = True
            save_data()

            user_states.pop(user_id, None)

            await update.message.reply_text("✅ تم إرسال الصورة إلى الدعم بنجاح")
        except Exception as e:
            print(f"خطأ في إرسال صورة الدعم: {e}")
            await update.message.reply_text("❌ حدث خطأ أثناء إرسال الصورة، حاول مرة أخرى")
        return

    # =========================
    # صور التوثيق أثناء التسجيل
    # =========================
    if isinstance(state, dict) and state.get("step") == "register_id_front":
        front_file_id = update.message.photo[-1].file_id

        user_states[user_id] = {
            "step": "register_id_back",
            "username": state["username"],
            "password": state["password"],
            "residence": state["residence"],
            "full_name": state["full_name"],
            "front_id_file_id": front_file_id
        }

        await update.message.reply_text(
            "✅ تم استلام صورة الوجه الأمامي للهوية\nالآن قم برفع صورة واضحة للوجه الخلفي للهوية الشخصية:"
        )
        return

    if isinstance(state, dict) and state.get("step") == "register_id_back":
        back_file_id = update.message.photo[-1].file_id
        front_file_id = state["front_id_file_id"]

        pending_verification_requests[user_id] = {
            "username": state["username"],
            "password": state["password"],
            "residence": state["residence"],
            "full_name": state["full_name"],
            "referral": REFERRAL_DATA.get(user_id, "غير محدد"),
            "telegram_first_name": update.message.from_user.first_name,
            "telegram_username": f"@{update.message.from_user.username}" if update.message.from_user.username else "لا يوجد",
            "telegram_id": user_id,
            "front_id_file_id": front_file_id,
            "back_id_file_id": back_file_id,
            "time": now_str()
        }
        user_identity_photos[state["username"]] = {
            "front_id_file_id": front_file_id,
            "back_id_file_id": back_file_id,
            "updated_at": now_str()
         }
        save_data()

        verification_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ موافقة", callback_data=f"approve_verification_{user_id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_verification_{user_id}")
            ]
        ])

        try:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=front_file_id,
                caption=(
                    f"🆕 طلب توثيق حساب جديد\n\n"
                    f"👤 الاسم والكنية: {state['full_name']}\n"
                    f"🏠 مكان الإقامة: {state['residence']}\n"
                    f"🧾 اسم المستخدم: {state['username']}\n"
                    f"🔑 كلمة المرور: {state['password']}\n"
                    f"📱 يوزر تيليغرام: {f'@{update.message.from_user.username}' if update.message.from_user.username else 'لا يوجد'}\n"
                    f"🆔 Telegram ID: {user_id}\n"
                    f"📌 تم دعوته عن طريق: {REFERRAL_DATA.get(user_id, 'غير محدد')}\n"
                    f"🕒 الوقت: {now_str()}\n\n"
                    f"📷 صورة الوجه الأمامي للهوية"
                )
            )

            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=back_file_id,
                caption="📷 صورة الوجه الخلفي للهوية",
                reply_markup=verification_keyboard
            )

        except Exception as e:
            print(f"خطأ في إرسال طلب التوثيق للأدمن: {e}")
            pending_verification_requests.pop(user_id, None)
            save_data()
            await update.message.reply_text("❌ حدث خطأ أثناء إرسال طلب التوثيق، حاول مرة أخرى")
            return

        user_states.pop(user_id, None)

        await update.message.reply_text("✅ تم إرسال طلب التوثيق إلى الإدارة، بانتظار المراجعة")
        return

        # =========================
    # صور إثبات الإيداع وتغيير الباقة
    # =========================

    if not isinstance(state, dict) or state.get("step") not in ["send_proof", "send_plan_change_proof", "send_topup_proof"]:
        return
    username = logged_in_users.get(user_id)

    if not username:
        await update.message.reply_text("يجب تسجيل الدخول أولاً ❌\nاضغط /k")
        return
    
    if has_active_capital_withdraw_request(username):
        user_states.pop(user_id, None)
        await update.message.reply_text(
            "⛔ تم رفض إثبات الدفع\n\n"
            "لديك طلب سحب رأس مال قيد الانتظار، ولا يمكنك تنفيذ أي إيداع أو تغيير باقة حتى تتم معالجة الطلب.",
            reply_markup=main_menu_keyboard()
        )
        return

    ensure_user_defaults(username)

    if is_user_banned(username):
        await update.message.reply_text("⛔ حسابك محظور")
        user_states.pop(user_id, None)
        return

    if is_user_frozen(username):
        await update.message.reply_text("⚠️ حسابك مجمد ماليًا، ولا يمكن إرسال طلب إيداع الآن")
        user_states.pop(user_id, None)
        return

    if state.get("step") == "send_proof" and user_plans.get(username) not in [None, "NONE"]:
      await update.message.reply_text("❌ لديك باقة مفعلة بالفعل ولا يمكنك الاشتراك بأكثر من باقة")
      user_states.pop(user_id, None)
      return

    if user_id in pending_deposit_requests:
        await update.message.reply_text("⏳ لديك طلب إيداع معلق بالفعل")
        user_states.pop(user_id, None)
        return

    photo_file = await update.message.photo[-1].get_file()

    if state.get("step") == "send_plan_change_proof":
        current_plan = user_plans.get(username, "NONE")
        target_plan = state["target_plan"]
        amount = state["amount"]

        pending_deposit_requests[user_id] = {
            "username": username,
            "plan": target_plan,
            "amount": amount,
            "type": "plan_change",
            "old_plan": current_plan,
            "new_plan": target_plan,
            "time": now_str()
        }
        save_data()

        keyboard = [
             [
        InlineKeyboardButton("✅ موافقة", callback_data=f"approve_deposit_{user_id}"),
        InlineKeyboardButton("❌ رفض", callback_data=f"reject_deposit_{user_id}")
                 ],
                 [
        InlineKeyboardButton("💼 إضافة محفظة", callback_data=f"add_wallet_{user_id}")
            ]
           ]
        admin_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_file.file_id,
            caption=(
                f"📦 طلب تغيير باقة\n"
                f"👤 المستخدم: {username}\n"
                f"🆔 ID: {user_id}\n"
                f"📌 الحالة: {get_status_text(username)}\n"
                f"📦 الباقة الحالية: {current_plan}\n"
                f"📦 الباقة الجديدة: {target_plan}\n"
                f"💰 مبلغ الإيداع: {amount}$"
            ),
            reply_markup=admin_markup
        )

        user_states.pop(user_id, None)
        await update.message.reply_text("✅ تم إرسال طلب تغيير الباقة إلى الإدارة")
        return
    
    if state.get("step") == "send_topup_proof":
        current_plan = user_plans.get(username, "NONE")
        amount = round(float(state["amount"]), 2)
        current_capital = get_user_capital(username)
        final_capital = round(current_capital + amount, 2)

        pending_deposit_requests[user_id] = {
            "username": username,
            "plan": current_plan,
            "amount": amount,
            "type": "topup_deposit",
            "old_capital": current_capital,
            "final_capital": final_capital,
            "time": now_str()
        }
        save_data()

        keyboard = [
            [
                InlineKeyboardButton("✅ موافقة", callback_data=f"approve_deposit_{user_id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_deposit_{user_id}")
            ],
            [
                InlineKeyboardButton("💼 إضافة محفظة", callback_data=f"add_wallet_{user_id}")
            ]
        ]
        admin_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_file.file_id,
            caption=(
                f"➕ طلب إيداع جديد فوق الرصيد الحالي\n\n"
                f"👤 المستخدم: {username}\n"
                f"🆔 ID: {user_id}\n"
                f"📌 الحالة: {get_status_text(username)}\n"
                f"📦 الباقة الحالية: {current_plan}\n"
                f"💰 رأس المال الحالي: {current_capital}$\n"
                f"➕ مبلغ الإيداع الجديد: {amount}$\n"
                f"📈 رأس المال بعد الموافقة: {final_capital}$"
            ),
            reply_markup=admin_markup
        )

        user_states.pop(user_id, None)
        await update.message.reply_text(
            "✅ تم إرسال طلب الإيداع الجديد إلى الإدارة، بانتظار المراجعة",
            reply_markup=main_menu_keyboard()
        )
        return

    pending_deposit_requests[user_id] = {
        "username": username,
        "plan": state["plan"],
        "amount": state["amount"],
        "type": "new_deposit",
        "time": now_str()
    }    
    save_data()

    keyboard = [
    [
        InlineKeyboardButton("✅ موافقة", callback_data=f"approve_deposit_{user_id}"),
        InlineKeyboardButton("❌ رفض", callback_data=f"reject_deposit_{user_id}")
    ],
    [
        InlineKeyboardButton("💼 إضافة محفظة", callback_data=f"add_wallet_{user_id}")
    ]
]
    admin_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_file.file_id,
        caption=(
            f"📥 طلب إيداع جديد\n"
            f"👤 المستخدم: {username}\n"
            f"🆔 ID: {user_id}\n"
            f"📌 الحالة: {get_status_text(username)}\n"
            f"📦 الباقة: {state['plan']}\n"
            f"💰 المبلغ: {state['amount']}$"
        ),
        reply_markup=admin_markup
    )

    user_states.pop(user_id, None)
    await update.message.reply_text("✅ تم إرسال طلبك للإدارة")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if bot_maintenance_mode and user_id != ADMIN_ID:
        await update.message.reply_text(
            "⛔ البوت متوقف مؤقتًا للصيانة\n\n"
            "تقوم الإدارة حالياً بإجراء تحديثات على النظام.\n"
            "يرجى المحاولة لاحقًا."
        )
        return

    if not is_admin_media_send_step(user_id):
        return

    admin_state = user_states.get(user_id)
    caption_text = update.message.caption.strip() if update.message.caption else ""
    document_file_id = update.message.document.file_id

    # 1) رد على الدعم
    if admin_state.get("step") == "admin_reply_support":
        target_user_id = admin_state["target_user_id"]

        try:
            batch_id = create_admin_batch("support_reply_document", f"user_id:{target_user_id}")

            sent_msg = await context.bot.send_document(
                chat_id=target_user_id,
                document=document_file_id,
                caption=f"📩 رد من الدعم:\n\n{caption_text}" if caption_text else "📩 رد من الدعم"
            )

            add_message_to_batch(batch_id, target_user_id, sent_msg.message_id)

            target_username = logged_in_users.get(target_user_id)
            if not target_username:
                for uname in users:
                    found_id = find_user_id_by_username(uname)
                    if found_id == target_user_id:
                        target_username = uname
                        break

            if target_username:
                add_transaction(
                    target_username,
                    "admin_support_reply_document",
                    0,
                    f"رد الأدمن بملف: {caption_text[:80] if caption_text else 'بدون نص'}"
                )
                support_waiting_reply.pop(target_username, None)
                save_data()

            user_states.pop(user_id, None)

            await update.message.reply_text(
                "✅ تم إرسال الملف إلى المستخدم بنجاح",
                reply_markup=admin_keyboard()
            )

            await update.message.reply_text(
                "يمكنك حذف آخر إرسال إذا أردت:",
                reply_markup=build_delete_last_batch_keyboard()
            )

        except Exception as e:
            print(f"خطأ في إرسال ملف رد الدعم: {e}")
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "❌ تعذر إرسال الملف إلى المستخدم",
                reply_markup=admin_keyboard()
            )
        return

    # 2) رسالة خاصة لمستخدم محدد
    if admin_state.get("step") == "admin_send_private_message":
        username = admin_state["target_username"]

        if username not in users:
            user_states.pop(user_id, None)
            await update.message.reply_text("❌ المستخدم غير موجود", reply_markup=admin_keyboard())
            return

        target_user_id = get_saved_telegram_id(username)
        if not target_user_id:
            user_states.pop(user_id, None)
            await update.message.reply_text("❌ لا يوجد Telegram ID محفوظ لهذا المستخدم بعد", reply_markup=admin_keyboard())
            return

        try:
            batch_id = create_admin_batch("private_message_document", f"user:{username}")

            sent_msg = await context.bot.send_document(
                chat_id=target_user_id,
                document=document_file_id,
                caption=f"📨 رسالة من الإدارة:\n\n{caption_text}" if caption_text else "📨 رسالة من الإدارة"
            )

            add_message_to_batch(batch_id, target_user_id, sent_msg.message_id)

            add_transaction(
                username,
                "admin_private_message_document",
                0,
                f"أرسل الأدمن ملفًا خاصًا: {caption_text[:80] if caption_text else 'بدون نص'}"
            )

            user_states.pop(user_id, None)

            await update.message.reply_text(
                f"✅ تم إرسال الملف إلى المستخدم {username}",
                reply_markup=admin_keyboard()
            )

            await update.message.reply_text(
                "يمكنك حذف آخر إرسال إذا أردت:",
                reply_markup=build_delete_last_batch_keyboard()
            )

        except Exception as e:
            print(f"خطأ في إرسال الملف الخاص: {e}")
            user_states.pop(user_id, None)
            await update.message.reply_text(
                "❌ تعذر إرسال الملف إلى المستخدم",
                reply_markup=admin_keyboard()
            )
        return

    # 3) رسالة حسب الباقة
    if admin_state.get("step") == "admin_send_plan_message":
        plan_name = admin_state["target_plan"]
        target_users = [u for u, p in user_plans.items() if p == plan_name]
        sent_count = 0
        batch_id = create_admin_batch("plan_message_document", f"plan:{plan_name}")

        for username in target_users:
            target_user_id = get_saved_telegram_id(username)
            if not target_user_id:
                continue

            try:
                sent_msg = await context.bot.send_document(
                    chat_id=target_user_id,
                    document=document_file_id,
                    caption=f"📨 رسالة من الإدارة لمشتركي {plan_name}:\n\n{caption_text}" if caption_text else f"📨 رسالة من الإدارة لمشتركي {plan_name}"
                )
                add_message_to_batch(batch_id, target_user_id, sent_msg.message_id)
                sent_count += 1
            except:
                pass

        user_states.pop(user_id, None)

        await update.message.reply_text(
            f"✅ تم إرسال الملف إلى {sent_count} مستخدم من مشتركي {plan_name}",
            reply_markup=admin_keyboard()
        )

        await update.message.reply_text(
            "يمكنك حذف آخر إرسال إذا أردت:",
            reply_markup=build_delete_last_batch_keyboard()
        )
        return

    # 4) رسالة جماعية للجميع
    if admin_state.get("step") == "admin_send_broadcast":
        success = 0
        failed = 0
        batch_id = create_admin_batch("broadcast_document", "all_users")

        for uid in chat_ids:
            try:
                sent_msg = await context.bot.send_document(
                    chat_id=uid,
                    document=document_file_id,
                    caption=caption_text if caption_text else None
                )
                add_message_to_batch(batch_id, uid, sent_msg.message_id)
                success += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1

        user_states.pop(user_id, None)

        await update.message.reply_text(
            f"✅ تم إرسال الملف الجماعي بنجاح\n\n"
            f"📨 عدد الناجحين: {success}\n"
            f"❌ عدد الذين تعذر الإرسال لهم: {failed}",
            reply_markup=admin_keyboard()
        )

        await update.message.reply_text(
            "يمكنك حذف آخر إرسال إذا أردت:",
            reply_markup=build_delete_last_batch_keyboard()
        )
        return    


# =========================
# أزرار الأدمن
# =========================
def is_admin_callback(data):
    admin_prefixes = (
        "admin_",
        "approve_deposit_",
        "reject_deposit_",
        "approve_withdraw_",
        "reject_withdraw_",
        "approve_verification_",
        "reject_verification_",
        "capital_paid_",
        "filter_users_",
        "treeuser::",
        "treeback::",
        "alltreeuser::",
        "alltreeback::",
        "msg_plan_",
        "reply_support_",
        "add_wallet_",
    )

    admin_exact = {
        "admin_close_subscriptions",
        "admin_open_subscriptions",
        "admin_enable_maintenance",
        "admin_disable_maintenance",
        "back_to_admin_menu",
        "back_to_filter_menu",
        "delete_last_admin_batch",
    }

    return data in admin_exact or data.startswith(admin_prefixes)

async def handle_admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global subscriptions_open
    global bot_maintenance_mode
    global admin_last_batch_id
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        print(f"خطأ في query.answer(): {e}")
        

    data = query.data

    if data.startswith("promo_plan::"):
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
            return

        plan_name = data.split("::", 1)[1]

        if plan_name not in PLANS:
            await query.message.reply_text("❌ الباقة غير موجودة")
            return

        await query.message.reply_text(
            build_plan_features_text(plan_name),
            reply_markup=build_plan_action_keyboard(plan_name)
        )
        return

    if data == "promo_my_plan":
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
            return

        if user_plans.get(username) in [None, "NONE"]:
            await query.message.reply_text("❌ لا توجد لديك باقة مفعلة حالياً", reply_markup=main_menu_keyboard())
            return

        await query.message.reply_text(
            build_my_plan_text(username, user_id),
            reply_markup=build_my_plan_keyboard(username)
        )
        return

    if data == "data_entry_back":
        user_id = query.from_user.id

        try:
            await query.message.delete()
        except Exception as e:
            print(f"تعذر حذف رسالة تنبيه حالة الإدخال: {e}")

        await go_back_from_data_entry_state(user_id, context)
        return
    
    if bot_maintenance_mode and query.from_user.id != ADMIN_ID:
        try:
            await query.answer("⛔ البوت متوقف مؤقتًا للصيانة", show_alert=True)
        except:
            pass

        try:
            await query.message.reply_text(
                "⛔ البوت متوقف مؤقتًا للصيانة\n\n"
                "تقوم الإدارة حالياً بإجراء تحديثات على النظام.\n"
                "يرجى المحاولة لاحقًا."
            )
        except:
            pass

        return

    # =========================
    # حماية صارمة لأزرار الأدمن
    # مع السماح لموظفي الدعم بزر الرد فقط عند تفعيل النظام
    # =========================
    if is_admin_callback(data) and query.from_user.id != ADMIN_ID:
       if (
           data.startswith("reply_support_")
           and support_employees_enabled
           and is_support_employee(query.from_user.id)
            ):
           pass
       else:
           try:
               await query.answer("❌ هذا الزر خاص بالإدارة فقط", show_alert=True)
           except:
               pass

           try:
               await query.message.reply_text("❌ ليس لديك صلاحية تنفيذ هذا الإجراء")
           except:
               pass

           return
    
    if data == "admin_enable_maintenance":
        bot_maintenance_mode = True
        save_data()

        await query.edit_message_text(
            f"✅ تم إيقاف البوت للصيانة\n"
            f"🛠 حالة البوت الآن: {get_bot_maintenance_status_text()}"
        )

        success, failed = await notify_all_users(
            context,
            "⛔ البوت متوقف مؤقتًا للصيانة\n\n"
            "تقوم الإدارة حالياً بإجراء تحديثات على النظام.\n"
            "يرجى عدم تنفيذ أي عمليات الآن، وسيتم إشعاركم عند عودة البوت للعمل."
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📢 تم إرسال إشعار الصيانة للمستخدمين\n\n"
                f"✅ تم الإرسال إلى: {success}\n"
                f"❌ فشل الإرسال إلى: {failed}"
            ),
            reply_markup=admin_keyboard()
        )
        return

    if data == "admin_disable_maintenance":
        bot_maintenance_mode = False
        save_data()

        await query.edit_message_text(
            f"✅ تم تشغيل البوت من جديد\n"
            f"🛠 حالة البوت الآن: {get_bot_maintenance_status_text()}"
        )

        success, failed = await notify_all_users(
            context,
            "✅ تم تشغيل البوت من جديد\n\n"
            "يمكنكم الآن استخدام جميع خدمات البوت بشكل طبيعي."
        )

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📢 تم إرسال إشعار تشغيل البوت للمستخدمين\n\n"
                f"✅ تم الإرسال إلى: {success}\n"
                f"❌ فشل الإرسال إلى: {failed}"
            ),
            reply_markup=admin_keyboard()
        )
        return

    if data.startswith("subscribe_plan::"):
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
            return

        plan_name = data.split("::", 1)[1]

        if plan_name not in PLANS:
            await query.message.reply_text("❌ الباقة غير موجودة")
            return

        if not subscriptions_open:
            await query.message.reply_text(
                "⛔ الاشتراك في الباقات متوقف حاليًا من قبل الإدارة.\nيرجى المحاولة لاحقًا."
            )
            return

        ensure_user_defaults(username)

        if is_user_banned(username):
            await query.message.reply_text("⛔ حسابك محظور")
            return

        if is_user_frozen(username):
            await query.message.reply_text("⚠️ حسابك مجمد ماليًا، ولا يمكن طلب إيداع جديد حاليًا")
            return
        
        if has_active_capital_withdraw_request(username):
            await query.message.reply_text(
                "⛔ لا يمكنك تنفيذ أي إيداع أو اشتراك جديد حاليًا\n\n"
                "لديك طلب سحب رأس مال قيد الانتظار.\n"
                f"⌛ الوقت المتبقي: {get_capital_withdraw_countdown_text(username)}"
            )
            return

        if user_plans.get(username) not in [None, "NONE"]:
            await query.message.reply_text("❌ لديك باقة مفعلة بالفعل ولا يمكنك الاشتراك بأكثر من باقة")
            return

        if user_id in pending_deposit_requests:
            await query.message.reply_text("⏳ لديك طلب إيداع معلق بالفعل بانتظار مراجعة الإدارة")
            return

        user_states[user_id] = {
            "step": "enter_amount",
            "plan": plan_name
        }

        plan = PLANS[plan_name]

        max_text = "بدون حد أعلى" if plan["max_deposit"] is None else f"{plan['max_deposit']}$"

        await query.message.reply_text(
           f"📦 اخترت {plan_name}\n"
           f"💰 أدخل مبلغ الإيداع ابتداءً من {plan['min_deposit']}$ وحتى {max_text}"
             )
        return

    if data == "plan_details_back_home":
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="🏠 تم الرجوع إلى الصفحة الرئيسية",
            reply_markup=main_menu_keyboard()
        )
        return

    # =========================
    # شجرة جميع المستخدمين
    # =========================
    if data.startswith("alltreeuser::"):
        parts = data.split("::", 2)
        if len(parts) != 3:
            await query.message.reply_text("❌ بيانات الشجرة غير صحيحة")
            return

        current_view_id = parts[1]
        username = parts[2]

        current_view = get_tree_view(current_view_id)
        if not current_view:
            await query.message.reply_text("❌ انتهت صلاحية هذه الشاشة، افتح شجرة المستخدمين من جديد")
            return

        children = get_all_direct_invited_users(username)
        children_count = len(children)

        if not children:
            await query.message.reply_text(
                f"📂 المستخدم: {username}\n"
                f"📌 الحالة: {get_status_badge(username)}\n"
                f"👥 عدد الأبناء المباشرين: 0\n\n"
                f"📭 لا يوجد أبناء لهذا المستخدم"
            )
            return

        child_view_id = create_tree_view(
            view_type="all_users_tree",
            usernames=children,
            title=(
                f"📂 أبناء المستخدم: {username}\n"
                f"📌 الحالة: {get_status_badge(username)}\n"
                f"👥 عدد الأبناء المباشرين: {children_count}"
            ),
            status=None,
            parent_username=username,
            back_view_id=current_view_id
        )
        cleanup_tree_views()

        await query.message.reply_text(
            (
                f"📂 أبناء المستخدم: {username}\n"
                f"📌 الحالة: {get_status_badge(username)}\n"
                f"👥 عدد الأبناء المباشرين: {children_count}"
            ),
            reply_markup=build_all_users_tree_keyboard(child_view_id)
        )
        return

    if data.startswith("alltreeback::"):
        parts = data.split("::", 1)
        if len(parts) != 2:
            await query.message.reply_text("❌ بيانات الرجوع غير صحيحة")
            return

        back_view_id = parts[1]
        back_view = get_tree_view(back_view_id)

        if not back_view:
            await query.message.reply_text("❌ انتهت صلاحية شاشة الرجوع، افتح شجرة المستخدمين من جديد")
            return

        await query.message.reply_text(
            back_view["title"],
            reply_markup=build_all_users_tree_keyboard(back_view_id)
        )
        return

    if data == "back_to_admin_menu":
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="🛠 العودة إلى لوحة الأدمن",
            reply_markup=admin_keyboard()
        )
        return
    
    if data.startswith("admin_confirm_delete_user::"):
        parts = data.split("::", 1)
        if len(parts) != 2:
            await query.message.reply_text("❌ بيانات الحذف غير صحيحة")
            return

        username = parts[1]

        if username not in users:
            await query.message.reply_text("❌ المستخدم غير موجود أو تم حذفه بالفعل")
            return

        target_user_id = find_user_id_by_username(username)

        full_name = user_full_name.get(username, "غير متوفر")
        residence = user_residence.get(username, "غير متوفر")
        plan = user_plans.get(username, "NONE")
        balance = round(float(user_balance.get(username, 0)), 2)
        capital = round(float(user_deposits.get(username, 0)), 2)
        profit_only = round(balance - capital, 2)
        if profit_only < 0:
            profit_only = 0

        verification_text = "موثق ✅" if verified_users.get(username, False) else "غير موثق ❌"
        status_text = get_status_text(username)

        telegram_first_name = "غير متوفر"
        telegram_username = "لا يوجد"

        if target_user_id:
            for uid, uname in logged_in_users.items():
                if uname == username:
                    target_user_id = uid
                    break

        pending_requests_summary = get_pending_requests_summary_for_admin(target_user_id) if target_user_id else "لا توجد عليه طلبات معلقة وقت الحذف."

        deleted_account_entry = {
            "username": username,
            "telegram_id": target_user_id if target_user_id else "غير متوفر",
            "telegram_first_name": telegram_first_name,
            "telegram_username": telegram_username,
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

        add_deleted_account_log(deleted_account_entry)

        if target_user_id is None:
            # إذا لم نجد Telegram ID نحذف يدويًا بالاعتماد على username
            users.pop(username, None)
            user_plans.pop(username, None)
            user_balance.pop(username, None)
            transactions.pop(username, None)
            user_deposits.pop(username, None)
            user_last_profit.pop(username, None)
            user_withdraw_logs.pop(username, None)
            user_deposit_logs.pop(username, None)
            user_statuses.pop(username, None)
            support_blocked_users.pop(username, None)
            user_first_deposit_time.pop(username, None)
            user_last_withdraw_time.pop(username, None)
            user_telegram_ids.pop(username, None)
            user_residence.pop(username, None)
            user_full_name.pop(username, None)
            verified_users.pop(username, None)
            user_referrer.pop(username, None)
            referral_bonus_paid.pop(username, None)
            stopped_profit_users.pop(username, None)
            support_waiting_reply.pop(username, None)
            support_claims.pop(username, None)
            support_message_copies.pop(str(user_id), None)
            manual_withdraw_open.pop(username, None)
            user_created_time.pop(username, None)
            user_wallet_address.pop(username, None)
            user_wallet_network.pop(username, None)

            for invited_username, referrer_username in list(user_referrer.items()):
                if referrer_username == username:
                    user_referrer.pop(invited_username, None)

            save_users()
            save_data()
        else:
            delete_user_completely(target_user_id, username)

        try:
            if target_user_id:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="❌ تم حذف حسابك نهائيًا بواسطة الإدارة"
                )
        except:
            pass

        await query.edit_message_text(
            f"✅ تم حذف المستخدم {username} نهائيًا مع جميع بياناته"
        )
        return

    if data.startswith("admin_cancel_delete_user::"):
        parts = data.split("::", 1)
        if len(parts) != 2:
            await query.message.reply_text("❌ بيانات الإلغاء غير صحيحة")
            return

        username = parts[1]
        await query.edit_message_text(f"✅ تم إلغاء حذف المستخدم {username}")
        return

    # =========================

    if data == "cancel_delete_my_account":
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        try:
            await query.message.delete()
        except Exception as e:
            print(f"تعذر حذف رسالة تأكيد حذف الحساب: {e}")

        if username:
            await context.bot.send_message(
                chat_id=user_id,
                text="🏠 تم الرجوع إلى الصفحة الرئيسية",
                reply_markup=main_menu_keyboard()
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="اختر خيار:",
                reply_markup=auth_keyboard()
            )

        return

    if data == "confirm_delete_my_account":
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.edit_message_text("❌ تعذر العثور على جلسة الحساب، يرجى تسجيل الدخول مجددًا")
            return

        # أخذ نسخة من بيانات المستخدم قبل الحذف
        full_name = user_full_name.get(username, "غير متوفر")
        residence = user_residence.get(username, "غير متوفر")
        plan = user_plans.get(username, "NONE")
        balance = round(float(user_balance.get(username, 0)), 2)
        capital = round(float(user_deposits.get(username, 0)), 2)
        profit_only = round(balance - capital, 2)
        if profit_only < 0:
            profit_only = 0

        verification_text = "موثق ✅" if verified_users.get(username, False) else "غير موثق ❌"
        status_text = get_status_text(username)
        telegram_first_name = query.from_user.first_name if query.from_user.first_name else "غير متوفر"
        telegram_username = f"@{query.from_user.username}" if query.from_user.username else "لا يوجد"

        pending_requests_summary = get_pending_requests_summary_for_admin(user_id)

        deleted_account_entry = {
            "username": username,
            "telegram_id": user_id,
            "telegram_first_name": telegram_first_name,
            "telegram_username": telegram_username,
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

        add_deleted_account_log(deleted_account_entry)

        delete_user_completely(user_id, username)

        await query.message.delete()

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "💙 تم حذف حسابك وجميع بياناتك من البوت بنجاح.\n\n"
                "نشكر لك الوقت الذي قضيته معنا، "
                "ونسعد دائمًا بخدمتك متى رغبت.\n\n"
                "نتمنى لك كل التوفيق، "
                "ونتمنى عودتك إلينا مجددًا 🌷"
            ),
            reply_markup=auth_keyboard()
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🗑 قام مستخدم بحذف حسابه نهائيًا\n\n"
                    f"👤 الاسم داخل البوت: {username}\n"
                    f"🙍 الاسم الأول في تيليغرام: {telegram_first_name}\n"
                    f"📱 يوزر تيليغرام: {telegram_username}\n"
                    f"🆔 Telegram ID: {user_id}\n"
                    f"👤 الاسم والكنية: {full_name}\n"
                    f"🏠 مكان الإقامة: {residence}\n"
                    f"🪪 حالة التوثيق: {verification_text}\n"
                    f"📌 حالة الحساب قبل الحذف: {status_text}\n"
                    f"📦 الباقة قبل الحذف: {plan}\n"
                    f"💰 رأس المال قبل الحذف: {capital}$\n"
                    f"📈 الرصيد قبل الحذف: {balance}$\n"
                    f"💵 الأرباح فقط قبل الحذف: {profit_only}$\n"
                    f"🕒 وقت الحذف: {now_str()}\n\n"
                    f"📋 الطلبات المعلقة وقت الحذف:\n{pending_requests_summary}"
                )
            )
        except Exception as e:
            print(f"خطأ في إرسال إشعار حذف الحساب للأدمن: {e}")

        return

    

    if data == "delete_last_admin_batch":
        
        if not admin_last_batch_id:
            await query.edit_message_text("❌ لا يوجد آخر إرسال محفوظ يمكن حذفه حالياً")
            return

        batch = admin_sent_batches.get(admin_last_batch_id)
        if not batch:
            admin_last_batch_id = None
            save_data()
            await query.edit_message_text("❌ تعذر العثور على بيانات آخر دفعة إرسال")
            return

        deleted_count = 0
        failed_count = 0

        batch_type = batch.get("type", "unknown")
        target_label = batch.get("target", "unknown")
        batch_messages = batch.get("messages", [])

        readable_type = get_batch_type_text(batch_type)
        readable_target = get_batch_target_text(target_label)

        for item in batch_messages:
            chat_id = item.get("chat_id")
            message_id = item.get("message_id")

            if not chat_id or not message_id:
                failed_count += 1
                continue

            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                deleted_count += 1
            except Exception as e:
                print(f"تعذر حذف رسالة من الدفعة الأخيرة | chat_id={chat_id}, message_id={message_id}, error={e}")
                failed_count += 1

        admin_sent_batches.pop(admin_last_batch_id, None)
        admin_last_batch_id = None

        # تنظيف الدفعات الفارغة أو التالفة القديمة
        invalid_batch_ids = []
        for batch_id, batch_data in admin_sent_batches.items():
            if not isinstance(batch_data, dict):
                invalid_batch_ids.append(batch_id)
                continue

            msgs = batch_data.get("messages", [])
            if not isinstance(msgs, list):
                invalid_batch_ids.append(batch_id)

        for batch_id in invalid_batch_ids:
            admin_sent_batches.pop(batch_id, None)

        save_data()

        total_count = len(batch_messages)

        result_lines = [
            "🗑 تم تنفيذ حذف آخر دفعة إرسال",
            "",
            f"📌 نوع الإرسال: {readable_type}",
            f"🎯 الهدف: {readable_target}",
            f"📨 عدد الرسائل المسجلة في الدفعة: {total_count}",
            f"✅ تم حذفها بنجاح: {deleted_count}",
            f"❌ تعذر حذفها: {failed_count}",
        ]

        if failed_count > 0:
            result_lines.extend([
                "",
                "ℹ️ ملاحظة:",
                "قد يتعذر حذف بعض الرسائل بسبب حذفها مسبقًا، أو قيود تيليغرام، أو لأن الرسالة لم تعد متاحة."
            ])

        await query.edit_message_text("\n".join(result_lines))
        return

    if data == "confirm_capital_withdraw":
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.edit_message_text("يجب تسجيل الدخول أولاً ❌")
            return
        
        if not is_user_verified(username):
            await query.edit_message_text(
                "⛔ لا يمكنك تأكيد طلب سحب رأس المال\n\n"
                "حسابك غير موثق حتى الآن.\n"
                "يجب توثيق الحساب أولًا قبل السماح بأي عملية سحب.\n\n"
                "اضغط على زر 🪪 توثيق الحساب من لوحة المستخدم وابدأ التوثيق."
            )
            return

        if user_id in capital_withdraw_requests:
            await query.edit_message_text(
                f"⏳ لديك بالفعل طلب سحب رأس المال قيد الانتظار\n"
                f"⌛ الوقت المتبقي: {get_capital_withdraw_countdown_text(username)}"
            )
            return

        update_profit(username)

        total_amount = get_user_total_balance(username)
        now = time.time()
        due_time = now + (10 * 86400)

        stopped_profit_users[username] = True
        saved_wallet = user_wallet_address.get(username, "غير محفوظة")
        saved_network = user_wallet_network.get(username, "غير محفوظة")

        capital_withdraw_requests[user_id] = {
         "username": username,
         "amount": round(total_amount, 2),
         "request_time": now,
         "due_time": due_time,
         "wallet": saved_wallet,
         "network": saved_network,
         "admin_notified": False
            }

        add_transaction(
            username,
            "capital_withdraw_requested",
            total_amount,
            "طلب سحب رأس المال وإيقاف الربح"
        )

        save_data()

        await query.edit_message_text(
            text=(
                f"✅ تم إيقاف احتساب أي أرباح على رأس مالك\n"
                f"💰 ستحصل على: {round(total_amount, 2)}$\n"
                f"⌛ مدة الانتظار حتى تنفيذ الطلب: 10 أيام\n"
                f"🕒 العد التنازلي: {get_capital_withdraw_countdown_text(username)}"
            )
        )
        return

    if data == "cancel_capital_withdraw":
        await query.message.delete()

        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="🏠 تم إلغاء العملية والعودة إلى الصفحة الرئيسية",
            reply_markup=main_menu_keyboard()
        )
        return
    
    if data.startswith("capital_paid_"):
        user_id = int(data.split("_")[-1])
        request = capital_withdraw_requests.get(user_id)

        if not request:
            await query.edit_message_text("❌ طلب سحب رأس المال غير موجود أو تمت معالجته بالفعل")
            return

        username = request.get("username")
        amount = round(float(request.get("amount", 0)), 2)

        if username not in users:
            capital_withdraw_requests.pop(user_id, None)
            save_data()
            await query.edit_message_text("❌ المستخدم غير موجود، تم حذف الطلب")
            return
        
        if not is_user_verified(username):
            await query.edit_message_text(
                "❌ لا يمكن تأكيد دفع سحب رأس المال\n\n"
                "حساب المستخدم غير موثق حتى الآن.\n"
                "يجب توثيق الحساب قبل تنفيذ أي عملية سحب."
            )
            return

        # تصفير البيانات المالية
        user_balance[username] = 0
        user_deposits[username] = 0

        # إزالة الباقة
        user_plans[username] = "NONE"

        # إزالة أوقات الربح والسحب السابقة
        user_last_profit[username] = time.time()
        user_first_deposit_time.pop(username, None)
        user_last_withdraw_time.pop(username, None)

        # إعادة تفعيل الربح في حال اشترك لاحقاً من جديد
        stopped_profit_users.pop(username, None)

        # حذف طلب سحب رأس المال
        capital_withdraw_requests.pop(user_id, None)

        # تسجيل العملية
        add_transaction(
            username,
            "capital_withdraw_paid",
            amount,
            "تم دفع سحب رأس المال وإغلاق الباقة بواسطة الأدمن"
        )

        save_data()

        # إشعار المستخدم
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ تم تنفيذ طلب سحب رأس المال بنجاح\n\n"
                    f"💰 المبلغ المدفوع: {amount}$\n"
                    f"📦 تم إغلاق باقتك الحالية\n"
                    f"📉 تم إيقاف الباقة وتصفير الرصيد\n\n"
                    f"يمكنك الاشتراك من جديد متى أردت"
                ),
                reply_markup=main_menu_keyboard()
            )
        except Exception as e:
            print(f"خطأ في إرسال إشعار دفع سحب رأس المال للمستخدم: {e}")

        await query.edit_message_text(
            text=(
                f"✅ تم تأكيد دفع سحب رأس المال للمستخدم {username}\n\n"
                f"💰 المبلغ: {amount}$\n"
                f"📦 تم حذف الباقة\n"
                f"📉 تم تصفير الرصيد ورأس المال\n"
                f"🗑 تم إغلاق الطلب بنجاح"
            )
        )
        return
 
    if data.startswith("approve_verification_"):
       target_user_id = int(data.split("_")[-1])
       request = pending_verification_requests.get(target_user_id)

       if not request:
        await query.edit_message_caption(caption="❌ طلب التوثيق غير موجود")
        return

       username = request["username"]
       full_name = request["full_name"]
       residence = request["residence"]
       timezone = request.get("timezone", "Europe/Vienna")

       if username not in users:
        pending_verification_requests.pop(target_user_id, None)
        save_data()
        await query.edit_message_caption(caption="❌ المستخدم غير موجود")
        return

       user_full_name[username] = full_name
       user_residence[username] = residence
       user_timezone[username] = timezone
       verified_users[username] = True

       pending_verification_requests.pop(target_user_id, None)
       save_data()

       try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                "✅ تم توثيق حسابك بنجاح\n\n"
                f"👤 الاسم والكنية: {full_name}\n"
                f"🏠 مكان الإقامة: {residence}"
            )
        )
       except Exception as e:
        print(f"خطأ في إرسال رسالة الموافقة للمستخدم: {e}")

       await query.edit_message_caption(
        caption=(
            f"✅ تمت الموافقة على توثيق الحساب\n\n"
            f"👤 اسم المستخدم: {username}\n"
            f"👤 الاسم والكنية: {full_name}\n"
            f"🏠 مكان الإقامة: {residence}"
        )
       )
       return

    if data.startswith("reject_verification_"):
       target_user_id = int(data.split("_")[-1])
       request = pending_verification_requests.get(target_user_id)

       if request:
        pending_verification_requests.pop(target_user_id, None)
        save_data()

       try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="❌ تم رفض طلب توثيق الحساب، يرجى إعادة المحاولة بصورة أوضح وبيانات صحيحة."
        )
       except Exception as e:
        print(f"خطأ في إرسال رسالة الرفض للمستخدم: {e}")

       await query.edit_message_caption(caption="❌ تم رفض طلب التوثيق")
       return

    if data == "admin_close_subscriptions":
        subscriptions_open = False
        save_data()

        await query.edit_message_text(
            f"✅ تم تحديث الحالة\n📌 الاشتراك الآن: {get_subscriptions_status_text()}"
        )
        return
    
    if data == "admin_open_subscriptions":
        subscriptions_open = True
        save_data()

        await query.edit_message_text(
            f"✅ تم تحديث الحالة\n📌 الاشتراك الآن: {get_subscriptions_status_text()}"
        )
        return
    
    if data == "filter_users_active":
       status = "active"
       root_users = get_root_users_by_status(status)

       if not root_users:
           await query.message.reply_text("📭 لا يوجد مستخدمون نشطون بدون دعوة")
           return

       view_id = create_tree_view(
        view_type="status_tree",
        status=status,
        usernames=root_users,
        title="✅ جذور شجرة المستخدمين النشطين:",
        parent_username=None,
        back_view_id=None
          )
       cleanup_tree_views()

       await query.message.reply_text(
           "✅ جذور شجرة المستخدمين النشطين:\nاختر مستخدمًا للتوسع في الشجرة:",
           reply_markup=build_user_tree_keyboard(view_id)
       )
       return

    if data == "filter_users_frozen":
       status = "frozen"
       root_users = get_root_users_by_status(status)

       if not root_users:
           await query.message.reply_text("📭 لا يوجد مستخدمون مجمدون بدون دعوة")
           return

       view_id = create_tree_view(
        view_type="status_tree",
        status=status,
        usernames=root_users,
        title="⚠️ جذور شجرة المستخدمين المجمدين:",
        parent_username=None,
        back_view_id=None
          )
       cleanup_tree_views()

       await query.message.reply_text(
           "⚠️ جذور شجرة المستخدمين المجمدين:\nاختر مستخدمًا للتوسع في الشجرة:",
           reply_markup=build_user_tree_keyboard(view_id)
       )
       return

    if data == "filter_users_banned":
       status = "banned"
       root_users = get_root_users_by_status(status)

       if not root_users:
           await query.message.reply_text("📭 لا يوجد مستخدمون محظورون بدون دعوة")
           return

       view_id = create_tree_view(
        view_type="status_tree",
        status=status,
        usernames=root_users,
        title="⛔ جذور شجرة المستخدمين المحظورين:",
        parent_username=None,
        back_view_id=None
          )
       cleanup_tree_views()

       await query.message.reply_text(
           "⛔ جذور شجرة المستخدمين المحظورين:\nاختر مستخدمًا للتوسع في الشجرة:",
           reply_markup=build_user_tree_keyboard(view_id)
       )
       return

    if data.startswith("treeuser::"):
       parts = data.split("::", 2)
       if len(parts) != 3:
           await query.message.reply_text("❌ بيانات الشجرة غير صحيحة")
           return

       view_id = parts[1]
       username = parts[2]

       current_view = get_tree_view(view_id)
       if not current_view:
           await query.message.reply_text("❌ انتهت صلاحية هذه الشاشة، افتح الفلترة من جديد")
           return

       status = current_view["status"]
       children = get_direct_invited_users_by_status(username, status)

       title_map = {
           "active": "النشطين",
           "frozen": "المجمدين",
           "banned": "المحظورين"
       }
       title = title_map.get(status, status)

       if not children:
           await query.message.reply_text(
               f"📭 المستخدم {username} لا يملك مدعوين مباشرين ضمن فئة {title}"
           )
           return

       child_view_id = create_tree_view(
        view_type="status_tree",
        status=status,
        usernames=children,
        title=f"📂 المدعوون المباشرون عن طريق {username}",
        parent_username=username,
        back_view_id=view_id
            )
       cleanup_tree_views()

       await query.message.reply_text(
           f"📂 المدعوون المباشرون عن طريق {username} ضمن فئة {title}:",
           reply_markup=build_user_tree_keyboard(child_view_id)
       )
       return   
    
    if data.startswith("treeback::"):
       parts = data.split("::", 1)
       if len(parts) != 2:
           await query.message.reply_text("❌ بيانات الرجوع غير صحيحة")
           return

       back_view_id = parts[1]
       back_view = get_tree_view(back_view_id)

       if not back_view:
           await query.message.reply_text("❌ انتهت صلاحية شاشة الرجوع، افتح الفلترة من جديد")
           return

       await query.message.reply_text(
           back_view["title"],
           reply_markup=build_user_tree_keyboard(back_view_id)
       )
       return
      
    if data == "back_to_filter_menu":
        active_count = sum(1 for u in users if get_user_status(u) == "active")
        frozen_count = sum(1 for u in users if get_user_status(u) == "frozen")
        banned_count = sum(1 for u in users if get_user_status(u) == "banned")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ النشطون ({active_count})", callback_data="filter_users_active")],
            [InlineKeyboardButton(f"⚠️ المجمدون ({frozen_count})", callback_data="filter_users_frozen")],
            [InlineKeyboardButton(f"⛔ المحظورون ({banned_count})", callback_data="filter_users_banned")]
        ])

        await query.message.reply_text(
            "اختر نوع المستخدمين الذين تريد عرضهم:",
            reply_markup=keyboard
        )
        return

    if data == "profit_reinvest":
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.message.reply_text("يجب تسجيل الدخول أولاً ❌", reply_markup=auth_keyboard())
            return

        ensure_user_defaults(username)
        update_profit(username)

        if user_plans.get(username) in [None, "NONE"]:
            await query.message.reply_text("❌ لا توجد لديك باقة مفعلة حالياً")
            return

        if is_user_banned(username):
            await query.message.reply_text("⛔ حسابك محظور")
            return

        if is_user_frozen(username):
            await query.message.reply_text("⚠️ حسابك مجمد ماليًا، ولا يمكن تنفيذ هذه العملية حاليًا")
            return

        if not is_profit_reinvest_available(username):
            await query.message.reply_text(
                "❌ خيار استثمار الأرباح غير متاح حاليًا\n\n"
                "يظهر هذا الخيار لمدة ساعة واحدة فقط من لحظة إتاحة السحب."
            )
            return

        capital = get_user_capital(username)
        profit_only = get_user_profit_only(username)
        new_capital = round(capital + profit_only, 2)

        if profit_only <= 0:
            await query.message.reply_text("❌ لا توجد أرباح متاحة للاستثمار حاليًا")
            return

        await query.message.reply_text(
            f"🔁 تأكيد استثمار الأرباح\n\n"
            f"سيتم إضافة الأرباح المتاحة للسحب إلى رأس مالك.\n\n"
            f"💰 رأس المال الحالي: {capital}$\n"
            f"💵 الأرباح المتاحة للسحب: {profit_only}$\n"
            f"📈 رأس المال الجديد بعد الاستثمار: {new_capital}$\n\n"
            f"⏳ هذا الخيار متاح لمدة:\n"
            f"{get_profit_reinvest_countdown_text(username)}\n\n"
            f"هل تريد المتابعة؟",
            reply_markup=build_profit_reinvest_confirm_keyboard()
        )
        return

    if data == "cancel_profit_reinvest":
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        try:
            await query.message.delete()
        except:
            pass

        await context.bot.send_message(
            chat_id=user_id,
            text="🏠 تم الرجوع إلى باقتك",
            reply_markup=main_menu_keyboard()
        )

        if username:
            await context.bot.send_message(
                chat_id=user_id,
                text=build_my_plan_text(username, user_id),
                reply_markup=build_my_plan_keyboard(username)
            )
        return

    if data == "confirm_profit_reinvest":
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.edit_message_text("يجب تسجيل الدخول أولاً ❌")
            return

        ensure_user_defaults(username)
        update_profit(username)

        if user_plans.get(username) in [None, "NONE"]:
            await query.edit_message_text("❌ لا توجد لديك باقة مفعلة حالياً")
            return

        if is_user_banned(username) or is_user_frozen(username):
            await query.edit_message_text("❌ حالة الحساب لا تسمح بتنفيذ العملية")
            return

        if not is_profit_reinvest_available(username):
            await query.edit_message_text(
                "❌ انتهت مدة إتاحة استثمار الأرباح\n\n"
                "هذا الخيار متاح لمدة ساعة واحدة فقط من لحظة إتاحة السحب."
            )
            return

        old_capital = get_user_capital(username)
        current_balance = get_user_total_balance(username)
        profit_only = get_user_profit_only(username)

        if profit_only <= 0:
            await query.edit_message_text("❌ لا توجد أرباح متاحة للاستثمار حاليًا")
            return

        new_capital = round(old_capital + profit_only, 2)

        user_deposits[username] = new_capital
        user_balance[username] = current_balance

        user_last_profit[username] = time.time()
        user_last_withdraw_time[username] = time.time()

        manual_withdraw_open.pop(username, None)
        pending_profit_capital_activation.pop(username, None)

        user_deposit_logs.setdefault(username, []).append({
            "amount": profit_only,
            "time": now_str(),
            "status": "approved",
            "type": "profit_reinvest",
            "note": f"تم استثمار الأرباح وإضافتها إلى رأس المال | من {old_capital}$ إلى {new_capital}$"
        })

        add_transaction(
            username,
            "profit_reinvest",
            profit_only,
            f"تم استثمار الأرباح وإضافتها إلى رأس المال | رأس المال من {old_capital}$ إلى {new_capital}$"
        )

        save_data()

        await query.edit_message_text(
            f"✅ تم استثمار الأرباح بنجاح\n\n"
            f"💰 رأس المال السابق: {old_capital}$\n"
            f"💵 الأرباح المستثمرة: {profit_only}$\n"
            f"📈 رأس المال الجديد: {new_capital}$\n\n"
            f"⏰ تم بدء دورة سحب جديدة من الآن.\n"
            f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}"
        )
        return 

    if data == "refresh_my_countdown":
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            try:
                await query.edit_message_text("يجب تسجيل الدخول أولاً ❌")
            except:
                pass
            return

        text_message = build_my_plan_text(username, user_id)

        try:
            await query.edit_message_text(
                text=text_message,
                reply_markup=build_my_plan_keyboard(username)
            )
        except Exception as e:
            if "Message is not modified" not in str(e):
                print(f"خطأ في تحديث العد التنازلي: {e}")

        return
    #===
    if data == "change_current_plan":
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.edit_message_text("يجب تسجيل الدخول أولاً ❌")
            return

        if has_active_capital_withdraw_request(username):
            await query.edit_message_text(
                "⛔ لا يمكنك تغيير الباقة حاليًا\n\n"
                "لديك طلب سحب رأس مال قيد الانتظار.\n"
                f"⌛ الوقت المتبقي: {get_capital_withdraw_countdown_text(username)}\n\n"
                "بعد تنفيذ طلب سحب رأس المال وإغلاق الباقة، يمكنك الاشتراك من جديد."
            )
            return

        current_plan = user_plans.get(username)

        if current_plan in [None, "NONE"]:
            await query.edit_message_text("❌ لا توجد لديك باقة مفعلة حالياً")
            return

        await query.edit_message_text(
             text="🚀 اختر الباقة الأعلى للترقية:",
             reply_markup=build_change_plan_keyboard(current_plan)
              )
        return

    if data == "change_plan_back_home":
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="🏠 تم الرجوع إلى الصفحة الرئيسية",
            reply_markup=main_menu_keyboard()
        )
        return
    
    if data == "no_upgrade_available":
        await query.answer("لا توجد باقات أعلى من باقتك الحالية", show_alert=True)
        return

    if data.startswith("select_new_plan::"):
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.edit_message_text("يجب تسجيل الدخول أولاً ❌")
            return
        
        if has_active_capital_withdraw_request(username):
            await query.edit_message_text(
                "⛔ لا يمكنك تغيير الباقة حاليًا\n\n"
                "لديك طلب سحب رأس مال قيد الانتظار.\n"
                f"⌛ الوقت المتبقي: {get_capital_withdraw_countdown_text(username)}"
            )
            return

        target_plan = data.split("::", 1)[1]
        current_plan = user_plans.get(username)

        if PLAN_LEVELS.get(target_plan, 0) <= PLAN_LEVELS.get(current_plan, 0):
            await query.edit_message_text("❌ يمكنك فقط الترقية إلى باقة أعلى")
            return

        if target_plan == current_plan:
            await query.edit_message_text("❌ هذه هي باقتك الحالية بالفعل")
            return

        required_amount = get_required_upgrade_amount(username, target_plan)
        current_balance = get_user_total_balance(username)
        current_capital = get_user_capital(username)

        # إذا كان الرصيد الحالي يكفي للترقية، تتم مباشرة بدون إيداع جديد
        if current_balance >= PLANS[target_plan]["min_deposit"]:
            old_plan = current_plan

            # تحويل الرصيد الحالي إلى رأس مال جديد داخل الباقة الجديدة
            user_plans[username] = target_plan
            user_deposits[username] = round(current_balance, 2)
            user_balance[username] = round(current_balance, 2)

            # إعادة ضبط توقيت الربح والسحب من لحظة الترقية
            user_last_profit[username] = time.time()
            user_last_withdraw_time[username] = time.time()

            add_transaction(
                username,
                "plan_change_auto_by_balance",
                0,
                f"تمت الترقية تلقائيًا من {old_plan} إلى {target_plan} اعتمادًا على الرصيد الحالي {current_balance}$"
            )

            save_data()

            await query.edit_message_text(
                text=(
                    f"✅ تمت ترقية باقتك بنجاح مباشرة بدون إيداع جديد\n\n"
                    f"📦 الباقة القديمة: {old_plan}\n"
                    f"📦 الباقة الجديدة: {target_plan}\n"
                    f"💰 الرصيد المعتمد للترقية: {current_balance}$\n"
                    f"💼 رأس المال الجديد: {current_balance}$\n"
                    f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}"
                )
            )

            return

        # إذا لم يكن الرصيد الحالي كافيًا، ننتقل إلى الإيداع كالمعتاد
        user_states[user_id] = {
            "step": "plan_change_selected",
            "target_plan": target_plan
        }

        await query.edit_message_text(
            text=build_plan_features_text(target_plan)
        )

        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"💰 رصيدك الحالي: {current_balance}$\n"
                f"💼 رأس مالك الحالي: {current_capital}$\n\n"
                f"يجب عليك إيداع {required_amount}$ على الأقل حتى تتمكن من الاشتراك بباقة {target_plan}"
            ),
            reply_markup=build_plan_change_confirm_keyboard(target_plan)
        )
        return

    if data.startswith("start_plan_change_deposit::"):
        user_id = query.from_user.id
        username = logged_in_users.get(user_id)

        if not username:
            await query.edit_message_text("يجب تسجيل الدخول أولاً ❌")
            return
        
        if has_active_capital_withdraw_request(username):
            await query.edit_message_text(
                "⛔ لا يمكنك تنفيذ إيداع لتغيير الباقة حاليًا\n\n"
                "لديك طلب سحب رأس مال قيد الانتظار.\n"
                f"⌛ الوقت المتبقي: {get_capital_withdraw_countdown_text(username)}"
            )
            return

        target_plan = data.split("::", 1)[1]

        required_amount = get_required_upgrade_amount(username, target_plan)

        user_states[user_id] = {
            "step": "plan_change_enter_amount",
            "target_plan": target_plan,
            "required_amount": required_amount
        }

        await context.bot.send_message(
            chat_id=user_id,
            text=f"💰 أدخل مبلغ الإيداع المطلوب لتغيير الباقة إلى {target_plan}\nالحد الأدنى المطلوب: {required_amount}$"
        )
        return

    if data.startswith("add_wallet_"):
        target_user_id = int(data.split("_")[-1])

        request = pending_deposit_requests.get(target_user_id)
        if not request:
            await query.message.reply_text("❌ لا يوجد طلب إيداع مرتبط بهذا المستخدم")
            return

        username = request["username"]

        user_states[ADMIN_ID] = {
            "step": "admin_add_wallet_address",
            "target_user_id": target_user_id,
            "target_username": username
        }

        await query.message.reply_text(
            f"💼 أدخل الآن عنوان محفظة المستخدم {username}",
            reply_markup=admin_cancel_keyboard()
        )
        return    
    #===
    if data.startswith("approve_deposit_"):
        user_id = int(data.split("_")[-1])
        request = pending_deposit_requests.get(user_id)

        if not request:
            await query.edit_message_caption(caption="❌ الطلب غير موجود")
            return

        username = request["username"]
        ensure_user_defaults(username)
        request_type = request.get("type", "new_deposit")

        if has_active_capital_withdraw_request(username):
            pending_deposit_requests.pop(user_id, None)
            save_data()

            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "❌ تم رفض طلب الإيداع تلقائيًا\n\n"
                        "لديك طلب سحب رأس مال قيد الانتظار، ولا يمكن تنفيذ أي إيداع أو تغيير باقة حتى تتم معالجة الطلب."
                    )
                )
            except:
                pass

            await query.edit_message_caption(
                caption="❌ تم رفض الطلب لأن المستخدم لديه طلب سحب رأس مال قيد الانتظار"
            )
            return

        if request_type == "topup_deposit":
            current_plan = user_plans.get(username, "NONE")

            if current_plan in [None, "NONE"] or current_plan not in PLANS:
                pending_deposit_requests.pop(user_id, None)
                save_data()
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ تم رفض الإيداع لأنك لا تملك باقة مفعلة حاليًا"
                )
                await query.edit_message_caption(caption="❌ تم رفض الإيداع لأن المستخدم لا يملك باقة مفعلة")
                return

            if is_user_frozen(username) or is_user_banned(username):
                pending_deposit_requests.pop(user_id, None)
                save_data()
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ لا يمكن الموافقة على الإيداع لأن حالة الحساب لا تسمح بذلك"
                )
                await query.edit_message_caption(caption="❌ لا يمكن الموافقة لأن الحساب غير نشط")
                return

            amount = round(float(request["amount"]), 2)

            # تحديث الأرباح القديمة قبل زيادة رأس المال
            update_profit(username)

            old_capital = get_user_capital(username)
            old_balance = get_user_total_balance(username)
            new_capital = round(old_capital + amount, 2)
            new_balance = round(old_balance + amount, 2)

            current_withdraw_end_ts = get_next_withdraw_timestamp(username)
            now_ts = time.time()

            current_plan_data = PLANS[current_plan]
            current_max_deposit = current_plan_data["max_deposit"]

            if current_max_deposit is not None and new_capital > float(current_max_deposit):
                suitable_plan = get_plan_by_capital_amount(new_capital)

                pending_deposit_requests.pop(user_id, None)
                save_data()

                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"❌ لم تتم الموافقة على الإيداع الجديد لأنه يتجاوز حدود باقتك الحالية\n\n"
                        f"📦 باقتك الحالية: {current_plan}\n"
                        f"💰 رأس المال الحالي: {old_capital}$\n"
                        f"➕ مبلغ الإيداع المطلوب: {amount}$\n"
                        f"📈 رأس المال بعد الإيداع: {new_capital}$\n\n"
                        f"✅ هذا الرصيد يناسب باقة: {suitable_plan if suitable_plan else 'غير محددة'}\n"
                        f"يرجى طلب تغيير الباقة بدل الإيداع العادي."
                    )
                )

                await query.edit_message_caption(
                    caption="❌ تم رفض الإيداع لأنه يتجاوز حدود الباقة الحالية"
                )
                return

            user_deposits[username] = new_capital
            user_balance[username] = new_balance

            if current_withdraw_end_ts and current_withdraw_end_ts > now_ts:
                pending_profit_capital_activation[username] = {
                    "old_capital": old_capital,
                    "new_capital": new_capital,
                    "topup_amount": amount,
                    "activate_at": current_withdraw_end_ts,
                    "created_at": now_ts
                }
            else:
                pending_profit_capital_activation.pop(username, None)

            user_last_profit[username] = time.time()

            user_deposit_logs.setdefault(username, []).append({
                "amount": amount,
                "time": now_str(),
                "status": "approved",
                "type": "topup_deposit",
                "note": f"تمت الموافقة على إيداع جديد | رأس المال من {old_capital}$ إلى {new_capital}$"
            })

            add_transaction(
                username,
                "topup_deposit_approved",
                amount,
                f"إيداع جديد فوق الرصيد الحالي | رأس المال من {old_capital}$ إلى {new_capital}$"
            )

            pending_deposit_requests.pop(user_id, None)
            save_data()

            if current_withdraw_end_ts and current_withdraw_end_ts > now_ts:
                profit_activation_text = (
                    f"⏳ ملاحظة مهمة:\n"
                    f"سيتم احتساب الأرباح اليومية مؤقتًا على رأس مالك القديم: {old_capital}$\n"
                    f"حتى انتهاء دورة السحب الحالية بتاريخ:\n"
                    f"{format_timestamp(current_withdraw_end_ts)}\n\n"
                    f"بعد انتهاء الدورة الحالية، سيبدأ احتساب الأرباح على رأس المال الجديد: {new_capital}$"
                )
            else:
                profit_activation_text = (
                    f"✅ سيتم احتساب الأرباح القادمة على رأس المال الجديد مباشرة: {new_capital}$"
                )

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ تمت الموافقة على الإيداع الجديد بنجاح\n\n"
                    f"📦 الباقة الحالية: {current_plan}\n"
                    f"➕ مبلغ الإيداع: {amount}$\n"
                    f"💰 رأس المال السابق: {old_capital}$\n"
                    f"💰 رأس المال الجديد: {new_capital}$\n"
                    f"📈 الرصيد الحالي: {new_balance}$\n\n"
                    f"{profit_activation_text}"
                ),
                reply_markup=main_menu_keyboard()
            )

            await query.edit_message_caption(
                caption=(
                    f"✅ تمت الموافقة على الإيداع الجديد\n\n"
                    f"👤 المستخدم: {username}\n"
                    f"➕ المبلغ: {amount}$\n"
                    f"💰 رأس المال القديم: {old_capital}$\n"
                    f"💰 رأس المال الجديد: {new_capital}$\n"
                    f"📊 احتساب الأرباح الحالي: على {old_capital}$\n"
                    f"⏳ يبدأ احتساب الأرباح على رأس المال الجديد بتاريخ:\n"
                    f"{format_timestamp(current_withdraw_end_ts) if current_withdraw_end_ts else 'فورًا'}"
                )
            )
            return

        if request_type == "plan_change":
            old_plan = request.get("old_plan", user_plans.get(username, "NONE"))
            new_plan = request.get("new_plan", request["plan"])
            amount = float(request["amount"])

            user_balance[username] = round(float(user_balance.get(username, 0)) + amount, 2)
            user_deposits[username] = round(float(user_deposits.get(username, 0)) + amount, 2)
            user_plans[username] = new_plan
            user_last_profit[username] = time.time()
            user_last_withdraw_time[username] = time.time()

            user_deposit_logs.setdefault(username, []).append({
            "amount": request["amount"],
            "time": now_str(),
            "status": "approved",
            "type": "new_deposit",
            "note": f"تمت الموافقة على إيداع وتفعيل {request['plan']}"
             })

            add_transaction(username, "plan_change_approved", amount, f"تغيير الباقة من {old_plan} إلى {new_plan}")

            pending_deposit_requests.pop(user_id, None)
            save_data()

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ تمت الموافقة على طلب تغيير الباقة بنجاح\n"
                    f"📦 الباقة القديمة: {old_plan}\n"
                    f"📦 الباقة الجديدة: {new_plan}\n"
                    f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}"
                ),
                reply_markup=main_menu_keyboard()
            )

            await query.edit_message_caption(caption="✅ تمت الموافقة على طلب تغيير الباقة")
            return

        if user_plans.get(username) not in [None, "NONE"]:
            await query.edit_message_caption(caption="❌ هذا المستخدم لديه باقة مفعلة بالفعل")
            return

        if is_user_frozen(username) or is_user_banned(username):
            await query.edit_message_caption(caption="❌ لا يمكن الموافقة لأن حالة الحساب ليست نشطة")
            return
        

        deposit_amount = round(float(request["amount"]), 2)
        user_balance[username] = deposit_amount
        user_deposits[username] = deposit_amount
        user_last_profit[username] = time.time()
        user_plans[username] = request["plan"]
        if username not in user_first_deposit_time:
           user_first_deposit_time[username] = time.time()

        user_deposit_logs.setdefault(username, []).append({
            "amount": request["amount"],
            "time": now_str(),
            "status": "approved",
            "type": "new_deposit",
            "note": f"تمت الموافقة على إيداع وتفعيل {request['plan']}"
        })

        add_transaction(username, "deposit_approved", request["amount"], f"تفعيل {request['plan']}")
        referrer_username = user_referrer.get(username)
        bonus_already_paid = referral_bonus_paid.get(username, False)

        if referrer_username and not bonus_already_paid:
           bonus_amount = round(deposit_amount * 0.20, 2)

           user_balance[referrer_username] = round(float(user_balance.get(referrer_username, 0)) + bonus_amount, 2)

           add_transaction(
                referrer_username,
                "referral_bonus",
                bonus_amount,
                f"هدية أول إيداع من المستخدم {username}"
                  )

           referral_bonus_paid[username] = True

           referrer_user_id = get_saved_telegram_id(referrer_username)
           if referrer_user_id:
               try:
                   await context.bot.send_message(
                         chat_id=referrer_user_id,
                         text=(
                         f"🎉 مبروك! حصلت على هدية إحالة\n\n"
                         f"👤 المستخدم المدعو: {username}\n"
                         f"💰 قيمة أول إيداع: {deposit_amount}$\n"
                         f"🎁 قيمة الهدية: {bonus_amount}$"
                          )
                          )
               except:
                    pass

        pending_deposit_requests.pop(user_id, None)
        save_data()

        home_keyboard = ReplyKeyboardMarkup(
           [["الصفحة الرئيسية"]],
           resize_keyboard=True
           )

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ تم تفعيل باقتك بنجاح 🎉\nاضغط على زر الصفحة الرئيسية في الأسفل",
            reply_markup=home_keyboard
        )

        await query.edit_message_caption(caption="✅ تمت الموافقة على طلب الإيداع")
        return

    elif data.startswith("reject_deposit_"):
         user_id = int(data.split("_")[-1])

         request = pending_deposit_requests.get(user_id)
         request_type = request.get("type", "new_deposit") if request else "new_deposit"

         if request:
             username = request.get("username")
             amount = round(float(request.get("amount", 0)), 2)
             plan_name = request.get("plan", "غير معروف")

             if username:
                 if request_type == "plan_change":
                     note = f"تم رفض طلب تغيير الباقة إلى {plan_name}"
                 elif request_type == "topup_deposit":
                     note = "تم رفض طلب الإيداع الجديد فوق الرصيد الحالي"
                 else:
                     note = f"تم رفض طلب الإيداع للباقة {plan_name}"

                 user_deposit_logs.setdefault(username, []).append({
                     "amount": amount,
                     "time": now_str(),
                     "status": "rejected",
                     "type": request_type,
                     "note": note
                 })

                 add_transaction(
                     username,
                     "deposit_rejected",
                     amount,
                     note
                 )

         pending_deposit_requests.pop(user_id, None)
         save_data()

         if request_type == "plan_change":
            reject_text = "❌ تم رفض طلب تغيير الباقة"
         elif request_type == "topup_deposit":
            reject_text = "❌ تم رفض طلب الإيداع الجديد"
         else:
            reject_text = "❌ تم رفض طلب الإيداع"

         await context.bot.send_message(
            chat_id=user_id,
            text=reject_text
         )

         await query.edit_message_caption(caption=reject_text)
         return

    elif data.startswith("approve_withdraw_"):
        user_id = int(data.split("_")[-1])
        request = pending_withdraw_requests.get(user_id)

        if not request:
            await query.edit_message_text("❌ طلب السحب غير موجود")
            return

        username = request["username"]
        ensure_user_defaults(username)

        if not is_user_verified(username):
            pending_withdraw_requests.pop(user_id, None)
            save_data()

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "❌ تم رفض طلب السحب تلقائيًا\n\n"
                    "حسابك غير موثق حتى الآن.\n"
                    "يجب توثيق الحساب أولًا قبل السماح بأي عملية سحب.\n\n"
                    "اضغط على زر 🪪 توثيق الحساب وابدأ التوثيق الآن."
                )
            )

            await query.edit_message_text(
                "❌ تم رفض طلب السحب لأن حساب المستخدم غير موثق"
            )
            return

        if is_user_frozen(username) or is_user_banned(username):
            pending_withdraw_requests.pop(user_id, None)
            save_data()
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ تعذر تنفيذ السحب لأن حالة الحساب لا تسمح بذلك حاليًا"
            )
            await query.edit_message_text("❌ تعذر تنفيذ السحب لأن الحساب ليس بحالة نشطة")
            return

        amount = round(float(request["amount"]), 2)

        current_balance = get_user_total_balance(username)
        capital = get_user_capital(username)
        min_withdraw = get_min_withdraw_amount(username)
        max_profit_available = round(current_balance - capital, 2)

        if max_profit_available < 0:
            max_profit_available = 0

        if amount < min_withdraw:
            pending_withdraw_requests.pop(user_id, None)
            save_data()

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"❌ تم رفض طلب السحب لأن المبلغ أقل من الحد الأدنى للسحب\n\n"
                    f"💰 رأس مالك: {capital}$\n"
                    f"📉 الحد الأدنى للسحب: {min_withdraw}$\n"
                    f"💸 المبلغ المطلوب: {amount}$\n\n"
                    f"📌 الحد الأدنى للسحب يساوي 20% من رأس المال"
                )
            )

            await query.edit_message_text(
                "❌ تم رفض طلب السحب لأن المبلغ أقل من الحد الأدنى"
            )
            return

        amount = min(amount, max_profit_available)

        if amount <= 0:
            pending_withdraw_requests.pop(user_id, None)
            save_data()
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ تعذر تنفيذ السحب لأن الأرباح المتاحة أصبحت غير كافية"
            )
            await query.edit_message_text("❌ الأرباح المتاحة لم تعد كافية لتنفيذ السحب")
            return

        if amount < min_withdraw:
            pending_withdraw_requests.pop(user_id, None)
            save_data()

            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"❌ تم رفض طلب السحب لأن الأرباح المتاحة أصبحت أقل من الحد الأدنى للسحب\n\n"
                    f"💰 رأس مالك: {capital}$\n"
                    f"📉 الحد الأدنى للسحب: {min_withdraw}$\n"
                    f"📈 الأرباح المتاحة الآن: {max_profit_available}$"
                )
            )

            await query.edit_message_text(
                "❌ تم رفض طلب السحب لأن الأرباح المتاحة أصبحت أقل من الحد الأدنى"
            )
            return

        user_balance[username] = round(current_balance - amount, 2)
        user_last_withdraw_time[username] = time.time()

        # إذا كان السحب مفتوحًا يدويًا، نلغي هذه الحالة بعد تنفيذ السحب الفعلي
        if username in manual_withdraw_open:
            manual_withdraw_open.pop(username, None)

        user_withdraw_logs.setdefault(username, []).append({
            "amount": amount,
            "time": now_str(),
            "status": "approved",
            "note": "تمت الموافقة على سحب الأرباح"
        })

        add_transaction(username, "withdraw_approved", amount, "تمت الموافقة على سحب الأرباح")

        pending_withdraw_requests.pop(user_id, None)
        save_data()

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ تمت الموافقة على طلب السحب"
        )

        await query.edit_message_text("✅ تمت الموافقة على طلب سحب الأرباح")
        return

    elif data.startswith("reject_withdraw_"):
        user_id = int(data.split("_")[-1])
        request = pending_withdraw_requests.get(user_id)

        if request:
            username = request["username"]
            user_withdraw_logs.setdefault(username, []).append({
                "amount": request["amount"],
                "time": now_str(),
                "status": "rejected",
                "note": "تم رفض طلب سحب الأرباح من قبل الإدارة"
            })
            add_transaction(username, "withdraw_rejected", request["amount"], "تم رفض طلب سحب الأرباح")

        pending_withdraw_requests.pop(user_id, None)
        save_data()

        await context.bot.send_message(
            chat_id=user_id,
            text="❌ السحب غير متاح حالياً، أعد المحاولة لاحقاً"
        )

        await query.edit_message_text("❌ تم رفض طلب السحب")
        return
    
    elif data.startswith("admin_addbalance_"):
        username = data.replace("admin_addbalance_", "", 1)

        user_states[ADMIN_ID] = {
            "step": "admin_add_balance_input",
            "target_username": username
        }

        await query.message.reply_text(
            f"➕ أرسل الآن المبلغ الذي تريد إضافته للمستخدم {username}"
        )
        return

    elif data.startswith("admin_subbalance_"):
        username = data.replace("admin_subbalance_", "", 1)

        user_states[ADMIN_ID] = {
            "step": "admin_sub_balance_input",
            "target_username": username
        }

        await query.message.reply_text(
            f"➖ أرسل الآن المبلغ الذي تريد خصمه من المستخدم {username}"
        )
        return

    elif data.startswith("admin_setplan_"):
        username = data.replace("admin_setplan_", "", 1)

        if username not in users:
            await query.message.reply_text("❌ المستخدم غير موجود")
            return

        await query.message.reply_text(
            f"📦 اختر الآن الباقة الجديدة للمستخدم {username}:",
            reply_markup=build_admin_set_plan_keyboard(username)
        )
        return
    
    elif data.startswith("admin_chooseplan::"):
        parts = data.split("::")
        if len(parts) != 3:
            await query.message.reply_text("❌ بيانات اختيار الباقة غير صحيحة")
            return

        username = parts[1]
        plan_code = parts[2].lower()

        if username not in users:
            await query.message.reply_text("❌ المستخدم غير موجود")
            return

        plan_map = {
            "silver": "الباقة الفضية",
            "gold": "الباقة الذهبية",
            "vip": "باقة VIP"
        }

        if plan_code not in plan_map:
            await query.message.reply_text("❌ الباقة غير صحيحة")
            return

        new_plan = plan_map[plan_code]
        old_plan = user_plans.get(username, "NONE")

        user_plans[username] = new_plan

        now = time.time()
        if username not in user_first_deposit_time:
            user_first_deposit_time[username] = now
        user_last_withdraw_time[username] = now

        save_data()
        add_transaction(username, "admin_set_plan", 0, f"تغيير الباقة من {old_plan} إلى {new_plan}")

        user_id_found = find_user_id_by_username(username)
        if user_id_found:
            try:
                await context.bot.send_message(
                    chat_id=user_id_found,
                    text=(
                        f"✅ تم تعديل باقتك بواسطة الإدارة\n"
                        f"📦 الباقة الجديدة: {new_plan}\n"
                        f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}"
                    )
                )
            except:
                pass

        await query.message.reply_text(
            f"✅ تم تغيير باقة المستخدم {username}\n"
            f"📦 القديمة: {old_plan}\n"
            f"📦 الجديدة: {new_plan}\n\n"
            f"{build_admin_user_text(username)}",
            reply_markup=build_admin_user_keyboard(username)
        )
        return

    elif data.startswith("admin_resetwithdraw_"):
        username = data.replace("admin_resetwithdraw_", "", 1)

        if username not in users:
            await query.message.reply_text("❌ المستخدم غير موجود")
            return

        now = time.time()

        if username not in user_first_deposit_time:
            user_first_deposit_time[username] = now

        user_last_withdraw_time[username] = now
        save_data()
        add_transaction(username, "admin_reset_withdraw_cycle", 0, "إعادة ضبط دورة السحب بواسطة الأدمن")

        user_id_found = find_user_id_by_username(username)
        if user_id_found:
            try:
                await context.bot.send_message(
                    chat_id=user_id_found,
                    text=(
                        f"♻️ تم إعادة ضبط دورة السحب الخاصة بك بواسطة الإدارة\n"
                        f"💸 موعد السحب القادم: {get_next_withdraw_datetime_text(username)}"
                    )
                )
            except:
                pass

        await query.edit_message_text(
            text=build_admin_user_text(username) + "\n\n✅ تم إعادة ضبط دورة السحب بنجاح",
            reply_markup=build_admin_user_keyboard(username)
        )
        return
    
    elif data.startswith("admin_message_"):
        username = data.replace("admin_message_", "", 1)

        if username not in users:
            await query.message.reply_text("❌ المستخدم غير موجود")
            return

        user_states[ADMIN_ID] = {
            "step": "admin_send_private_message",
            "target_username": username
        }

        await query.message.reply_text(
            f"📨 اكتب الآن الرسالة التي تريد إرسالها إلى المستخدم {username}\n\n"
            f"للتراجع اضغط: 🔙 إلغاء الإرسال",
            reply_markup=admin_cancel_keyboard()
        )
        return
    
    elif data.startswith("admin_delete_subscription_"):
       username = data.replace("admin_delete_subscription_", "", 1)

       if username not in users:
           await query.message.reply_text("❌ المستخدم غير موجود")
           return

       await query.message.reply_text(
        f"⚠️ هل أنت متأكد من حذف اشتراك المستخدم؟\n\n"
        f"👤 المستخدم: {username}\n"
        f"📦 الباقة الحالية: {user_plans.get(username, 'NONE')}\n"
        f"💰 رأس المال الحالي: {get_user_capital(username)}$\n"
        f"📈 الرصيد الحالي: {get_user_total_balance(username)}$\n\n"
        f"سيتم تصفير بيانات الاشتراك المالية فقط، وسيبقى الحساب موجودًا.",
        reply_markup=build_delete_subscription_confirm_keyboard(username)
       )
       return
    
    elif data.startswith("admin_confirm_delete_subscription_"):
       username = data.replace("admin_confirm_delete_subscription_", "", 1)

       success, result_text = delete_user_subscription_only(username)

       if not success:
        await query.message.reply_text(result_text)
        return

       user_id_found = get_saved_telegram_id(username)

       if user_id_found:
        try:
            await context.bot.send_message(
                chat_id=user_id_found,
                text=(
                    "🗑 تم حذف اشتراكك الحالي بواسطة الإدارة.\n\n"
                    "يمكنك الآن الاشتراك من جديد من صفحة البداية."
                ),
                reply_markup=main_menu_keyboard()
            )
        except Exception as e:
            print(f"خطأ في إرسال إشعار حذف الاشتراك للمستخدم: {e}")

       await query.message.reply_text(
        f"{result_text}\n\n"
        f"{build_admin_user_text(username)}",
        reply_markup=build_admin_user_keyboard(username)
       )
       return


    elif data.startswith("admin_cancel_delete_subscription_"):
       username = data.replace("admin_cancel_delete_subscription_", "", 1)

       if username in users:
        await query.message.reply_text(
            "✅ تم إلغاء عملية حذف الاشتراك",
            reply_markup=build_admin_user_keyboard(username)
        )
       else:
        await query.message.reply_text("✅ تم إلغاء العملية")

       return
    
    elif data.startswith("admin_ban_"):
        username = data.replace("admin_ban_", "", 1)
        result = await apply_admin_status_action(context, username, "ban")
        await query.edit_message_text(
            text=build_admin_user_text(username) + f"\n\n{result}",
            reply_markup=build_admin_user_keyboard(username)
        )
        return

    elif data.startswith("admin_unban_"):
        username = data.replace("admin_unban_", "", 1)
        result = await apply_admin_status_action(context, username, "unban")
        await query.edit_message_text(
            text=build_admin_user_text(username) + f"\n\n{result}",
            reply_markup=build_admin_user_keyboard(username)
        )
        return

    elif data.startswith("admin_freeze_"):
        username = data.replace("admin_freeze_", "", 1)
        result = await apply_admin_status_action(context, username, "freeze")
        await query.edit_message_text(
            text=build_admin_user_text(username) + f"\n\n{result}",
            reply_markup=build_admin_user_keyboard(username)
        )
        return

    elif data.startswith("admin_unfreeze_"):
        username = data.replace("admin_unfreeze_", "", 1)
        result = await apply_admin_status_action(context, username, "unfreeze")
        await query.edit_message_text(
            text=build_admin_user_text(username) + f"\n\n{result}",
            reply_markup=build_admin_user_keyboard(username)
        )
        return

    elif data.startswith("admin_refresh_"):
        username = data.replace("admin_refresh_", "", 1)
        await query.edit_message_text(
            text=build_admin_user_text(username),
            reply_markup=build_admin_user_keyboard(username)
        )
        return
    
    elif data.startswith("admin_identity_"):
       username = data.replace("admin_identity_", "", 1)

       if username not in users:
        await query.message.reply_text("❌ المستخدم غير موجود")
        return

       photos = user_identity_photos.get(username)

       if not photos:
        # محاولة احتياطية: إذا كان لديه طلب توثيق معلق حاليًا
        target_user_id = get_saved_telegram_id(username)
        pending_request = pending_verification_requests.get(target_user_id) if target_user_id else None

        if pending_request:
            photos = {
                "front_id_file_id": pending_request.get("front_id_file_id"),
                "back_id_file_id": pending_request.get("back_id_file_id"),
                "updated_at": pending_request.get("time", "غير متوفر")
            }

       if not photos:
        await query.message.reply_text(
            f"❌ لا توجد صور بطاقة شخصية محفوظة للمستخدم: {username}\n\n"
            "ملاحظة: الصور القديمة التي تمت الموافقة عليها قبل هذا التعديل قد لا تكون محفوظة إذا تم حذف طلب التوثيق."
        )
        return

       front_photo = photos.get("front_id_file_id")
       back_photo = photos.get("back_id_file_id")
       updated_at = photos.get("updated_at", "غير متوفر")

       if not front_photo or not back_photo:
        await query.message.reply_text("❌ بيانات صور البطاقة غير مكتملة لهذا المستخدم")
        return

       try:
        await context.bot.send_photo(
            chat_id=query.from_user.id,
            photo=front_photo,
            caption=(
                f"🪪 البطاقة الشخصية للمستخدم: {username}\n\n"
                f"📷 الوجه الأمامي\n"
                f"🕒 آخر تحديث: {updated_at}"
            )
        )

        await context.bot.send_photo(
            chat_id=query.from_user.id,
            photo=back_photo,
            caption=(
                f"🪪 البطاقة الشخصية للمستخدم: {username}\n\n"
                f"📷 الوجه الخلفي\n"
                f"🕒 آخر تحديث: {updated_at}"
            )
        )

       except Exception as e:
        print(f"خطأ في إرسال صور البطاقة الشخصية للأدمن: {e}")
        await query.message.reply_text("❌ حدث خطأ أثناء إرسال صور البطاقة الشخصية")
    
       return
    
    elif data.startswith("admin_openwithdraw_"):
        username = data.replace("admin_openwithdraw_", "", 1)

        success, result_text = open_withdraw_now_for_user(username)

        if not success:
            await query.message.reply_text(result_text)
            return

        user_id_found = find_user_id_by_username(username)
        if user_id_found:
            try:
                await context.bot.send_message(
                    chat_id=user_id_found,
                    text=(
                        "✅ تم فتح السحب لك بواسطة الإدارة\n\n"
                        "💸 يمكنك الآن طلب سحب الأرباح ابتداءً من هذه اللحظة.\n"
                        f"📦 باقتك الحالية: {user_plans.get(username, 'NONE')}\n"
                        f"🕒 وقت فتح السحب: {now_str()}"
                    )
                )
            except Exception as e:
                print(f"خطأ في إرسال إشعار فتح السحب للمستخدم: {e}")

        await query.edit_message_text(
            text=build_admin_user_text(username) + "\n\n✅ تم فتح السحب لهذا المستخدم بنجاح",
            reply_markup=build_admin_user_keyboard(username)
        )
        return
    
    elif data.startswith("admin_closewithdraw_"):
        username = data.replace("admin_closewithdraw_", "", 1)

        success, result_text = close_manual_withdraw_for_user(username)

        if not success:
            await query.message.reply_text(result_text)
            return

        user_id_found = find_user_id_by_username(username)
        if user_id_found:
            try:
                await context.bot.send_message(
                    chat_id=user_id_found,
                    text=(
                        "🔒 تم إيقاف فتح السحب اليدوي بواسطة الإدارة\n\n"
                        "تمت إعادة السحب إلى وضعه الطبيعي وفق دورة السحب الخاصة بباقتك."
                    )
                )
            except Exception as e:
                print(f"خطأ في إرسال إشعار إيقاف فتح السحب للمستخدم: {e}")

        await query.edit_message_text(
            text=build_admin_user_text(username) + "\n\n✅ تم إيقاف فتح السحب وإعادة السحب إلى وضعه الطبيعي",
            reply_markup=build_admin_user_keyboard(username)
        )
        return

    elif data.startswith("admin_tx_"):
        username = data.replace("admin_tx_", "", 1)
        await query.message.reply_text(build_user_transactions_text(username))
        return
    
    elif data.startswith("reply_support_"):
       target_user_id = int(data.split("_")[-1])
       operator_id = query.from_user.id

       target_username = find_username_by_telegram_id(target_user_id)

       if not target_username:
           await query.message.reply_text("❌ تعذر تحديد المستخدم صاحب رسالة الدعم")
           return

       # المدير يستطيع الرد دائمًا
       # وعند ضغط المدير على زر الرد يتم حجز المستخدم للمدير لمدة 15 دقيقة
       # ويتم حذف نسخ رسالة المستخدم من موظفي الدعم
       if operator_id == ADMIN_ID:

          claim_support_user(target_username, ADMIN_ID)

          await delete_support_message_from_other_employees(
              context=context,
              target_user_id=target_user_id,
              keep_employee_id=ADMIN_ID
               )

          user_states[operator_id] = {
             "step": "admin_reply_support",
             "target_user_id": target_user_id
              }

          await query.message.reply_text(
               f"✉️ اكتب الآن الرد الذي تريد إرساله إلى المستخدم:\n"
               f"🆔 User ID: {target_user_id}\n"
               f"⏳ تم حجز هذا المستخدم للمدير لمدة 15 دقيقة\n\n"
               f"✅ تم حذف نسخة رسالة الدعم من موظفي الدعم.\n\n"
               f"للتراجع اضغط: 🔙 إلغاء الإرسال",
             reply_markup=admin_cancel_keyboard()
              )
          return

       # الموظف لا يستطيع الرد إذا نظام الموظفين متوقف
       if not support_employees_enabled:
           await query.answer("⛔ موظفو الدعم متوقفون حاليًا", show_alert=True)
           return

       if not is_support_employee(operator_id):
           await query.answer("❌ لا تملك صلاحية الرد على الدعم", show_alert=True)
           return

       # إذا المحادثة محجوزة لموظف آخر
       if has_active_support_claim(target_username):
           current_employee_id = get_support_claim_employee_id(target_username)

           if current_employee_id and int(current_employee_id) != int(operator_id):
               await query.answer("❌ هذه المحادثة محجوزة لموظف آخر مؤقتًا", show_alert=True)
               return

       # حجز المستخدم لهذا الموظف لمدة 15 دقيقة
       claim_support_user(target_username, operator_id)

       # حذف نسخة الرسالة من باقي الموظفين فقط
       await delete_support_message_from_other_employees(
           context=context,
           target_user_id=target_user_id,
           keep_employee_id=operator_id
       )

       user_states[operator_id] = {
        "step": "admin_reply_support",
        "target_user_id": target_user_id
       }

       await query.message.reply_text(
           f"✉️ اكتب الآن الرد الذي تريد إرساله إلى المستخدم:\n"
           f"🆔 User ID: {target_user_id}\n"
           f"⏳ تم حجز هذه المحادثة لك لمدة 15 دقيقة\n\n"
           f"للتراجع اضغط: 🔙 إلغاء الإرسال",
           reply_markup=admin_cancel_keyboard()
       )
       return
    
    elif data.startswith("admin_blocksupport_"):
        username = data.replace("admin_blocksupport_", "", 1)
        result = await apply_admin_support_action(context, username, "blocksupport")
        await query.edit_message_text(
            text=build_admin_user_text(username) + f"\n\n{result}",
            reply_markup=build_admin_user_keyboard(username)
        )
        return

    elif data.startswith("admin_unblocksupport_"):
        username = data.replace("admin_unblocksupport_", "", 1)
        result = await apply_admin_support_action(context, username, "unblocksupport")
        await query.edit_message_text(
            text=build_admin_user_text(username) + f"\n\n{result}",
            reply_markup=build_admin_user_keyboard(username)
        )
        return
    
    if data.startswith("msg_plan_"):
        plan_name = data.replace("msg_plan_", "", 1)

        user_states[ADMIN_ID] = {
            "step": "admin_send_plan_message",
            "target_plan": plan_name
        }

        await query.message.reply_text(
            f"📨 اكتب الآن الرسالة التي تريد إرسالها إلى مشتركي: {plan_name}\n\n"
            f"للتراجع اضغط: 🔙 إلغاء الإرسال",
            reply_markup=admin_cancel_keyboard()
        )
        return

async def apply_admin_support_action(context, username, action):

    if username not in users:
        return "❌ المستخدم غير موجود"

    user_id_found = find_user_id_by_username(username)

    if action == "blocksupport":
        if is_support_blocked(username):
            return f"ℹ️ المستخدم {username} محجوب من الدعم بالفعل"

        support_blocked_users[username] = True
        save_data()
        add_transaction(username, "block_support", 0, "تم حجب المستخدم من مراسلة الدعم")

        if user_id_found:
            try:
                await context.bot.send_message(
                    chat_id=user_id_found,
                    text="🚫 تم حجب خاصية مراسلة الدعم عن حسابك مؤقتًا"
                )
            except:
                pass

        return f"✅ تم حجب المستخدم {username} من مراسلة الدعم"

    if action == "unblocksupport":
        if not is_support_blocked(username):
            return f"ℹ️ المستخدم {username} غير محجوب من الدعم أصلًا"

        support_blocked_users[username] = False
        save_data()
        add_transaction(username, "unblock_support", 0, "تم فك حجب المستخدم من مراسلة الدعم")

        if user_id_found:
            try:
                await context.bot.send_message(
                    chat_id=user_id_found,
                    text="✅ تم السماح لك مجددًا بمراسلة الدعم"
                )
            except:
                pass

        return f"✅ تم فك حجب المستخدم {username} من مراسلة الدعم"

    return "❌ إجراء غير معروف"

async def block_support_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if not context.args:
        await update.message.reply_text("❌ استخدم:\n/blocksupport username")
        return

    username = context.args[0]
    result = await apply_admin_support_action(context, username, "blocksupport")
    await update.message.reply_text(result)


async def unblock_support_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ليس لديك صلاحية استخدام هذا الأمر")
        return

    if not context.args:
        await update.message.reply_text("❌ استخدم:\n/unblocksupport username")
        return

    username = context.args[0]
    result = await apply_admin_support_action(context, username, "unblocksupport")
    await update.message.reply_text(result)
# =========================
# التشغيل
# =========================
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN غير موجود. تأكد من وضع التوكن أو متغير البيئة.")
    
    init_db_pool()
    init_db()

    load_users()
    load_chat_ids()
    load_data()

    for username in users:
        ensure_user_defaults(username)

    migrate_old_users_timezones()

    save_data()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.job_queue.run_repeating(check_capital_withdraw_requests, interval=60, first=10)
    app.job_queue.run_repeating(auto_update_all_profits, interval=300, first=15)
    app.job_queue.run_repeating(send_unverified_account_reminders, interval=43200, first=60)

    # رسائل تحفيزية لغير المشتركين ورسائل تطمينية للمشتركين كل 12 ساعة
    app.job_queue.run_repeating(send_periodic_motivation_messages, interval=43200, first=600)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("k", k))
    app.add_handler(CommandHandler("ana", ana))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("send", send_to_all))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("userinfo", userinfo))

    app.add_handler(CommandHandler("resetpass", resetpass))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("freeze", freeze_user))
    app.add_handler(CommandHandler("unfreeze", unfreeze_user))
    app.add_handler(CommandHandler("blocksupport", block_support_user))
    app.add_handler(CommandHandler("unblocksupport", unblock_support_user))
    app.add_handler(CommandHandler("addbalance", add_balance))
    app.add_handler(CommandHandler("subbalance", subtract_balance))
    app.add_handler(CommandHandler("setplan", set_plan))
    app.add_handler(CommandHandler("resetwithdraw", reset_withdraw_cycle))

    app.add_handler(CallbackQueryHandler(handle_admin_buttons))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()