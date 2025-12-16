import requests
import utils.config as config
import shutil
import os


def log(msg):
    """Print message if verbose is True."""
    if config.VERBOSE:
        print(msg)


def cleanup_all():
    """Remove temporary files unless --keep flag is set."""
    if config.KEEP_INDEX:
        print("\nKeeping index files")
        return

    print("\nCleaning up...")
    if config.TMP_DIR.exists():
        shutil.rmtree(config.TMP_DIR)
        print(f"Removed {config.TMP_DIR}")


def select_mode():
    while True:
        mode_input = input("\nSelect mode: 1) Search 2) Ask 3) Teach: ").strip()
        if mode_input in ("1", "2", "3"):
            config.MODE = int(mode_input)
            print(f"Selected mode {config.MODE}.\n")
            break
        print("Invalid. Enter 1, 2, or 3.")


def chat_llm(
    prompt: str, model=config.CHAT_MODEL, ctx=config.CHAT_CTX_WINDOW, history=None
) -> str:
    """Send prompt to LLM and get response (supports both Ollama and external APIs)."""
    messages = []
    if history:
        for h in history:
            messages.append({"role": "user", "content": h["user"]})
            messages.append({"role": "assistant", "content": h["assistant"]})
    messages.append({"role": "user", "content": prompt})

    try:
        if config.USE_EXTERNAL_API:
            # Use OpenAI-compatible API
            if not config.EXTERNAL_API_KEY:
                return "Error: API key not set. Set EXTERNAL_API_KEY or OPENAI_API_KEY environment variable, or set EXTERNAL_API_KEY in config.py."

            headers = {
                "Authorization": f"Bearer {config.EXTERNAL_API_KEY}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": ctx,
            }

            r = requests.post(
                config.EXTERNAL_API_URL,
                headers=headers,
                json=payload,
                timeout=180,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        else:
            # Use local Ollama
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
            print("Error: Request timed out")
        elif "connection" in error_msg.lower():
            if config.USE_EXTERNAL_API:
                print("Error: Cannot connect to external API")
            else:
                print("Error: Cannot connect to Ollama")
        else:
            print(f"Error: {error_msg}")
        return f"Error: {error_msg}"


# embed text using Jina API
# def embed_text(text: str):
