from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard():
    keyboard = [
        ["الصفحة الرئيسية"],
        ["باقة VIP", "الباقة الذهبية", "الباقة الفضية"],
        ["باقتي", "👥 دعوة صديق"],
        ["➕ إيداع جديد", "💸 سحب الأرباح"],
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
    keyboard = [
        ["📥 طلبات الإيداع", "💸 طلبات السحب"],
        ["🏦 طلبات سحب رأس المال", "🗑 سجل الحسابات المحذوفة"],
        ["👥 عدد المستخدمين", "📊 ملخص مالي"],
        ["📌 حالة الاشتراك", "⛔ إيقاف/تشغيل الاشتراك"],
        ["🛠 حالة البوت", "⏯ إيقاف/تشغيل البوت"],
        ["👨‍💼 موظفو الدعم", "⏯ تشغيل/إيقاف موظفي الدعم"],
        ["📢 إرسال رسالة للجميع", "📨 إرسال رسالة حسب الباقة"],
        ["📂 فلترة المستخدمين", "📈 إحصائيات متقدمة"],
        ["🔍 بحث عن مستخدم", "🗑 حذف مستخدم"],
        ["🔙 رجوع"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def admin_cancel_keyboard():
    keyboard = [
        ["🔙 إلغاء الإرسال"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def build_delete_subscription_confirm_keyboard(username):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ تأكيد حذف الاشتراك",
                callback_data=f"admin_confirm_delete_subscription_{username}"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ إلغاء",
                callback_data=f"admin_cancel_delete_subscription_{username}"
            )
        ]
    ])


def build_my_plan_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تحديث العد التنازلي", callback_data="refresh_my_countdown")],
        [InlineKeyboardButton("📦 تغيير الباقة الحالية", callback_data="change_current_plan")]
    ])


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


def build_plan_change_confirm_keyboard(target_plan):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 إيداع", callback_data=f"start_plan_change_deposit::{target_plan}"),
            InlineKeyboardButton("🔙 رجوع", callback_data="change_plan_back_home")
        ]
    ])


def build_plan_action_keyboard(plan_name):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ اشتراك", callback_data=f"subscribe_plan::{plan_name}")
        ],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data="plan_details_back_home")
        ]
    ])


def build_support_reply_keyboard(user_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✉️ رد على المستخدم", callback_data=f"reply_support_{user_id}")
        ]
    ])


def build_delete_last_batch_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑 حذف آخر إرسال من المستخدمين", callback_data="delete_last_admin_batch")
        ]
    ])