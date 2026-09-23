import os
from dotenv import load_dotenv

load_dotenv()


def _clean_base_url(value: str, default: str = "http://localhost:8000") -> str:
    """
    Normaliza la URL base del backend.

    Local:
        http://localhost:8000

    Docker:
        http://backend:8000
    """
    value = (value or default).strip()

    if not value:
        value = default

    return value.rstrip("/")


# ─── URLs Y ENDPOINTS ────────────────────────────────────────────────────

INSTAGRAM_LOGIN_URL = "https://www.instagram.com/accounts/login/"
INSTAGRAM_HOME_URL = "https://www.instagram.com/"
INSTAGRAM_EXPLORE_URL = "https://www.instagram.com/explore/"
INSTAGRAM_NOTIFICATIONS_URL = "https://www.instagram.com/notifications/"
INSTAGRAM_DIRECT_URL = "https://www.instagram.com/direct/inbox/"
INSTAGRAM_STORIES_CREATE_URL = "https://www.instagram.com/stories/create/"
INSTAGRAM_FOLLOW_REQUESTS_URL = "https://www.instagram.com/accounts/activity/"


# ─── BACKEND API ─────────────────────────────────────────────────────────
# Local:
#   BACKEND_BASE_URL=http://localhost:8000
#
# Docker:
#   BACKEND_BASE_URL=http://backend:8000

BACKEND_BASE_URL = _clean_base_url(
    os.getenv(
        "BACKEND_BASE_URL",
        os.getenv("API_BASE_URL", "http://localhost:8000"),
    )
)

BACKEND_API_BASE_URL = f"{BACKEND_BASE_URL}/api"

BACKEND_TASKS_ENDPOINT = f"{BACKEND_API_BASE_URL}/tasks"
BACKEND_IA_ENDPOINT = f"{BACKEND_API_BASE_URL}/ia"
BACKEND_PENDING_BOTS_ENDPOINT = f"{BACKEND_API_BASE_URL}/pending_bots/"


# ─── WEBSOCKET ───────────────────────────────────────────────────────────
# Local:
#   SOCKET=ws://localhost:8000/ws/
#
# Docker:
#   SOCKET=ws://backend:8000/ws/

SOCKET_URL = (
    os.getenv(
        "SOCKET",
        os.getenv("WS_BASE_URL", "ws://localhost:8000/ws/"),
    )
    .strip()
    .rstrip("/")
    + "/"
)


# ─── SELENIUM REMOTO ─────────────────────────────────────────────────────
# Local:
#   vacío o no definido
#
# Docker:
#   SELENIUM_REMOTE_URL=http://selenium_chrome:4444/wd/hub

SELENIUM_REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL", "").strip()


# ─── TIMEOUTS Y ESPERAS ──────────────────────────────────────────────────

DEFAULT_WAIT_TIMEOUT = 10
LOGIN_WAIT_TIMEOUT = 30
PAGE_LOAD_TIMEOUT = 20
ELEMENT_CLICK_WAIT = 15


# ─── DELAYS Y COMPORTAMIENTO HUMANO ──────────────────────────────────────

MIN_RANDOM_DELAY = 3
MAX_RANDOM_DELAY = 8
MIN_SCROLL_PAUSE = 1
MAX_SCROLL_PAUSE = 4


# ─── REINTENTOS Y BACKOFF ────────────────────────────────────────────────

MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2
RETRY_BACKOFF_MAX = 30


# ─── LÍMITES DE OPERACIONES ──────────────────────────────────────────────

MAX_POSTS_PER_SESSION = 3
MAX_LIKES_PER_SESSION = 10
MAX_COMMENTS_PER_SESSION = 5
MAX_FOLLOWS_PER_SESSION = 10
MAX_UNFOLLOWS_PER_SESSION = 10
MAX_FOLLOW_REQUESTS_ACCEPT = 10


# ─── PATRONES Y VALIDACIÓN ──────────────────────────────────────────────

VALID_IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]
MAX_IMAGE_SIZE_MB = 8
MAX_CAPTION_LENGTH = 2200
MAX_HASHTAGS = 30


# ─── LOGGING Y DEBUG ─────────────────────────────────────────────────────

LOG_LEVEL = "INFO"
LOG_FILE = "logs/bot.log"
ENABLE_SCREENSHOTS_ON_ERROR = True
SCREENSHOT_DIR = "screenshots/"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s (%(lineno)d): %(message)s"


# ─── PROXY Y NAVEGADOR ──────────────────────────────────────────────────

BROWSER_TYPE = "chrome"
HEADLESS_MODE = False
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ─── IA Y GENERACIÓN ─────────────────────────────────────────────────────

IA_MODEL_TEXT = "deepseek-chat"
IA_MODEL_IMAGE = "dall-e-3"
IA_TEMPERATURE = 0.7