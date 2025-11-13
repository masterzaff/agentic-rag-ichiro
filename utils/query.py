import time
import utils.config as config
from utils.functions import log, select_mode, chat_llm
from utils.htmlcontext import agentic_rag, should_search_kb


def query_mode(store, index, emb):
    """Interactive query mode."""
    print(
        f"\nRAG ready with {len(store)} chunks. Type '/help' for commands.\n",
    )

    # Conversation history (keep last N exchanges)
    history = []

    while True:
        q = input("Query: ").strip()
        if not q:
            continue

        if q.lower().startswith("/"):
            if q.lower().startswith("/exit") or q.lower().startswith("/quit"):
                print("Exiting query mode.")
                break
            elif q.lower().startswith("/help"):
                print("\nAvailable commands:")
                print("  /mode            - Change query mode")
                print("  /clear           - Clear conversation history")
                print("  /help            - Show this help")
                print("  /exit or /quit   - Exit codebase query mode\n")
                continue
            elif q.lower().startswith("/mode"):
                select_mode()
                continue
            elif q.lower().startswith("/clear"):
                history.clear()
                print("History cleared.\n")
                continue
            else:
                print("Unknown command.\n")
                continue

        print("")
        decision = should_search_kb(q)
        action = decision.get("action", "SEARCH")

        if action == "DIRECT":
            print("Mode: Direct response")
            chat_start = time.time() if config.VERBOSE else None
            direct_prompt = f"""You are {config.BOT_NAME}, an intelligent assistant that helps users find information and answer questions about ICHIRO's knowledge base. ICHIRO is a research team from ITS (Institut Teknologi Sepuluh Nopember) that is dedicated to humanoid robotics research. Answer the following query in a friendly and conversational manner. Consider the conversation history to understand follow-up questions and references.

Query: {q}

Answer:"""
            answer = chat_llm(direct_prompt, history=history)
            if config.VERBOSE:
                chat_elapsed = time.time() - chat_start
                print(f"\n{answer} [chat: {chat_elapsed:.2f}s]\n")
            else:
                print(f"\n{answer}\n")
        else:
            print("Mode: RAG search")
            answer, chunks, start_time = agentic_rag(
                q, store, index, emb, history=history
            )
            unique_docs = len(set(c["doc_id"] for c in chunks))
            if config.VERBOSE:
                elapsed = time.time() - start_time
                print(
                    f"\nAnswer (from {len(chunks)} chunks, {unique_docs} docs):\n{answer} [RAG: {elapsed:.2f}s]\n",
                )
            else:
                print(
                    f"\nAnswer (from {len(chunks)} chunks, {unique_docs} docs):\n{answer} \n",
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
        print("No code files found in codebase.")
        return

    print(
        f"\nCodebase query ready with {len(files)} files. Type '/help' for commands.\n",
    )

    # File content memory cache (path -> content)
    file_memory = {}

    # Conversation history
    history = []

    # Build file index with metadata (done once at startup)
    print("Building file index...")
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
            print(f"Warning: Failed to index {file_path}: {e}")
            pass

    print(f"Indexed {len(file_index)} files")

    while True:
        q = input("Code Query: ").strip()
        if not q:
            continue

        # Handle commands
        if q.lower().startswith("/"):
            if q.lower().startswith("/exit") or q.lower().startswith("/quit"):
                print("Exiting codebase query mode.")
                break
            elif q.lower().startswith("/help"):
                print("\nAvailable commands:")
                print(
                    "  /ls [path]       - List files (optionally in a specific path)",
                )
                print("  /read <file>     - Read a specific file")
                print("  /search <term>   - Search for files containing term")
                print("  /tree            - Show directory tree")
                print("  /memory          - Show cached files in memory")
                print("  /wipe            - Wipe file memory cache")
                print("  /clear           - Clear conversation history")
                print("  /help            - Show this help")
                print("  /exit or /quit   - Exit codebase query mode\n")
                continue
            elif q.lower().startswith("/memory"):
                if file_memory:
                    print(f"\nCached files ({len(file_memory)}):")
                    for path in file_memory.keys():
                        print(f"  {path}")
                else:
                    print("\nNo files in memory cache.")
                print("")
                continue
            elif q.lower().startswith("/wipe"):
                file_memory.clear()
                print("Memory cache wiped.\n")
                continue
            elif q.lower().startswith("/clear"):
                history.clear()
                print("History cleared.\n")
                continue
            elif q.lower().startswith("/ls"):
                parts = q.split(maxsplit=1)
                rel_path = parts[1] if len(parts) > 1 else ""
                files_in_path = codebase_ls(rel_path)
                if files_in_path:
                    print(f"\nFiles in '{rel_path or '/'}':")
                    for f in files_in_path[:50]:
                        print(f"  {f}")
                    if len(files_in_path) > 50:
                        print(f"  ... and {len(files_in_path) - 50} more files")
                else:
                    print(f"No files found in '{rel_path}'")
                print("")
                continue
            elif q.lower().startswith("/read"):
                parts = q.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: /read <filename>\n")
                    continue
                filename = parts[1].strip()
                file_path = config.CODEBASE_DIR / filename
                if not file_path.exists():
                    print(f"File not found: {filename}\n")
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    print(f"\n--- {filename} ---")
                    print(content)
                    print(f"--- End of {filename} ---\n")
                except Exception as e:
                    print(f"Error reading file: {e}\n")
                continue
            elif q.lower().startswith("/search"):
                parts = q.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: /search <term>\n")
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
                        print(f"Warning: Failed to search {file_path}: {e}")
                        pass
                if matching_files:
                    print(
                        f"\nFound '{search_term}' in {len(matching_files)} files:",
                    )
                    for f in matching_files[:20]:
                        print(f"  {f}")
                    if len(matching_files) > 20:
                        print(
                            f"  ... and {len(matching_files) - 20} more files",
                        )
                else:
                    print(f"No files found containing '{search_term}'")
                print("")
                continue
            elif q.lower().startswith("/tree"):
                print("\nDirectory structure:")
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
                    print("  /")
                    for f in sorted(tree["root"])[:10]:
                        print(f"    {f}")

                for dir_path in sorted(tree.keys())[:20]:
                    if dir_path != "root":
                        print(f"  {dir_path}/")
                        for f in sorted(tree[dir_path])[:5]:
                            print(f"    {f}")
                        if len(tree[dir_path]) > 5:
                            print(
                                f"    ... and {len(tree[dir_path]) - 5} more files",
                            )

                if len(tree) > 21:
                    print(f"  ... and {len(tree) - 21} more directories")
                print("")
                continue
            else:
                print("Unknown command. Type '/help' for available commands.\n")
                continue

        # Natural language query about codebase - AGENTIC MODE
        print("")

        try:
            # Decide if we need to search code or answer directly
            decision = should_search_codebase(q, file_memory, chat_llm)
            action = decision.get("action", "SEARCH_CODE")
            reason = decision.get("reason", "")

            if action == "DIRECT":
                # Answer with general programming knowledge
                print("Mode: Direct answer (general programming knowledge)")
                if reason:
                    print(f"Reason: {reason}")

                direct_prompt = f"""You are {config.BOT_NAME}, a helpful programming assistant that helps user with programming questions about a specific codebase which you currently have access to. ICHIRO is a research team from ITS (Institut Teknologi Sepuluh Nopember) that is dedicated to humanoid robotics research, so the codebase most likely relates to robotics, but not always. If user seems confused, tell them to try asking something about the codebase. Answer the following programming question using your general knowledge.

User Question: {q}

Instructions:
- Provide clear, accurate information about programming concepts
- Include code examples if helpful
- Be concise but thorough
- Consider conversation history for context

Answer:"""

                answer = chat_llm(direct_prompt, history=history)
                print(f"\n{answer}\n")

                # Add to history
                history.append({"user": q, "assistant": answer[:500]})
                if len(history) > config.HISTORY_LENGTH:
                    history.pop(0)

            elif action == "USE_MEMORY":
                # Use files already in memory
                print("Mode: Using cached files")
                if reason:
                    print(f"Reason: {reason}")

                if not file_memory:
                    print("No files in memory. Switching to codebase search...")
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
                    print(f"\nAnswer (from memory: {file_list}):")
                    print(f"{answer}\n")

                    # Add to history
                    history.append({"user": q, "assistant": answer[:500]})
                    if len(history) > config.HISTORY_LENGTH:
                        history.pop(0)

            if action == "SEARCH_CODE":
                # Agentic codebase search
                print("Mode: Agentic codebase search")
                if reason:
                    print(f"Reason: {reason}")

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
                        print(
                            f"\nAnswer (analyzed {len(analyzed_files)} files: {file_list}):",
                        )
                        print(f"{answer} [Time: {elapsed:.2f}s]\n")
                    else:
                        print(
                            f"\nAnswer (analyzed {len(analyzed_files)} files: {file_list}):",
                        )
                        print(f"{answer}\n")
                else:
                    print(f"\n{answer}\n")

                # Add to history
                history.append({"user": q, "assistant": answer[:500]})
                if len(history) > config.HISTORY_LENGTH:
                    history.pop(0)

        except Exception as e:
            print(f"Error processing query: {e}\n")
