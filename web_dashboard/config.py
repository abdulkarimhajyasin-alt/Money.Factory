import os
from dotenv import load_dotenv

load_dotenv()


def parse_env_int_list(name, default):
    raw_value = os.getenv(name, default)
    return [int(value.strip()) for value in raw_value.split(",") if value.strip()]


DATABASE_URL = os.getenv("DATABASE_URL")

WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY")
WEB_ADMIN_USERNAME = os.getenv("WEB_ADMIN_USERNAME", "admin")
WEB_ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = parse_env_int_list("ADMIN_IDS", "5685737658")
ADMIN_ID = ADMIN_IDS[0]
SUPPORT_EMPLOYEE_IDS = parse_env_int_list("SUPPORT_EMPLOYEE_IDS", "5102448932")
