import json
import re
import time
from typing import Callable
import utils.config as config
from utils.functions import log


def should_search_codebase(query: str, file_memory: dict, chat_fn: Callable) -> dict:
    """Decide whether to search the codebase, use cached files, or answer directly.

    chat_fn: callable(prompt, model, ctx, history=None) -> str
    """
    memory_info = ""
    if file_memory:
        memory_info = "\n\nCurrently loaded files in memory:\n" + "\n".join(
            [f"- {path}" for path in file_memory.keys()]
        )

    prompt = f"""You are a query classifier for a code analysis assistant. Determine if the user's query requires searching and analyzing code files, or can be answered directly with general programming knowledge.

User Query: {query}{memory_info}

Instructions:
- Respond "SEARCH_CODE" if the query asks about:
  * Specific implementation details in THIS codebase
  * How a particular feature works in THIS project
  * Where something is located in the code
  * Code structure, architecture, or organization
  * Debugging or understanding existing code
  * Files that might be relevant to a problem

- Please note that the assistant cannot directly access the codebase unless instructed to search it, so if the query requires anything from the codebase, it must be classified as "SEARCH_CODE".
  
- Respond "USE_MEMORY" if the query references information from currently loaded files (follow-up questions)

- Respond "DIRECT" if the query is:
  * General programming questions not specific to this codebase
  * Theoretical or conceptual programming questions
  * Requests for code examples or tutorials
  * Greetings or casual conversation
  * Questions about programming best practices in general


Respond in JSON format:
{{"action": "SEARCH_CODE|USE_MEMORY|DIRECT", "reason": "brief explanation"}}"""

    try:
        response = chat_fn(prompt, config.HELPER_MODEL, config.HELPER_CTX_WINDOW)
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        if "SEARCH_CODE" in response.upper():
            return {"action": "SEARCH_CODE", "reason": "requires codebase analysis"}
        elif "USE_MEMORY" in response.upper():
            return {"action": "USE_MEMORY", "reason": "references loaded files"}
        else:
            return {"action": "DIRECT", "reason": "general programming question"}
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parsing error in query classification: {e}")
        return {"action": "SEARCH_CODE", "reason": "classification uncertain"}
    except Exception as e:
        print(f"Warning: Error in query classification: {e}")
        return {"action": "SEARCH_CODE", "reason": "classification uncertain"}


def assess_code_confidence(
    query: str, files: list[dict], answer: str, chat_fn: Callable
) -> dict:
    """Assess confidence of an answer given file contexts. Returns JSON-like dict."""
    files_summary = "\n".join([f"- {f['path']}" for f in files])

    prompt = f"""You are assessing whether a code analysis answer is well-supported by the provided files.

Question: {query}
Answer: {answer}

Files analyzed:
{files_summary}

Instructions:
1. Rate confidence: HIGH, MEDIUM, or LOW
   - HIGH: Answer is directly supported by the code with clear evidence
   - MEDIUM: Answer is partially supported but might need more files or context
   - LOW: Answer is not well-supported or important files might be missing

2. If confidence is not HIGH, suggest:
   - Additional file names that might help (be specific if possible)
   - OR a refined search query to find the needed code
   - OR specific aspects that need more investigation

Respond in JSON format:
{{"confidence": "HIGH|MEDIUM|LOW", "reason": "brief explanation", "suggestion": "what to search next or null"}}"""

    try:
        response = chat_fn(prompt, config.HELPER_MODEL, config.HELPER_CTX_WINDOW)
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        if "HIGH" in response.upper():
            return {
                "confidence": "HIGH",
                "reason": "well supported",
                "suggestion": None,
            }
        elif "LOW" in response.upper():
            return {
                "confidence": "LOW",
                "reason": "insufficient context",
                "suggestion": query,
            }
        else:
            return {
                "confidence": "MEDIUM",
                "reason": "partial support",
                "suggestion": None,
            }
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parsing error in confidence assessment: {e}")
        return {
            "confidence": "MEDIUM",
            "reason": "assessment failed",
            "suggestion": None,
        }
    except Exception as e:
        print(f"Warning: Error in confidence assessment: {e}")
        return {
            "confidence": "MEDIUM",
            "reason": "assessment failed",
            "suggestion": None,
        }


