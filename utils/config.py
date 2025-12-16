import re
import os
from pathlib import Path

# Paths
WORK_DIR = Path(__file__).parent
TMP_DIR = WORK_DIR / "rag_tmp"
HTML_DIR = TMP_DIR / "html"
DATA_DIR = TMP_DIR / "data"
TEMP_EXTRACT_DIR = TMP_DIR / "extract"
INDEX_FILE = HTML_DIR / "index.html"
OUT_JSONL = TMP_DIR / "chunks.jsonl"
OUT_INDEX = TMP_DIR / "index.faiss"
CODEBASE_DIR = TMP_DIR / "codebase"

# Embedding config (env overrides)
EMB_MODEL = os.getenv("EMB_MODEL", "all-MiniLM-L6-v2")
USE_E5 = EMB_MODEL.startswith("intfloat/e5")
MAX_CHARS = int(os.getenv("MAX_CHARS", "1200"))
OVERLAP = int(os.getenv("OVERLAP", "150"))

# Query config
TOP_K = int(os.getenv("TOP_K", "5"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "3"))

# LLM Provider config
# Set USE_EXTERNAL_API to True to use OpenAI-compatible API
# Set to False to use local Ollama
USE_EXTERNAL_API = os.getenv("USE_EXTERNAL_API", "False").lower() in (
    "true",
    "1",
    "yes",
)

# Ollama config (used when USE_EXTERNAL_API = False)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# External API config (used when USE_EXTERNAL_API = True)
# OpenAI-compatible endpoint
EXTERNAL_API_URL = os.getenv(
    "EXTERNAL_API_URL", "https://api.openai.com/v1/chat/completions"
)
EXTERNAL_API_KEY = os.getenv("EXTERNAL_API_KEY") or os.getenv("OPENAI_API_KEY", "")

# Model configuration
CHAT_MODEL = os.getenv(
    "CHAT_MODEL", "llama3.1"
)  # For Ollama: "llama3.1", For OpenAI: "gpt-4", "gpt-3.5-turbo"
CHAT_CTX_WINDOW = int(os.getenv("CHAT_CTX_WINDOW", "16000"))
HELPER_MODEL = os.getenv(
    "HELPER_MODEL", "mistral"
)  # For Ollama: "mistral", For OpenAI: "gpt-3.5-turbo"
HELPER_CTX_WINDOW = int(os.getenv("HELPER_CTX_WINDOW", "4096"))
HISTORY_LENGTH = int(os.getenv("HISTORY_LENGTH", "4"))

# Cleaning config
LINK_MODE = os.getenv("LINK_MODE", "wiki")  # one of: wiki | title | url | strip
INTERNAL_LINK_RE = re.compile(r"^[./]*([^?#]+\.html)(?:[#?].*)?$", re.I)

# Global flags
BOT_NAME = os.getenv("BOT_NAME", "ICHIRO Assistant")
KEEP_INDEX = os.getenv("KEEP_INDEX", "False").lower() in ("true", "1", "yes")
VERBOSE = os.getenv("VERBOSE", "False").lower() in ("true", "1", "yes")
MODE = int(os.getenv("MODE", "1"))  # 1: search mode, 2: ask mode, 3: teach mode
CODEBASE_FLAG = os.getenv("CODEBASE_FLAG", "False").lower() in ("true", "1", "yes")
