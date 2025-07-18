# Список Telegram ID админов
ADMIN_IDS = [7975271183]  # замените на свой Telegram ID
import os
from dotenv import load_dotenv

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")

# SSH config for xray_manager
SSH_HOST = os.getenv("SSH_HOST")
SSH_USER = os.getenv("SSH_USER")
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH")
XRAY_MANAGER_PATH = os.getenv("XRAY_MANAGER_PATH", "/opt/xray_manager/xray_manager.py")