def agentic_code_search(
    query: str,
    files: list,
    file_index: list[dict],
    file_memory: dict,
    history: list = None,
    max_iterations: int = 3,
    chat_fn: Callable = None,
) -> tuple[str, list[dict], dict]:
    """Iteratively search and analyze code until confident.

    chat_fn is required and must match chat_llm signature used in the project.
    Returns: (answer, analyzed_files, file_memory)
    """
    if chat_fn is None:
        raise ValueError("chat_fn (LLM caller) must be provided to agentic_code_search")

    all_file_contents = []
    seen_paths = set()
    current_query = query

    for iteration in range(1, max_iterations + 1):
        if iteration > 1:
            print(f"Refining search (iteration {iteration}): {current_query}")

        # STAGE 1: LLM selects files
        file_list = []
        for idx, file_info in enumerate(file_index):
            file_list.append(
                f"{idx+1}. {file_info['path']} ({file_info['lines']} lines, {file_info['extension']})"
            )

        files_overview = "\n".join(file_list[:200])
        if len(file_index) > 200:
            files_overview += f"\n... and {len(file_index) - 200} more files"

        # Show what we already have
        already_loaded = ""
        if seen_paths:
            already_loaded = "\n\nFiles already analyzed in this search:\n" + "\n".join(
                [f"- {p}" for p in seen_paths]
            )

        memory_context = ""
        if file_memory:
            cached = set(file_memory.keys()) - seen_paths
            if cached:
                memory_context = (
                    "\n\nFiles in cache (available instantly):\n"
                    + "\n".join([f"- {p}" for p in cached])
                )

        selection_prompt = f"""You are a code analysis assistant helping to find relevant files.

Available files:
{files_overview}{already_loaded}{memory_context}

User Question: {current_query}

Task: Select up to 3 NEW files that would help answer this question.
- Focus on files NOT already analyzed
- Prefer files from cache if they're relevant
- Consider file names, extensions, and typical project structure
- If you have enough information from already analyzed files, return empty list

Respond in JSON format:
{{"files": ["path1", "path2"], "reasoning": "why these files", "sufficient": true/false}}

Set "sufficient": true if already analyzed files are enough to answer the question."""

        selection_response = chat_fn(
            selection_prompt, config.HELPER_MODEL, config.HELPER_CTX_WINDOW
        )

        # Parse response
        selected_files = []
        sufficient = False
        try:
            json_match = re.search(r"\{[^{}]*\}", selection_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                selected_files = data.get("files", [])
                sufficient = data.get("sufficient", False)
                reasoning = data.get("reasoning", "")
                if reasoning and iteration == 1:
                    print(f"Selection: {reasoning}")
        except json.JSONDecodeError as e:
            print(f"Warning: JSON parsing error in file selection: {e}")
            # Fallback: crude extraction
            for file_info in file_index:
                if (
                    file_info["path"] in selection_response
                    and file_info["path"] not in seen_paths
                ):
                    selected_files.append(file_info["path"])
        except Exception as e:
            print(f"Warning: Error in file selection: {e}")
            # Fallback: crude extraction
            for file_info in file_index:
                if (
                    file_info["path"] in selection_response
                    and file_info["path"] not in seen_paths
                ):
                    selected_files.append(file_info["path"])

        # Limit to 3 new files per iteration
        selected_files = [f for f in selected_files[:3] if f not in seen_paths]

        if not selected_files and iteration == 1:
            return (
                "I couldn't identify any relevant files for this query.",
                [],
                file_memory,
            )

        if sufficient or not selected_files:
            # LLM thinks we have enough info
            if iteration > 1:
                print(f"Sufficient context gathered")
            break

        # STAGE 2: Load the selected files
        if iteration == 1:
            print(f"Loading {len(selected_files)} files...")
        else:
            print(f"Loading {len(selected_files)} additional files...")

        for file_path in selected_files:
            if file_path in file_memory:
                content = file_memory[file_path]
                print(f"  - {file_path} (cached)")
            else:
                try:
                    full_path = config.CODEBASE_DIR / file_path
                    if full_path.exists():
                        with open(
                            full_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()

                        if len(content) > 8000:
                            content = (
                                content[:6000]
                                + f"\n\n... (truncated {len(content) - 8000} chars) ...\n\n"
                                + content[-2000:]
                            )

                        file_memory[file_path] = content
                        print(f"  - {file_path} (loaded)")
                    else:
                        print(f"  - {file_path} (not found)")
                        continue
                except UnicodeDecodeError as e:
                    print(f"  - {file_path} (encoding error: {e})")
                    continue
                except PermissionError as e:
                    print(f"  - {file_path} (permission denied: {e})")
                    continue
                except Exception as e:
                    print(f"  - {file_path} (error: {e})")
                    continue

            all_file_contents.append({"path": file_path, "content": content})
            seen_paths.add(file_path)

        if not all_file_contents:
            return "Could not load any relevant files.", [], file_memory

        # STAGE 3: Analyze with LLM
        context_parts = []
        for file_data in all_file_contents:
            context_parts.append(
                f"File: {file_data['path']}\n```\n{file_data['content']}\n```"
            )

        context = "\n\n".join(context_parts)

        analysis_prompt = f"""You are a code analysis assistant. Answer the question based on the provided code files.

Code Context:
{context}

Instructions:
- Provide accurate, detailed analysis based on the code
- Reference specific files, functions, and line numbers when possible
- If information is incomplete, clearly state what's missing
- Consider conversation history for follow-up questions
- Be concise but thorough
- You SHOULD NEVER ask user about the codebase, since you are the one who supposed to know it. But if you really don't know, respond with "I don't know." instead of making up an answer.

User Question: {query}

Answer:"""

        answer = chat_fn(
            analysis_prompt, config.CHAT_MODEL, config.CHAT_CTX_WINDOW, history
        )

        # Assess confidence
        assessment = assess_code_confidence(query, all_file_contents, answer, chat_fn)
        confidence = assessment.get("confidence", "MEDIUM")
        suggestion = assessment.get("suggestion")

        if iteration > 1 or confidence != "HIGH":
            print(f"Confidence: {confidence}")

        if confidence == "HIGH" or iteration == max_iterations:
            return answer, all_file_contents, file_memory

        if suggestion and iteration < max_iterations:
            current_query = suggestion
        else:
            return answer, all_file_contents, file_memory

    return answer, all_file_contents, file_memory
