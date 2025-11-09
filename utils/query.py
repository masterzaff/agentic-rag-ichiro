import json
import re
import requests
import time
from sentence_transformers import SentenceTransformer
import faiss
import utils.config as config
from utils.functions import log


def load_rag_system():
    """Load the RAG system (index + chunks)."""
    if not config.OUT_INDEX.exists() or not config.OUT_JSONL.exists():
        log("Error: Index or JSONL file not found", echo=True)
        return None, None, None

    try:
        store = [json.loads(x) for x in open(config.OUT_JSONL, encoding="utf-8")]
        index = faiss.read_index(str(config.OUT_INDEX))
        emb = SentenceTransformer(config.EMB_MODEL)
        log(f"Loaded {len(store)} chunks", echo=True)
        return store, index, emb
    except json.JSONDecodeError as e:
        log(f"Error: Failed to parse JSONL file - {e}", echo=True)
        return None, None, None
    except Exception as e:
        log(f"Error: Failed to load RAG system - {e}", echo=True)
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
        log(f"Error during retrieval: {e}", echo=True)
        return []


def chat_llm(
    prompt: str, model=config.CHAT_MODEL, ctx=config.CHAT_CTX_WINDOW, history=None
) -> str:
    """Send prompt to Ollama and get response."""
    messages = []
    if history:
        for h in history:
            messages.append({"role": "user", "content": h["user"]})
            messages.append({"role": "assistant", "content": h["assistant"]})
    messages.append({"role": "user", "content": prompt})

    try:
        r = requests.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"num_ctx": ctx},
            },
            timeout=180,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            log("Error: Request timed out", echo=True)
        elif "connection" in error_msg.lower():
            log("Error: Cannot connect to Ollama", echo=True)
        else:
            log(f"Error: {error_msg}", echo=True)
        return f"Error: {error_msg}"


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
        log(f"Warning: JSON parsing error in query classification: {e}", echo=False)
        return {"action": "SEARCH", "reason": "classification uncertain"}
    except Exception as e:
        log(f"Warning: Error in query classification: {e}", echo=False)
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
        log(f"Warning: JSON parsing error in confidence assessment: {e}", echo=False)
        return {
            "confidence": "MEDIUM",
            "reason": "assessment failed",
            "follow_up_query": None,
        }
    except Exception as e:
        log(f"Warning: Error in confidence assessment: {e}", echo=False)
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
            log(f"Refining (iteration {iteration}): {current_query}", echo=True)

        chunks = retrieve(current_query, store, index, emb, config.TOP_K)
        if not chunks:
            if iteration == 1:
                return "I don't know - no relevant information found.", []
            break

        new_chunks = [c for c in chunks if c.get("id") and c["id"] not in seen_ids]
        all_chunks.extend(new_chunks)
        seen_ids.update(c["id"] for c in new_chunks if "id" in c)

        if iteration == 1:
            log(f"Retrieved {len(new_chunks)} chunks", echo=True)
        elif new_chunks:
            log(f"Found {len(new_chunks)} more chunks", echo=True)

        answer = chat_llm(
            build_prompt(query, all_chunks, iteration, config.MODE), history=history
        )

        if not answer or answer.startswith("Error:"):
            log(f"Error getting response from LLM", echo=True)
            return (
                "I encountered an error while processing your query. Please try again.",
                all_chunks,
                start_time,
            )

        assessment = assess_confidence(query, all_chunks, answer)
        confidence = assessment.get("confidence", "MEDIUM")
        follow_up = assessment.get("follow_up_query")

        if iteration > 1 or confidence != "HIGH":
            log(f"Confidence: {confidence}", echo=True)

        if confidence == "HIGH" or iteration == max_iterations:
            return answer, all_chunks, start_time

        if follow_up and follow_up != current_query:
            current_query = follow_up
        else:
            return answer, all_chunks, start_time

    return answer, all_chunks, start_time


