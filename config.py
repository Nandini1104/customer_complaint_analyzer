"""Application configuration. Secrets come from environment variables."""
import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "customer_complaints.db")
SECRET_FILE = os.path.join(BASE_DIR, "database", ".secret_key")


def _secret_key():
    """Use SECRET_KEY from the environment; otherwise create and reuse a random local one."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    os.makedirs(os.path.dirname(SECRET_FILE), exist_ok=True)
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(SECRET_FILE, "w") as f:
        f.write(key)
    return key


class Config:
    SECRET_KEY = _secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///" + DB_PATH.replace("\\", "/"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024          # 2 MB upload limit
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"  # set 1 behind HTTPS
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")   # if unset, a random one is generated once
    API_KEY = os.environ.get("API_KEY")                 # if unset, a random one is stored in the DB
    PER_PAGE = 15
