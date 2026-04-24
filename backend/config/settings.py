import os
import sys
from dotenv import load_dotenv

load_dotenv()

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("FATAL: DATABASE_URL not set. Add your Neon.tech PostgreSQL URL to .env")
    sys.exit(1)

# --- Security ---
SECRET_KEY = os.getenv("SECRET_KEY", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)

if SECRET_KEY in ("", "change-me-to-random-string"):
    print("WARNING: Insecure SECRET_KEY. Run: python -c \"import secrets; print(secrets.token_hex(32))\"")

# JWT
JWT_ACCESS_TOKEN_EXPIRES_MINUTES = 60
JWT_REFRESH_TOKEN_EXPIRES_DAYS = 30

# Account lockout
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# --- AI Services ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY", "")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "test")

# --- CORS ---
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")]

# --- Rate Limiting ---
RATE_LIMIT_DEFAULT = "60/minute"
RATE_LIMIT_AUTH = "10/minute"
RATE_LIMIT_PREDICT = "20/minute"

# --- File Uploads ---
MAX_IMAGE_SIZE_MB = 10
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}

# --- Input Limits ---
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 255
MAX_MESSAGE_LENGTH = 5000
MAX_CHAT_TITLE_LENGTH = 200
MAX_SYMPTOM_LENGTH = 3000
