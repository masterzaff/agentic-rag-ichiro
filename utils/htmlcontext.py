import re
import json
import time
import faiss
import utils.config as config
from utils.functions import chat_llm, log
from sentence_transformers import SentenceTransformer
from pathlib import Path
from bs4 import BeautifulSoup, Tag, NavigableString


def load_title_map_from_index(index_path: Path) -> dict[str, str]:
    """Parse index.html for page titles."""
    title_map = {}
    if not index_path.exists():
        return title_map

    try:
        soup = BeautifulSoup(
            index_path.read_text(encoding="utf-8", errors="ignore"), "lxml"
        )
        for a in soup.find_all("a", href=True):
            if m := config.INTERNAL_LINK_RE.match(a["href"]):
                fname = Path(m.group(1)).name
                title_map.setdefault(fname, a.get_text(" ", strip=True) or fname)
    except Exception as e:
        log(f"Warning: Failed to load title map: {e}", echo=False)

    return title_map


def select_main_content(soup: BeautifulSoup) -> Tag:
    """Select main content area."""
    if mc := soup.select_one("#main-content"):
        return mc

    candidates = [
        (len(el.get_text(" ", strip=True)), el)
        for el in soup.find_all(["main", "article", "section", "div"])
        if len(el.get_text(" ", strip=True)) > 300
    ]

    return candidates[0][1] if candidates else (soup.body or soup)


def strip_noise(soup: BeautifulSoup):
    """Remove scripts, styles, and breadcrumbs."""
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    if bc := soup.select_one("#breadcrumbs"):
        bc.decompose()


def rewrite_internal_link(a: Tag, title_map: dict) -> str | None:
    """Turn <a href="something_123.html#..."> into your chosen representation."""
    text = a.get_text(" ", strip=True)
    href = a.get("href", "")
    m = config.INTERNAL_LINK_RE.match(href)
    if not m:
        if href.startswith(("http://", "https://")):
            return f"{text} ({href})" if text else href
        return text

    fname = Path(m.group(1)).name
    title = title_map.get(fname, fname)

    if config.LINK_MODE == "wiki":
        return f"[[{title}]]"
    if config.LINK_MODE == "title":
        return title
    if config.LINK_MODE == "url":
        return f"{title} ({fname})"
    if config.LINK_MODE == "strip":
        return text
    return text


def to_text(root: Tag, title_map: dict) -> str:
    lines = []

    def walk(node):
        if isinstance(node, NavigableString):
            s = str(node)
            if s.strip():
                lines.append(s.strip())
            return
        if not isinstance(node, Tag):
            return

        name = node.name.lower()

        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            title = node.get_text(" ", strip=True)
            underline = "=" if level <= 2 else "-"
            lines.append(title)
            lines.append(underline * len(title))
            lines.append("")
            return

        if name == "p":
            t = node.get_text(" ", strip=True)
            if t:
                lines.append(t)
                lines.append("")
            return

        if name == "pre":
            code = node.get_text("\n", strip=True)
            lines.append("```")
            lines.append(code)
            lines.append("```")
            lines.append("")
            return
        if name == "code":
            lines.append(f"`{node.get_text(strip=True)}`")
            return

        if name in {"ul", "ol"}:
            bullet = "-" if name == "ul" else "1."
            for li in node.find_all("li", recursive=False):
                item = li.get_text(" ", strip=True)
                if item:
                    lines.append(f"{bullet} {item}")
                for child in li.find_all(["ul", "ol"], recursive=False):
                    walk(child)
            lines.append("")
            return

        if name == "table":
            rows = []
            for tr in node.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                lines.append(" | ".join(["---"] * len(rows[0].split(" | "))))
                lines.extend(rows)
                lines.append("")
            return

        if name == "a":
            repl = rewrite_internal_link(node, title_map)
            if repl:
                lines.append(repl)
            return

        if name == "br":
            lines.append("")
            return

        for child in node.children:
            walk(child)

    walk(root)

    out = []
    prev_blank = False
    for ln in lines:
        is_blank = not ln.strip()
        if is_blank and prev_blank:
            continue
        out.append(ln.rstrip())
        prev_blank = is_blank
    return "\n".join(out).strip()


def clean_file(path: Path, title_map: dict) -> str:
    """Clean a single HTML file and return text content."""
    try:
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")
        strip_noise(soup)
        main = select_main_content(soup)

        page_title = (soup.title.string or "").strip() if soup.title else ""
        if not page_title:
            page_title = title_map.get(path.name, path.stem)

        body = to_text(main, title_map)
        if page_title and page_title not in body[:200]:
            body = f"{page_title}\n{'='*len(page_title)}\n\n{body}"

        body = re.sub(r"[ \t]+\n", "\n", body)
        body = re.sub(r"\n{3,}", "\n\n", body)
        return body
    except Exception as e:
        log(f"Warning: Failed to clean {path.name}: {e}", echo=False)
        return ""