def query_mode(store, index, emb):
    """Interactive query mode."""
    log(
        f"\nRAG ready with {len(store)} chunks. Ctrl+C or '/quit' to exit. '/mode' to change query mode.\n",
        echo=True,
    )

    # Conversation history (keep last N exchanges)
    history = []

    while True:
        q = input("Query: ").strip()
        if not q:
            continue

        if q.lower().startswith("/"):
            if q.lower().startswith("/exit") or q.lower().startswith("/quit"):
                log("Exiting query mode.", echo=True)
                break
            elif q.lower().startswith("/mode"):
                while True:
                    mode_input = input(
                        "\nSelect mode: 1) Search 2) Ask 3) Teach: "
                    ).strip()
                    if mode_input in ("1", "2", "3"):
                        config.MODE = int(mode_input)
                        print(f"Switched to mode {config.MODE}\n")
                        break
                    print("Invalid. Enter 1, 2, or 3.")
                continue
            else:
                log("Unknown command.\n", echo=True)
                continue

        log("", echo=True)
        decision = should_search_kb(q)
        action = decision.get("action", "SEARCH")

        if action == "DIRECT":
            log("Mode: Direct response", echo=True)
            chat_start = time.time() if config.VERBOSE else None
            direct_prompt = f"""You are {config.BOT_NAME}, an intelligent assistant that helps users find information and answer questions about ICHIRO's knowledge base. ICHIRO is a research team from ITS (Institut Teknologi Sepuluh Nopember) that is dedicated to humanoid robotics research. Answer the following query in a friendly and conversational manner. Consider the conversation history to understand follow-up questions and references.

Query: {q}

Answer:"""
            answer = chat_llm(direct_prompt, history=history)
            if config.VERBOSE:
                chat_elapsed = time.time() - chat_start
                log(f"\n{answer} [chat: {chat_elapsed:.2f}s]\n", echo=True)
            else:
                log(f"\n{answer}\n", echo=True)
        else:
            log("Mode: RAG search", echo=True)
            answer, chunks, start_time = agentic_rag(
                q, store, index, emb, history=history
            )
            unique_docs = len(set(c["doc_id"] for c in chunks))
            if config.VERBOSE:
                elapsed = time.time() - start_time
                log(
                    f"\nAnswer (from {len(chunks)} chunks, {unique_docs} docs):\n{answer} [RAG: {elapsed:.2f}s]\n",
                    echo=True,
                )
            else:
                log(
                    f"\nAnswer (from {len(chunks)} chunks, {unique_docs} docs):\n{answer} \n",
                    echo=True,
                )

        # Add to history (keep only main messages, not full context)
        history.append(
            {
                "user": q,
                "assistant": answer[:500],  # Truncate long answers to save context
            }
        )

        # Keep only last N exchanges
        if len(history) > config.HISTORY_LENGTH:
            history.pop(0)


from utils.codeagent import should_search_codebase, agentic_code_search


