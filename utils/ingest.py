from utils.functions import log
import utils.config as config
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import hashlib
import json
import re
import time
from pathlib import Path


def read_txt(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def guess_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:200]
    return "Untitled"


def sentence_chunks(
    title: str, text: str, max_chars=config.MAX_CHARS, overlap=config.OVERLAP
):
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    header = title.strip()
    buf, out = "", []
    for s in sents:
        s = s.strip()
        if not s:
            continue
        if len(buf) + 1 + len(s) > max_chars and buf:
            out.append(f"{header}\n{buf.strip()}")
            buf = buf[-overlap:] if overlap else ""
        buf += (" " if buf else "") + s
    if buf.strip():
        out.append(f"{header}\n{buf.strip()}")
    return out


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def embed_passages(model, texts):
    if config.USE_E5:
        texts = [f"passage: {t}" for t in texts]
    embs = model.encode(texts, normalize_embeddings=True)
    return np.asarray(embs, dtype="float32")


def ingest_documents():
    """Build chunks and index from DATA_DIR."""
    files = sorted(config.DATA_DIR.rglob("*.txt"))
    if not files:
        log("No .txt files found", echo=True)
        return False

    log(f"Building chunks from {len(files)} documents...", echo=True)

    # Create chunks
    chunks = []
    for f in files:
        try:
            raw = read_txt(f)
            title = guess_title(raw)
            for i, piece in enumerate(sentence_chunks(title, raw)):
                chunks.append(
                    {
                        "id": f"{f.name}#chunk-{i:04d}",
                        "doc_id": f.name,
                        "title": title,
                        "source": str(f),
                        "lang": "en",
                        "hash": sha1(piece),
                        "text": piece,
                    }
                )
        except Exception as e:
            log(f"Warning: Failed to process {f.name}: {e}", echo=False)

    # Deduplicate
    seen = set()
    unique = []
    for c in chunks:
        if c["hash"] not in seen:
            seen.add(c["hash"])
            unique.append(c)

    if not unique:
        log("No chunks created", echo=True)
        return False

    log(f"Created {len(unique)} chunks", echo=True)

    # Embed & index
    try:
        log(f"Embedding with {config.EMB_MODEL}...", echo=True)
        model = SentenceTransformer(config.EMB_MODEL)
        vecs = embed_passages(model, [c["text"] for c in unique])

        index = faiss.IndexFlatIP(vecs.shape[1])
        index.add(vecs)
        faiss.write_index(index, str(config.OUT_INDEX))

        with open(config.OUT_JSONL, "w", encoding="utf-8") as f:
            for c in unique:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        log(f"Saved {len(unique)} chunks", echo=True)
        return True
    except Exception as e:
        log(f"Error during indexing: {e}", echo=True)
        return False