def clean_html_files():
    """Clean HTML files and save as text."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    files = [
        p for p in config.HTML_DIR.rglob("*.html") if p.name.lower() != "index.html"
    ]
    if not files:
        log("No HTML files found", echo=True)
        return 0

    title_map = load_title_map_from_index(config.INDEX_FILE)
    log(f"Cleaning {len(files)} HTML files...", echo=True)

    count = 0
    for f in files:
        try:
            if cleaned := clean_file(f, title_map):
                (config.DATA_DIR / f"{f.stem}.txt").write_text(
                    cleaned, encoding="utf-8"
                )
                count += 1
        except Exception as e:
            log(f"Warning: Failed to save {f.name}: {e}", echo=False)

    if count == 0:
        log("No files cleaned", echo=True)
        return 0

    log(f"Cleaned {count} files", echo=True)
    return count


def load_rag_system():
    """Load the RAG system (index + chunks)."""
    if not config.OUT_INDEX.exists() or not config.OUT_JSONL.exists():
        print("Error: Index or JSONL file not found")
        return None, None, None

    try:
        store = [json.loads(x) for x in open(config.OUT_JSONL, encoding="utf-8")]
        index = faiss.read_index(str(config.OUT_INDEX))
        emb = SentenceTransformer(config.EMB_MODEL)
        print(f"Loaded {len(store)} chunks")
        return store, index, emb
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSONL file - {e}")
        return None, None, None
    except Exception as e:
        print(f"Error: Failed to load RAG system - {e}")
        return None, None, None


def qemb(q: str, emb):
    if config.USE_E5:
        q = f"query: {q}"
    v = emb.encode([q], normalize_embeddings=True).astype("float32")
    return v


def retrieve(query: str, store, index, emb, k=config.TOP_K):
    """Retrieve top-k relevant chunks for a query."""
    if not query or not store or index is None or emb is None:
        return []

    try:
        D, I = index.search(qemb(query, emb), k)
        return [store[i] for i in I[0] if i != -1 and 0 <= i < len(store)]
    except Exception as e:
        print(f"Error during retrieval: {e}")
        return []


def should_search_kb(query: str) -> dict:
    """Decide if the query requires searching the knowledge base."""
    prompt = f"""You are a query classifier for {config.BOT_NAME}, an intelligent assistant that helps users find information and answer questions about ICHIRO's knowledge base. ICHIRO is a research team from ITS (Institut Teknologi Sepuluh Nopember) that is dedicated to humanoid robotics research. Determine if the following user query requires searching a technical knowledge base or can be answered directly with general conversation.

User Query: {query}

The knowledge base contains technical documentation, guides, setup instructions, coding standards, and engineering documentation.

Instructions:
- Respond "SEARCH" if the query asks for specific technical information, documentation, how-to guides, or factual knowledge that would be in a knowledge base
- Respond "DIRECT" if the query is a greeting, casual conversation, general question, or doesn't require specific documentation

Examples:
- "hi" → DIRECT (greeting)
- "how are you" → DIRECT (casual)
- "what can you do" → DIRECT or SEARCH (can be either depending on context)
- "how to setup git" → SEARCH (technical)
- "python coding standards" → SEARCH (documentation)
- "tell me about ROS2" → SEARCH (technical knowledge)

Respond in JSON format:
{{"action": "SEARCH|DIRECT", "reason": "brief explanation"}}"""

    try:
        response = chat_llm(prompt, config.HELPER_MODEL, config.HELPER_CTX_WINDOW)
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        if "SEARCH" in response.upper():
            return {"action": "SEARCH", "reason": "requires knowledge base"}
        else:
            return {"action": "DIRECT", "reason": "general conversation"}
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parsing error in query classification: {e}")
        return {"action": "SEARCH", "reason": "classification uncertain"}
    except Exception as e:
        print(f"Warning: Error in query classification: {e}")
        return {"action": "SEARCH", "reason": "classification uncertain"}


def assess_confidence(query: str, chunks: list[dict], answer: str) -> dict:
    """Ask LLM to assess confidence and suggest follow-up queries if needed."""
    ctx = "\n\n".join(f"- {c['text']}" for c in chunks)
    prompt = f"""You are assessing whether an answer is well-supported by the context.

Question: {query}
Answer: {answer}

Context used:
{ctx}

Instructions:
1. Rate confidence: HIGH, MEDIUM, or LOW
   - HIGH: Answer is directly supported by context with clear evidence
   - MEDIUM: Answer is partially supported but missing some details
   - LOW: Answer is not well-supported or context is insufficient

2. If confidence is not HIGH, suggest a follow-up search query that could find missing information. Suggest a search query and NOT a command to search one.

