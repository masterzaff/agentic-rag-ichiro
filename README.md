# ICHIRO Assistant — Kaito（解人）

Kaito（解人） is ICHIRO's AI assistant designed to help engineers understand documentation and codebases through intelligent querying. It is a command-line RAG (Retrieval-Augmented Generation) system supporting multiple LLM backends, built for the ICHIRO robotics research team at ITS (Institut Teknologi Sepuluh Nopember).

## Features

- 📚 **HTML Documentation RAG**: Query HTML documentation with semantic search and intelligent retrieval
- 💻 **Agentic Codebase Analysis**: Multi-iteration intelligent file selection and code analysis with conversation memory
- 🤖 **Multiple Query Modes**: Search, Ask, and Teach modes for documentation queries
- 🔄 **Iterative Refinement**: Automatically selects relevant files across iterations for comprehensive answers
- 🧠 **Conversation Memory**: Maintains context and file cache across multiple queries within a session
- 🌐 **GitHub Integration**: Fetch and analyze GitHub repositories directly
- 🔌 **Flexible LLM Support**: Local Ollama or external OpenAI-compatible APIs (OpenAI, Azure, etc.)

## Quick Setup

Run the setup script for CPU (smaller environment size):

```bash
curl -fsSL https://raw.githubusercontent.com/ichiro-its/kaito/main/setup-cpu.sh | bash
```

Run the setup script for GPU (faster execution time):

```bash
curl -fsSL https://raw.githubusercontent.com/ichiro-its/kaito/main/setup-gpu.sh | bash
```

Setup scripts will:
- Copy `.env.example` to `.env` (if needed)
- Create and activate virtual environment (`venv`)
- Install appropriate dependencies (CPU or GPU)

## Read the Full Documentation

For detailed installation, usage, and architecture information, see [DOCS.md](DOCS.md).
