from datetime import datetime, timedelta
import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from pydantic import BaseModel

from web_dashboard.config import WEB_SECRET_KEY
from web_dashboard.database import get_web_db_connection, release_web_db_connection
from web_dashboard.services.storage_service import web_db_get as db_get
from web_dashboard.services.storage_service import get_all_data


router = APIRouter()
bearer_scheme = HTTPBearer()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


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


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserRegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    residence: str
    accepted_terms: bool


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


def create_user_access_token(username: str):
    payload = {
        "sub": username,
        "role": "user",
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    }

    return jwt.encode(payload, WEB_SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, WEB_SECRET_KEY, algorithms=[ALGORITHM])

        username = payload.get("sub")
        role = payload.get("role")

        if not username or role != "user":
            raise HTTPException(status_code=401, detail="Invalid user token")

        users = db_get("users", {})

        if username not in users:
            raise HTTPException(status_code=401, detail="User no longer exists")

        data = get_all_data()
        user_telegram_ids = data.get("user_telegram_ids", {})

        telegram_id = user_telegram_ids.get(username)

        if not telegram_id:
            raise HTTPException(
                status_code=403,
                detail="يجب ربط حسابك مع Telegram قبل استخدام لوحة المستخدم"
            )

        return username

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid user token")


@router.get("/terms")
def get_terms():
    return {
        "terms": TERMS_TEXT
    }


@router.post("/login")
def user_login(request: UserLoginRequest):
    username = request.username.strip()
    password = request.password.strip()

    users = db_get("users", {})

    if username not in users:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if users.get(username) != password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    data = get_all_data()
    user_telegram_ids = data.get("user_telegram_ids", {})

    telegram_id = user_telegram_ids.get(username)

    if not telegram_id:
        raise HTTPException(
            status_code=403,
            detail="يجب ربط حسابك مع Telegram قبل تسجيل الدخول إلى لوحة المستخدم"
        )

    token = create_user_access_token(username)

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username
    }


@router.post("/register")
def user_register(request: UserRegisterRequest):
    username = request.username.strip()
    password = request.password.strip()
    full_name = request.full_name.strip()
    residence = request.residence.strip()

    if not request.accepted_terms:
        raise HTTPException(status_code=400, detail="You must accept terms")

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")

    if len(password) < 3:
        raise HTTPException(status_code=400, detail="Password must be at least 3 characters")

    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required")

    if not residence:
        raise HTTPException(status_code=400, detail="Residence is required")

    users = db_get("users", {})
    data = get_all_data()

    if username in users:
        raise HTTPException(status_code=400, detail="Username already exists")

    users[username] = password

    user_plans = data.get("user_plans", {})
    user_balance = data.get("user_balance", {})
    user_deposits = data.get("user_deposits", {})
    user_statuses = data.get("user_statuses", {})
    user_full_name = data.get("user_full_name", {})
    user_residence = data.get("user_residence", {})
    verified_users = data.get("verified_users", {})
    user_created_time = data.get("user_created_time", {})
    user_referrer = data.get("user_referrer", {})
    transactions = data.get("transactions", {})

    user_plans[username] = "NONE"
    user_balance[username] = 0
    user_deposits[username] = 0
    user_statuses[username] = "active"
    user_full_name[username] = full_name
    user_residence[username] = residence
    verified_users[username] = False
    user_created_time[username] = time.time()
    user_referrer[username] = "بدون دعوة"

    transactions.setdefault(username, []).append({
        "type": "web_account_created",
        "amount": 0,
        "note": "تم إنشاء الحساب من لوحة المستخدم عبر الويب بعد الموافقة على شروط الاستخدام",
        "time": now_str()
    })

    data["user_plans"] = user_plans
    data["user_balance"] = user_balance
    data["user_deposits"] = user_deposits
    data["user_statuses"] = user_statuses
    data["user_full_name"] = user_full_name
    data["user_residence"] = user_residence
    data["verified_users"] = verified_users
    data["user_created_time"] = user_created_time
    data["user_referrer"] = user_referrer
    data["transactions"] = transactions

    db_set("users", users)
    db_set("data", data)

    token = create_user_access_token(username)

    return {
        "success": True,
        "message": "Account created successfully",
        "access_token": token,
        "token_type": "bearer",
        "username": username
    }