# ICHIRO Assistant

A powerful command-line RAG (Retrieval-Augmented Generation) system for querying documentation and codebases using AI. Built for ICHIRO robotics research team at ITS (Institut Teknologi Sepuluh Nopember).

## Features

- 📚 **Document RAG System**: Query HTML documentation with semantic search
- 💻 **Codebase Analysis**: Intelligent code search and analysis with agentic workflows
- 🤖 **Multiple Query Modes**: Search, Ask, and Teach modes for different use cases
- 🔄 **Iterative Refinement**: Automatically refines searches for better answers
- 🧠 **Conversation Memory**: Maintains context across multiple queries
- 🌐 **GitHub Integration**: Direct repository fetching and analysis

### Quick one-liner setup

Run the setup script for CPU (smaller environment size):

```bash
curl -fsSL https://raw.githubusercontent.com/masterzaff/agentic-rag-ichiro/main/setup-cpu.sh -o setup.sh && bash setup.sh
```

Run the setup script for GPU (faster execution time):

```bash
curl -fsSL https://raw.githubusercontent.com/masterzaff/agentic-rag-ichiro/main/setup-gpu.sh -o setup.sh && bash setup.sh
```

This fetches setup.sh, copies .env.example to .env if missing, creates .venv, and installs requirements. You can swap the URL for your own gist/raw link if you prefer.

## Read the full docs

You can read the full docs [here](DOCS.md).