def query_code():
    """Interactive codebase query mode with intelligent file selection and memory."""
    from utils.codecontext import codebase_ls
    from pathlib import Path

    files = codebase_ls()
    if not files:
        log("No code files found in codebase.", echo=True)
        return

    log(
        f"\nCodebase query ready with {len(files)} files. Type '/help' for commands.\n",
        echo=True,
    )

    # File content memory cache (path -> content)
    file_memory = {}

    # Conversation history
    history = []

    # Build file index with metadata (done once at startup)
    log("Building file index...", echo=True)
    file_index = []
    for file_path in files:
        try:
            full_path = config.CODEBASE_DIR / file_path
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                # Store basic metadata
                file_index.append(
                    {
                        "path": file_path,
                        "size": len(content),
                        "lines": content.count("\n") + 1,
                        "extension": Path(file_path).suffix,
                        # First 500 chars for preview
                        "preview": content[:500] if len(content) > 500 else content,
                    }
                )
        except Exception as e:
            log(f"Warning: Failed to index {file_path}: {e}", echo=False)
            pass

    log(f"Indexed {len(file_index)} files", echo=True)

    while True:
        q = input("Code Query: ").strip()
        if not q:
            continue

        # Handle commands
        if q.lower().startswith("/"):
            if q.lower().startswith("/exit") or q.lower().startswith("/quit"):
                log("Exiting codebase query mode.", echo=True)
                break
            elif q.lower().startswith("/help"):
                log("\nAvailable commands:", echo=True)
                log(
                    "  /ls [path]       - List files (optionally in a specific path)",
                    echo=True,
                )
                log("  /read <file>     - Read a specific file", echo=True)
                log("  /search <term>   - Search for files containing term", echo=True)
                log("  /tree            - Show directory tree", echo=True)
                log("  /memory          - Show cached files in memory", echo=True)
                log("  /clear           - Clear file memory cache", echo=True)
                log("  /help            - Show this help", echo=True)
                log("  /exit or /quit   - Exit codebase query mode\n", echo=True)
                continue
            elif q.lower().startswith("/memory"):
                if file_memory:
                    log(f"\nCached files ({len(file_memory)}):", echo=True)
                    for path in file_memory.keys():
                        log(f"  {path}", echo=True)
                else:
                    log("\nNo files in memory cache.", echo=True)
                log("", echo=True)
                continue
            elif q.lower().startswith("/clear"):
                file_memory.clear()
                log("Memory cache cleared.\n", echo=True)
                continue
            elif q.lower().startswith("/ls"):
                parts = q.split(maxsplit=1)
                rel_path = parts[1] if len(parts) > 1 else ""
                files_in_path = codebase_ls(rel_path)
                if files_in_path:
                    log(f"\nFiles in '{rel_path or '/'}':", echo=True)
                    for f in files_in_path[:50]:
                        log(f"  {f}", echo=True)
                    if len(files_in_path) > 50:
                        log(
                            f"  ... and {len(files_in_path) - 50} more files", echo=True
                        )
                else:
                    log(f"No files found in '{rel_path}'", echo=True)
                log("", echo=True)
                continue
            elif q.lower().startswith("/read"):
                parts = q.split(maxsplit=1)
                if len(parts) < 2:
                    log("Usage: /read <filename>\n", echo=True)
                    continue
                filename = parts[1].strip()
                file_path = config.CODEBASE_DIR / filename
                if not file_path.exists():
                    log(f"File not found: {filename}\n", echo=True)
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    log(f"\n--- {filename} ---", echo=True)
                    log(content, echo=True)
                    log(f"--- End of {filename} ---\n", echo=True)
                except Exception as e:
                    log(f"Error reading file: {e}\n", echo=True)
                continue
            elif q.lower().startswith("/search"):
                parts = q.split(maxsplit=1)
                if len(parts) < 2:
                    log("Usage: /search <term>\n", echo=True)
                    continue
                search_term = parts[1].strip().lower()
                matching_files = []
                for file_path in files:
                    try:
                        full_path = config.CODEBASE_DIR / file_path
                        with open(
                            full_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read().lower()
                            if search_term in content:
                                matching_files.append(file_path)
                    except Exception as e:
                        log(f"Warning: Failed to search {file_path}: {e}", echo=False)
                        pass
                if matching_files:
                    log(
                        f"\nFound '{search_term}' in {len(matching_files)} files:",
                        echo=True,
                    )
                    for f in matching_files[:20]:
                        log(f"  {f}", echo=True)
                    if len(matching_files) > 20:
                        log(
                            f"  ... and {len(matching_files) - 20} more files",
                            echo=True,
                        )
                else:
                    log(f"No files found containing '{search_term}'", echo=True)
                log("", echo=True)
                continue
            elif q.lower().startswith("/tree"):
                log("\nDirectory structure:", echo=True)
                from collections import defaultdict

                tree = defaultdict(list)
                for f in files:
                    parts = Path(f).parts
                    if len(parts) > 1:
                        parent = str(Path(*parts[:-1]))
                        tree[parent].append(parts[-1])
                    else:
                        tree["root"].append(f)

                if tree["root"]:
                    log("  /", echo=True)
                    for f in sorted(tree["root"])[:10]:
                        log(f"    {f}", echo=True)

                for dir_path in sorted(tree.keys())[:20]:
                    if dir_path != "root":
                        log(f"  {dir_path}/", echo=True)
                        for f in sorted(tree[dir_path])[:5]:
                            log(f"    {f}", echo=True)
                        if len(tree[dir_path]) > 5:
                            log(
                                f"    ... and {len(tree[dir_path]) - 5} more files",
                                echo=True,
                            )

                if len(tree) > 21:
                    log(f"  ... and {len(tree) - 21} more directories", echo=True)
                log("", echo=True)
                continue
            else:
                log(
                    "Unknown command. Type '/help' for available commands.\n", echo=True
                )
                continue

        # Natural language query about codebase - AGENTIC MODE
        log("", echo=True)

        try:
            # Decide if we need to search code or answer directly
            decision = should_search_codebase(q, file_memory, chat_llm)
            action = decision.get("action", "SEARCH_CODE")
            reason = decision.get("reason", "")

            if action == "DIRECT":
                # Answer with general programming knowledge
                log("Mode: Direct answer (general programming knowledge)", echo=True)
                if reason:
                    log(f"Reason: {reason}", echo=True)

                direct_prompt = f"""You are {config.BOT_NAME}, a helpful programming assistant that helps user with programming questions about a specific codebase which you currently have access to. ICHIRO is a research team from ITS (Institut Teknologi Sepuluh Nopember) that is dedicated to humanoid robotics research, so the codebase most likely relates to robotics, but not always. If user seems confused, tell them to try asking something about the codebase. Answer the following programming question using your general knowledge.

User Question: {q}

Instructions:
- Provide clear, accurate information about programming concepts
- Include code examples if helpful
- Be concise but thorough
- Consider conversation history for context

Answer:"""

                answer = chat_llm(direct_prompt, history=history)
                log(f"\n{answer}\n", echo=True)

                # Add to history
                history.append({"user": q, "assistant": answer[:500]})
                if len(history) > config.HISTORY_LENGTH:
                    history.pop(0)

            elif action == "USE_MEMORY":
                # Use files already in memory
                log("Mode: Using cached files", echo=True)
                if reason:
                    log(f"Reason: {reason}", echo=True)

                if not file_memory:
                    log(
                        "No files in memory. Switching to codebase search...", echo=True
                    )
                    action = "SEARCH_CODE"
                else:
                    # Build context from memory
                    context_parts = []
                    for path, content in file_memory.items():
                        context_parts.append(f"File: {path}\n```\n{content}\n```")

                    context = "\n\n".join(context_parts)

                    memory_prompt = f"""You are a code analysis assistant. Answer based on the previously loaded files.

Code Context:
{context}

Instructions:
- Analyze the code and provide accurate information
- Reference specific files and functions when relevant
- If the loaded files don't contain the answer, say so
- Consider conversation history for follow-up questions

User Question: {q}

Answer:"""

                    answer = chat_llm(memory_prompt, history=history)

                    file_list = ", ".join(file_memory.keys())
                    log(f"\nAnswer (from memory: {file_list}):", echo=True)
                    log(f"{answer}\n", echo=True)

                    # Add to history
                    history.append({"user": q, "assistant": answer[:500]})
                    if len(history) > config.HISTORY_LENGTH:
                        history.pop(0)

            if action == "SEARCH_CODE":
                # Agentic codebase search
                log("Mode: Agentic codebase search", echo=True)
                if reason:
                    log(f"Reason: {reason}", echo=True)

                start_time = time.time() if config.VERBOSE else None

                answer, analyzed_files, file_memory = agentic_code_search(
                    q,
                    files,
                    file_index,
                    file_memory,
                    history,
                    config.MAX_ITERATIONS,
                    chat_llm,
                )

                # Manage memory - keep only recent 10 files
                if len(file_memory) > 10:
                    excess = len(file_memory) - 10
                    for path in list(file_memory.keys())[:excess]:
                        del file_memory[path]

                if analyzed_files:
                    file_list = ", ".join([f["path"] for f in analyzed_files])
                    if config.VERBOSE:
                        elapsed = time.time() - start_time
                        log(
                            f"\nAnswer (analyzed {len(analyzed_files)} files: {file_list}):",
                            echo=True,
                        )
                        log(f"{answer} [Time: {elapsed:.2f}s]\n", echo=True)
                    else:
                        log(
                            f"\nAnswer (analyzed {len(analyzed_files)} files: {file_list}):",
                            echo=True,
                        )
                        log(f"{answer}\n", echo=True)
                else:
                    log(f"\n{answer}\n", echo=True)

                # Add to history
                history.append({"user": q, "assistant": answer[:500]})
                if len(history) > config.HISTORY_LENGTH:
                    history.pop(0)

        except Exception as e:
            log(f"Error processing query: {e}\n", echo=True)
