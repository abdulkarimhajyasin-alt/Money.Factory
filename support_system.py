import time


SUPPORT_CLAIM_SECONDS = 600


def is_support_blocked(blocked_users, username):
    return bool(blocked_users.get(username, False))


def get_support_status_text(blocked_users, username):
    return "محجوب من الدعم 🚫" if is_support_blocked(blocked_users, username) else "مسموح له بالدعم ✅"


def is_support_employee(support_employee_ids, user_id):
    try:
        return int(user_id) in [int(x) for x in support_employee_ids]
    except Exception:
        return False


def is_support_operator(admin_id, support_employee_ids, user_id):
    try:
        return int(user_id) == int(admin_id) or is_support_employee(support_employee_ids, user_id)
    except Exception:
        return False


def get_support_operator_text(admin_id, support_employee_ids, user_id):
    if int(user_id) == int(admin_id):
        return "الأدمن"
    if is_support_employee(support_employee_ids, user_id):
        return "موظف دعم"
    return "الدعم"


def get_support_employees_status_text(support_employees_enabled):
    return "مفعّل ✅" if support_employees_enabled else "متوقف ⛔"


def cleanup_expired_support_claim(support_claims, username, now=None):
    claim = support_claims.get(username)
    if not claim:
        return False

    current_time = time.time() if now is None else now
    expires_at = float(claim.get("expires_at", 0))

    if expires_at and expires_at > current_time:
        return False

    support_claims.pop(username, None)
    return True


def has_active_support_claim(support_claims, username, now=None):
    cleanup_expired_support_claim(support_claims, username, now)
    return username in support_claims


def get_support_claim_employee_id(support_claims, username):
    if not has_active_support_claim(support_claims, username):
        return None

    try:
        return int(support_claims[username].get("employee_id"))
    except Exception:
        return None


def claim_support_user(support_claims, username, employee_id, now=None):
    current_time = time.time() if now is None else now
    support_claims[username] = {
        "employee_id": int(employee_id),
        "expires_at": current_time + SUPPORT_CLAIM_SECONDS
    }


def get_support_recipients_for_user(
    admin_id,
    support_employee_ids,
    support_employees_enabled,
    support_claims,
    username,
):
    recipients = [int(admin_id)]

    if support_employees_enabled:
        if has_active_support_claim(support_claims, username):
            employee_id = get_support_claim_employee_id(support_claims, username)
            if employee_id and employee_id not in recipients:
                recipients.append(employee_id)
        else:
            for employee_id in support_employee_ids:
                employee_id = int(employee_id)
                if employee_id not in recipients:
                    recipients.append(employee_id)

    return recipients
