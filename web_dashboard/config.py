import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY", "change-this-secret-key")
WEB_ADMIN_USERNAME = os.getenv("WEB_ADMIN_USERNAME", "admin")
WEB_ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD", "admin123")
BOT_TOKEN = os.getenv("BOT_TOKEN")