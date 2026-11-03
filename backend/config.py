import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COURSES_DIR = ROOT / "data" / "courses"
AUTH_FILE = ROOT / "data" / "account.json"
SECRET_FILE = ROOT / "data" / "session-secret"
DEFAULT_API_URL = os.getenv("RAG_TUTOR_API_URL", "https://openwebui.uni-freiburg.de/api")
COOKIE_SECURE = os.getenv("RAG_TUTOR_COOKIE_SECURE", "0") == "1"