Respond in JSON format:
{{"confidence": "HIGH|MEDIUM|LOW", "reason": "brief explanation", "follow_up_query": "suggested query or null"}}"""

    try:
        response = chat_llm(prompt, config.HELPER_MODEL, config.HELPER_CTX_WINDOW)
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        if "HIGH" in response.upper():
            return {
                "confidence": "HIGH",
                "reason": "parsed from text",
                "follow_up_query": None,
            }
        elif "LOW" in response.upper():
            return {
                "confidence": "LOW",
                "reason": "parsed from text",
                "follow_up_query": query,
            }
        else:
            return {
                "confidence": "MEDIUM",
                "reason": "parsed from text",
                "follow_up_query": query,
            }
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parsing error in confidence assessment: {e}")
        return {
            "confidence": "MEDIUM",
            "reason": "assessment failed",
            "follow_up_query": None,
        }
    except Exception as e:
        print(f"Warning: Error in confidence assessment: {e}")
        return {
            "confidence": "MEDIUM",
            "reason": "assessment failed",
            "follow_up_query": None,
        }


def build_prompt(query: str, chunks: list[dict], iteration: int = 1, mode=1) -> str:
    ctx = "\n\n".join(f"- {c['text']}" for c in chunks)

    # Search Mode
    if mode == 1:
        prompt = f"""You are {config.BOT_NAME}, an intelligent assistant that helps users find information and answer questions about ICHIRO's knowledge base. ICHIRO is a research team from ITS (Institut Teknologi Sepuluh Nopember) that is dedicated to humanoid robotics research. Answer in plain text if possible."""

        if iteration > 1:
            prompt += f" (iteration {iteration})"

        prompt += f"""

    Context from knowledge base:
    {ctx}

    Instructions:
    - Consider the conversation history to understand follow-up questions and references.
    - Check if the context contains information DIRECTLY relevant to the question.
    - If it does, use ONLY that information to answer.
    - If it does not contain relevant information, answer with: "I don't know.", followed by a brief explanation.

    Question: {query}
    Answer:"""

    # Ask Mode
    elif mode == 2:
        prompt = f"""You are {config.BOT_NAME}, an intelligent assistant that answers user questions about ICHIRO's knowledge base. ICHIRO is a research team from ITS (Institut Teknologi Sepuluh Nopember) that is dedicated to humanoid robotics research. Answer in plain text if possible."""

        if iteration > 1:
            prompt += f" (iteration {iteration})"

        prompt += f"""

    Context from knowledge base:
    {ctx}

    Instructions:
    - Consider the conversation history to understand follow-up questions and references.
    - Check if the context contains information DIRECTLY relevant to the question.
    - If it does, use ONLY that information to answer.
    - If it does not contain relevant information, indicate that the information is NOT FOUND in the knowledge base, then answer using your general knowledge if relevant. Answer with: "I don't know.", followed by explanation if you cannot answer.

    Question: {query}
    Answer:"""

    # Teach Mode
    elif mode == 3:
        prompt = f"""You are {config.BOT_NAME}, an intelligent teacher that helps users find information and teach them based on their questions about ICHIRO's knowledge base. ICHIRO is a research team from ITS (Institut Teknologi Sepuluh Nopember) that is dedicated to humanoid robotics research. Answer in plain text if possible."""

        if iteration > 1:
            prompt += f" (iteration {iteration})"

        prompt += f"""

    Context from knowledge base:
    {ctx}

    Instructions:
    - The knowledge base is mostly about learning materials, so your goal is to teach the user based on the provided context.
    - Consider the conversation history to understand follow-up questions and references.
    - Check if the context contains information DIRECTLY relevant to the question.
    - If it does, use that information to tailor your response.
    - If it does not contain relevant information, indicate that the information is NOT FOUND in the knowledge base, then answer using your general knowledge if applicable. If you do not know, answer with: "I don't know.", followed by a brief explanation.

    Question: {query}
    Answer:"""
    return prompt


def agentic_rag(
    query: str, store, index, emb, max_iterations=config.MAX_ITERATIONS, history=None
) -> tuple[str, list[dict]]:
    """Iteratively retrieve and refine until confident."""
    start_time = time.time() if config.VERBOSE else None

    all_chunks = []
    seen_ids = set()
    current_query = query

    for iteration in range(1, max_iterations + 1):
        if iteration > 1:
            print(f"Refining (iteration {iteration}): {current_query}")

        chunks = retrieve(current_query, store, index, emb, config.TOP_K)
        if not chunks:
            if iteration == 1:
                return "I don't know - no relevant information found.", []
            break

        new_chunks = [c for c in chunks if c.get("id") and c["id"] not in seen_ids]
        all_chunks.extend(new_chunks)
        seen_ids.update(c["id"] for c in new_chunks if "id" in c)

        if iteration == 1:
            print(f"Retrieved {len(new_chunks)} chunks")
        elif new_chunks:
            print(f"Found {len(new_chunks)} more chunks")

        answer = chat_llm(
            build_prompt(query, all_chunks, iteration, config.MODE), history=history
        )

        if not answer or answer.startswith("Error:"):
            print(f"Error getting response from LLM")
            return (
                "I encountered an error while processing your query. Please try again.",
                all_chunks,
                start_time,
            )

        assessment = assess_confidence(query, all_chunks, answer)
        confidence = assessment.get("confidence", "MEDIUM")
        follow_up = assessment.get("follow_up_query")

        if iteration > 1 or confidence != "HIGH":
            print(f"Confidence: {confidence}")

        if confidence == "HIGH" or iteration == max_iterations:
            return answer, all_chunks, start_time

        if follow_up and follow_up != current_query:
            current_query = follow_up
        else:
            return answer, all_chunks, start_time

    return answer, all_chunks, start_time
