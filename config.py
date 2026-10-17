import os
from pathlib import Path

try:  # python-dotenv is optional
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent

# ---------- Database ----------
DB_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "support.db"))
if not os.path.isabs(DB_PATH):
    DB_PATH = str(BASE_DIR / DB_PATH)

#كلمة سر واجهة الموظفين 
STAFF_PASSWORD = os.getenv("STAFF_PASSWORD", "")

# ---------- LLM  ----------
LLM_API_KEY = os.getenv("LLM_API_KEY", "")   
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://router.huggingface.co/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3-Coder-Next:novita")
LLM_TEMPERATURE = 0.1

# ---------- Discord (disabled by default) ----------
DISCORD_ENABLED = os.getenv("DISCORD_ENABLED", "false").strip().lower() == "true"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ---------- Email عبر Gmail (disabled by default) ----------
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").strip().lower() == "true"
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")                                   # إيميل Gmail المرسل
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "")        # App Password
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "465"))   # 465 (SSL) أو 587 (STARTTLS) إذا 465 محجوب بالشبكة

# ---------- Domain constants ----------
CATEGORIES = ["Software", "Hardware", "Network", "Authentication", "General", "Other"]
PRIORITIES = ["HIGH", "MEDIUM", "LOW"]

# Agent actions 
ACTIONS = [
    "validate_ticket", "classify_ticket", "assess_priority",
    "ask_for_info", "draft_response", "escalate", "finish",
]

# Ticket states
STATUSES = [
    "RECEIVED", "VALIDATED", "WAITING_FOR_INFO", "CLASSIFIED", "DRAFT_READY",
    "ESCALATED", "PENDING_HUMAN_REVIEW", "APPROVED", "REJECTED", "CLOSED",
]

# ---------- Input rules ----------
MIN_MESSAGE_CHARS = 10      # letters/digits, whitespace does not count
MAX_MESSAGE_CHARS = 2000
MAX_FIELD_CHARS = 100       # customer_id, department, ...

# ----------  Conversation context ----------
CONTEXT_WINDOW = 6          # عدد آخر الرسائل اللي بنرسلها للنموذج (Sliding Window)
MAX_CONTEXT_CHARS = 500     # قص أي رسالة طويلة بالـ history قبل إرسالها
MAX_FOLLOW_UPS = 3          #   أقصى عدد أسئلة متابعة قبل ما القرار يصير (أو يروح لموظف)

# ---------- UI ----------
DRAFT_LABEL = "Draft — Human Review Required"
