"""
GLM-OCR App — Centralized Configuration
All settings from environment variables with sensible defaults.
"""
import os
import secrets

# === Auth ===
APP_PASSWORD = os.environ.get("APP_PASSWORD", "glm-ocr-2024")
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# === Server ===
PORT = int(os.environ.get("PORT", "8080"))

# === MaaS API (Zhipu GLM-OCR) ===
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
ZHIPU_API_BASE = os.environ.get("ZHIPU_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
OCR_MODEL = os.environ.get("OCR_MODEL", "glm-ocr")

# === Storage ===
DATA_DIR = os.environ.get("DATA_DIR", "/data")
INPUT_DIR = os.path.join(DATA_DIR, "input_pdfs")
OUTPUT_DIR = os.path.join(DATA_DIR, "output_markdown")
DB_PATH = os.path.join(DATA_DIR, "ocr_history.db")

# === OCR Settings ===
DPI = int(os.environ.get("DPI", "200"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))

# === Google Drive ===
GOOGLE_DRIVE_ENABLED = os.environ.get("GOOGLE_DRIVE_ENABLED", "false").lower() == "true"
DRIVE_CREDENTIALS_JSON = os.environ.get("DRIVE_CREDENTIALS_JSON", "")  # base64 encoded
DRIVE_INPUT_FOLDER_ID = os.environ.get("DRIVE_INPUT_FOLDER_ID", "")
DRIVE_OUTPUT_FOLDER_ID = os.environ.get("DRIVE_OUTPUT_FOLDER_ID", "")
DRIVE_SYNC_INTERVAL = int(os.environ.get("DRIVE_SYNC_INTERVAL", "60"))  # seconds

# === Init directories ===
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
