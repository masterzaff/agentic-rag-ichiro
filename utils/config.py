import re
from pathlib import Path

WORK_DIR = Path(__file__).parent
TMP_DIR = WORK_DIR / "rag_tmp"
HTML_DIR = TMP_DIR / "html"
DATA_DIR = TMP_DIR / "data"
TEMP_EXTRACT_DIR = TMP_DIR / "extract"
INDEX_FILE = HTML_DIR / "index.html"
OUT_JSONL = TMP_DIR / "chunks.jsonl"
OUT_INDEX = TMP_DIR / "index.faiss"
CODEBASE_DIR = TMP_DIR / "codebase"

# Embedding config
EMB_MODEL = "all-MiniLM-L6-v2"
USE_E5 = EMB_MODEL.startswith("intfloat/e5")
MAX_CHARS = 1200
OVERLAP = 150

# Query config
TOP_K = 5
MAX_ITERATIONS = 3
OLLAMA_URL = "http://localhost:11434"
CHAT_MODEL = "llama3.1"
CHAT_CTX_WINDOW = 16000
HELPER_MODEL = "mistral"
HELPER_CTX_WINDOW = 4096
HISTORY_LENGTH = 4

# Cleaning config
LINK_MODE = "wiki"  # one of: wiki | title | url | strip
INTERNAL_LINK_RE = re.compile(r"^[./]*([^?#]+\.html)(?:[#?].*)?$", re.I)

# Global flags
BOT_NAME = "ICHIRO Assistant"
KEEP_INDEX = False
VERBOSE = False
MODE = 1  # 1: search mode, 2: ask mode, 3: teach mode
CODEBASE_FLAG = False
