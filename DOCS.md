# ICHIRO Assistant — Complete Documentation

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Features & Modes](#features--modes)
6. [Commands Reference](#commands-reference)
7. [Architecture](#architecture)
8. [How It Works](#how-it-works)
9. [Examples](#examples)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Kaito（解人） is ICHIRO's AI-powered assistant for intelligent documentation and codebase querying. It uses Retrieval-Augmented Generation (RAG) for documentation and agentic workflows for code analysis.

### Two Main Query Modes

1. **Documentation Mode**: RAG-based semantic search over HTML documentation with configurable query strategies
2. **Codebase Mode**: Agentic file selection with iterative refinement and conversation memory for code analysis

---

## Installation

### Prerequisites

- Python 3.10 or higher
- Virtual environment (highly recommended): `python3 -m venv venv`
- One of the following LLM providers:
  - **Local**: [Ollama](https://ollama.ai/) with models `llama3.1` and `mistral`
  - **External API**: OpenAI API key or compatible endpoint (Azure OpenAI, etc.)

### Setup Steps

#### Option 1: Automated Setup (Recommended)

**For CPU-only systems:**
```bash
curl -fsSL https://raw.githubusercontent.com/ichiro-its/kaito/main/setup-cpu.sh | bash
```

**For GPU-enabled systems:**
```bash
curl -fsSL https://raw.githubusercontent.com/ichiro-its/kaito/main/setup-gpu.sh | bash
```
*Please note that you may need more storage availabe when setting up with GPU, since system need to install CUDA-compatible packages.*

#### Option 2: Manual Setup

1. Clone the repository:
```bash
git clone https://github.com/masterzaff/agentic-rag-ichiro.git
cd ichiro-assistant
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Copy environment template and configure:
```bash
cp .env.example .env
# Edit .env with your settings (see Configuration section)
```

4. Install dependencies:
```bash
# For CPU systems
pip install -r requirements-cpu.txt

# For GPU systems (CUDA)
pip install -r requirements-gpu.txt
```

---

## Configuration

### Environment Variables (.env file)

All settings can be configured via environment variables in `.env`. Here's a complete reference:

#### LLM Provider Selection

```dotenv
# Use local Ollama (False) or external API (True)
USE_EXTERNAL_API=False
```

#### Ollama Configuration (Local LLM)

```dotenv
# Ollama server URL
OLLAMA_URL=http://localhost:11434
```

**Setup Ollama models:**
```bash
ollama pull llama3.1     # Main chat model
ollama pull mistral      # Helper model for classifications
```

#### External API Configuration (OpenAI-Compatible)

```dotenv
# API key (supports both EXTERNAL_API_KEY and OPENAI_API_KEY)
EXTERNAL_API_KEY=your-api-key-here

# API endpoint (defaults to OpenAI)
EXTERNAL_API_URL=https://api.openai.com/v1/chat/completions

# For Azure OpenAI:
# EXTERNAL_API_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment/chat/completions?api-version=2024-02-01
```

#### Model Configuration

```dotenv
# Main chat model used for queries and RAG responses
CHAT_MODEL=llama3.1

# Context window size for chat model (in tokens)
CHAT_CTX_WINDOW=16000

# Helper model for query classification and confidence assessment
# If not set, defaults to CHAT_MODEL
HELPER_MODEL=mistral

# Context window for helper model
HELPER_CTX_WINDOW=4096

# Number of conversation history exchanges to keep in memory
HISTORY_LENGTH=4
```

#### Embedding & Chunking

```dotenv
# Sentence transformer model for embeddings
# Options: all-MiniLM-L6-v2 (default), intfloat/e5-small, intfloat/e5-base, etc.
EMB_MODEL=all-MiniLM-L6-v2

# Maximum characters per chunk (approximate)
MAX_CHARS=1200

# Character overlap between chunks (for context continuity)
OVERLAP=150
```

#### Retrieval & Iteration

```dotenv
# Number of chunks to retrieve per query
TOP_K=5

# Maximum iterations for agentic code search refinement
MAX_ITERATIONS=3
```

#### HTML Cleaning & Formatting

```dotenv
# How to format internal links in documentation:
# - wiki: [[Page Title]]
# - title: Page Title
# - url: Page Title (filename.html)
# - strip: Plain text (link removed)
LINK_MODE=wiki
```

#### Application Flags

```dotenv
# Bot name for responses
BOT_NAME=ICHIRO Assistant

# Keep index files after exit (speeds up subsequent runs)
KEEP_INDEX=False

# Enable verbose output with timing information
VERBOSE=False

# Default query mode: 1 (Search), 2 (Ask), 3 (Teach)
MODE=1

# (Not currently used)
CODEBASE_FLAG=False
```

---

## Usage

### Basic Command Structure

```bash
# Query HTML documentation from a zip file
python app.py ./docs.zip

# Query specific subfolder within a zip
python app.py ./docs.zip ./html/

# Query a GitHub repository
python app.py https://github.com/owner/repo

# Keep index files for faster subsequent runs
python app.py ./docs.zip --keep

# Enable verbose output with timing
python app.py ./docs.zip --verbose

# Combine flags
python app.py ./docs.zip ./docs/html --keep --verbose
```

### Starting the Application

```bash
# Activate virtual environment
source venv/bin/activate

# Run with your data source
python app.py <input> [options]
```

The app will:
1. Extract and prepare files
2. Build and index chunks
3. Load the RAG system or detect codebase
4. Enter interactive query mode

---

## Features & Modes

### Documentation Query Modes

When querying HTML documentation, you can choose from three modes:

#### Mode 1: Search Mode
- **Behavior**: Answers only from the knowledge base
- **Use case**: When you need accurate, documentation-backed answers
- **Fall-back**: Returns "Not found in documentation" for out-of-scope queries

#### Mode 2: Ask Mode
- **Behavior**: Uses knowledge base first; falls back to general knowledge
- **Use case**: Flexible querying with automatic supplementation
- **Fall-back**: Provides general programming knowledge when documentation doesn't cover topic

#### Mode 3: Teach Mode
- **Behavior**: Provides educational explanations based on documentation context
- **Use case**: Learning and understanding concepts with detailed explanations
- **Fall-back**: Generates teaching content from available context

Switch modes at any time with the `/mode` command.

### Codebase Query Features

#### Agentic File Selection
- LLM intelligently selects up to 3 relevant files per iteration
- Tracks already-analyzed files to avoid redundancy
- Uses file cache to avoid re-reading frequently accessed files
- Continues up to MAX_ITERATIONS (default: 3) for comprehensive analysis

#### File Memory Cache
- Automatically caches loaded files for instant subsequent access
- Manually manage with `/memory` and `/wipe` commands
- File paths remain in cache even between queries
- Files truncated to 8000 chars to preserve memory

#### Conversation History
- Maintains query/answer history within a session
- Automatically truncates long answers (500 char limit per entry)
- Keeps last N exchanges (configurable via HISTORY_LENGTH)
- Clear history with `/clear` command

---

## Commands Reference

### Documentation Query Commands

Available when querying HTML documentation:

```
/mode                    Switch between Search (1), Ask (2), and Teach (3) modes
/clear                   Clear conversation history
/help                    Show available commands
/quit or /exit           Exit query mode
```

### Codebase Query Commands

Available when querying GitHub repos or codebases:

```
/help                    Show all available commands

/ls [path]               List files in optional path
                         Example: /ls src/components

/read <file>             Read complete file content
                         Example: /read utils/helpers.py

/search <term>           Search for files containing term (case-insensitive)
                         Example: /search "ROS2 node"

/tree                    Display directory tree structure
                         Shows up to 20 directories, 10 files per directory

/memory                  Show all cached files in memory
                         Lists number of files and their paths

/wipe                    Clear entire file memory cache
                         Removes all cached file contents from session

/clear                   Clear conversation history
                         Resets context for queries

/quit or /exit           Exit codebase query mode
```

---

## Architecture

### Directory Structure

```
ichiro-assistant/
├── app.py                      # Main entry point
├── requirements-cpu.txt        # CPU dependencies
├── requirements-gpu.txt        # GPU dependencies (CUDA)
├── setup-cpu.sh               # Automated CPU setup
├── setup-gpu.sh               # Automated GPU setup
├── .env.example               # Configuration template
├── README.md                  # Quick start guide
├── DOCS.md                    # This file
│
├── main/
│   ├── codeagent.py          # Agentic code search with iterative refinement
│   ├── codecontext.py        # GitHub repo fetching and codebase setup
│   ├── htmlcontext.py        # HTML processing, RAG system loading, semantic search
│   └── query.py              # Main query loop and mode selection
│
├── utils/
│   ├── config.py             # Configuration management and constants
│   ├── extract.py            # File extraction and RAG system initialization
│   ├── functions.py          # Utility functions (LLM calls, logging)
│   ├── htmlcontext.py        # HTML cleaning and text extraction
│   └── ingest.py             # Document chunking and FAISS indexing
│
└── rag_tmp/                  # Temporary directory (auto-created/cleaned)
    ├── html/                 # Extracted HTML files
    ├── data/                 # Cleaned text files
    ├── codebase/             # Downloaded codebase (if querying repo)
    ├── chunks.jsonl          # Serialized chunks
    └── index.faiss           # FAISS vector index
```

### Data Flow

#### Documentation Query Flow

1. **Input Processing** (`extract.py`)
   - Extract zip or copy folder to `rag_tmp/html/`
   - Detect if input is codebase or documentation

2. **HTML Cleaning** (`htmlcontext.py`)
   - Parse HTML files with BeautifulSoup
   - Remove noise (scripts, styles, breadcrumbs)
   - Convert internal links based on LINK_MODE
   - Extract main content and convert to Markdown-like text
   - Save cleaned text to `rag_tmp/data/`

3. **Document Ingestion** (`ingest.py`)
   - Read all `.txt` files from data directory
   - Split into chunks with overlap (respects MAX_CHARS and OVERLAP)
   - Deduplicate chunks by hash
   - Generate embeddings using SentenceTransformer
   - Build FAISS index for fast similarity search
   - Save chunks to `chunks.jsonl` and index to `index.faiss`

4. **Query Processing** (`query.py` + `htmlcontext.py`)
   - Classify query: DIRECT (general knowledge) or SEARCH (RAG)
   - For RAG queries: retrieve TOP_K chunks via FAISS similarity
   - Assess confidence of retrieved chunks
   - Format retrieved chunks with context
   - Pass to LLM for response generation

#### Codebase Query Flow

1. **Repository Handling** (`codecontext.py`)
   - Parse GitHub URL to extract owner, repo, branch
   - Download archive from GitHub (with fallback to master branch)
   - Extract to `rag_tmp/codebase/` preserving directory structure
   - Build file index with metadata (path, lines, extension, preview)

2. **Agentic Search** (`codeagent.py`)
   - **Iteration Loop** (up to MAX_ITERATIONS):
     - LLM selects up to 3 new files based on query
     - Load selected files from disk or cache
     - Truncate large files (>8000 chars) intelligently
     - Assess confidence: if HIGH or no new files, exit loop
     - For MEDIUM confidence, suggest next search terms
   - Cache all loaded files for instant subsequent access

3. **Response Generation** (`query.py`)
   - Compile all analyzed files and their contents
   - Generate response using cached files as context
   - Update conversation history (last N exchanges)

---

## How It Works

### Semantic Search (Documentation)

1. **Query Embedding**: Convert user query to embedding using SentenceTransformer
2. **FAISS Similarity**: Search index for TOP_K most similar chunks
3. **Context Assembly**: Combine chunks with document IDs and titles
4. **LLM Response**: Pass retrieved context to LLM for synthesis

### Agentic Code Analysis (Codebase)

The system uses multi-round reasoning:

1. **Query Classification**: LLM decides SEARCH_CODE, USE_MEMORY, or DIRECT
2. **File Selection**: LLM examines file list and selects relevant files
3. **Confidence Assessment**: LLM rates answer confidence after each iteration
4. **Iterative Refinement**: Continues searching if confidence is MEDIUM
5. **Suggestion Generation**: If confidence is LOW, suggests next search terms

### Context Window Management

**For Documentation**:
- Maintains conversation history (configurable HISTORY_LENGTH)
- Each history entry truncated to 500 chars
- Allows context-aware follow-up queries

**For Codebase**:
- File memory cache persists within session
- Large files truncated to 6000 + 2000 chars (header + tail)
- Cache available instantly for repeated queries
- Manually cleared with `/wipe` command

---

## Examples

### Querying Documentation

```bash
$ python app.py ./ros2_docs.zip
Loading...
Extracting ros2_docs.zip...
Extracted 45 HTML files
Cleaning 45 HTML files...
Cleaned 45 files
Building chunks from 45 documents...
Created 234 chunks
Embedding with all-MiniLM-L6-v2...
Saved 234 chunks

Loading RAG system...
Loaded 234 chunks

Select mode: 1) Search 2) Ask 3) Teach: 1
Selected mode 1.

RAG ready with 234 chunks. Type '/help' for commands.

Query: How do I create a ROS2 node?

Mode: RAG search
Retrieved 5 chunks
Confidence: HIGH

Answer (from 5 chunks, 3 docs):
To create a ROS2 node, you need to:
1. Import rclpy
2. Initialize the ROS2 client library
3. Create a Node class inheriting from rclpy.node.Node
4. Implement callback methods for subscribers/timers
5. Create a main function to spin the node

Query: /mode
Select mode: 1) Search 2) Ask 3) Teach: 3
Selected mode 3.

Query: Explain how ROS2 differs from ROS1

Mode: RAG search
Retrieved 4 chunks
Confidence: MEDIUM

Answer (educational):
ROS2 is a complete redesign of ROS1 with several key differences:

**Architecture**: ROS2 is built on top of DDS (Data Distribution Service)...
```

### Querying a GitHub Repository

```bash
$ python app.py https://github.com/ros2/examples
Loading...
Fetching repository: https://github.com/ros2/examples
Downloading https://github.com/ros2/examples/archive/refs/heads/main.zip...
Codebase ready

Codebase query ready with 156 files. Type '/help' for commands.
Building file index...
Indexed 156 files

Code Query: How does the minimal publisher example work?

Mode: Agentic codebase search
Selection: Looking for publisher implementation patterns...
Loading 3 files...
  - rclpy/minimal_publisher/setup.py (loaded)
  - rclpy/minimal_publisher/README.md (loaded)
  - rclpy/minimal_publisher/minimal_publisher.py (loaded)

Refining search (iteration 2): Publisher callback and timer setup
Loading 2 additional files...
  - rclpy/minimal_subscriber/minimal_subscriber.py (cached)
  - examples_rclpy_executors/examples_rclpy_executors/callbacks.py (loaded)

Sufficient context gathered

Confidence: HIGH

Answer (analyzed 3 files):
The minimal publisher example demonstrates the core ROS2 pubsub pattern...

Code Query: /memory
Cached files (5):
  - rclpy/minimal_publisher/setup.py
  - rclpy/minimal_publisher/README.md
  - rclpy/minimal_publisher/minimal_publisher.py
  - rclpy/minimal_subscriber/minimal_subscriber.py
  - examples_rclpy_executors/examples_rclpy_executors/callbacks.py
```

### Using Multiple Query Modes

```bash
Query: What is ROS?

Mode: Direct response
ICHIRO is a research team dedicated to robotics...

Query: /mode
Select mode: 1) Search 2) Ask 3) Teach: 1
Selected mode 1.

Query: What is ROS?

Mode: RAG search
Retrieved 0 chunks
Confidence: LOW
No relevant documentation found about "ROS". Try a more specific query.

Query: How do I use ROS2 publishers?

Mode: RAG search
Retrieved 5 chunks
Confidence: HIGH
Answer: To use ROS2 publishers...
```

---

## Troubleshooting

### Common Issues

#### "Error: Cannot connect to Ollama"
- Verify Ollama is running: `ollama serve`
- Check OLLAMA_URL is correct in `.env` (default: http://localhost:11434)
- Ensure models are pulled: `ollama pull llama3.1 mistral`
- On Linux, try: `curl http://localhost:11434/api/tags`

#### "Error: API key not set"
- Set EXTERNAL_API_KEY or OPENAI_API_KEY environment variable
- Verify key has correct permissions and quota
- Test: `curl -H "Authorization: Bearer $EXTERNAL_API_KEY" https://api.openai.com/v1/models`

#### "No HTML files found"
- Check zip file contains `.html` files
- Try specifying target folder: `python app.py ./docs.zip ./docs/html/`
- Verify folder structure matches provided path

#### "Failed to extract: Permission denied"
- Ensure write permissions to current directory
- Try running with full path: `cd /tmp && python /path/to/app.py ...`
- Check disk space available

#### "Request timed out"
- Increase timeout (edit `utils/functions.py` timeout=180 to larger value)
- Check network connectivity
- For large repositories, ensure sufficient internet bandwidth

#### "FAISS index corrupted"
- Delete `rag_tmp/` directory to rebuild index
- Run: `rm -rf rag_tmp/ && python app.py ./docs.zip`

#### "Memory error on large codebase"
- Reduce CHAT_CTX_WINDOW or HELPER_CTX_WINDOW in `.env`
- Set HISTORY_LENGTH=2 to keep less context
- For large repos, query specific areas with `/ls` and `/read`

### Performance Optimization

#### Faster subsequent runs
- Use `--keep` flag to preserve index: `python app.py ./docs.zip --keep`
- Reduces initialization time from ~10s to ~1s

#### Faster embeddings
- Use smaller model: `EMB_MODEL=all-MiniLM-L6-v2` (default)
- Or faster: `EMB_MODEL=all-MiniLM-L6-v2`
- For GPU: Enable CUDA-aware embedding

#### Faster LLM responses
- Use smaller model: `CHAT_MODEL=mistral` (faster than llama3.1)
- Reduce context window: `CHAT_CTX_WINDOW=8000`
- Deploy on GPU if available

#### Reduce memory usage
- Decrease `MAX_CHARS` (default: 1200) for smaller chunks
- Set `KEEP_INDEX=False` to auto-clean after exit
- Clear file cache with `/wipe` in codebase mode

### Debug Mode

Enable verbose output for detailed information:

```bash
# Via command line
python app.py ./docs.zip --verbose

# Via environment
export VERBOSE=True
python app.py ./docs.zip
```

Verbose output includes:
- Timing for each operation (RAG search, LLM calls)
- Model selection and configuration
- File loading and caching information
- Query classification reasoning

---

## API Reference

### Core Functions

#### `extract.add_context(input_path, target_folder)`
Handles input validation and prepares files for querying.

**Parameters:**
- `input_path` (str): Path to .zip file, local directory, or GitHub URL
- `target_folder` (str, optional): Subfolder within zip to extract

**Returns:**
- Tuple: (context_ready: bool, is_codebase: bool)

#### `query.query_mode(store, index, emb)`
Interactive loop for documentation queries.

**Parameters:**
- `store` (list): List of chunks from JSONL
- `index` (faiss.Index): FAISS vector index
- `emb` (SentenceTransformer): Embedding model

#### `query.query_code()`
Interactive loop for codebase queries with agentic file selection.

#### `codeagent.agentic_code_search(query, files, file_index, file_memory, history, max_iterations, chat_fn)`
Performs multi-iteration intelligent file selection and analysis.

**Parameters:**
- `query` (str): User's natural language query
- `files` (list): Available file paths
- `file_index` (list[dict]): File metadata
- `file_memory` (dict): Path -> content cache
- `history` (list, optional): Conversation history
- `max_iterations` (int): Max search refinement cycles
- `chat_fn` (callable): LLM function reference

**Returns:**
- Tuple: (answer: str, analyzed_files: list[dict], file_memory: dict)

---

## Contributing & Customization

### Extending Query Modes

Add new modes in `query.py` by modifying `select_mode()` and `query_mode()` functions.

### Custom Embedding Models

Change `EMB_MODEL` in `.env` to any SentenceTransformer model:
- `all-MiniLM-L6-v2` (default, fast)
- `all-mpnet-base-v2` (higher quality)
- `intfloat/e5-base` (MTEB winners)

### Custom LLM Models

Change `CHAT_MODEL` or `HELPER_MODEL` to any model supported by your provider:
- **Ollama**: `ollama pull <model-name>` then set in `.env`
- **OpenAI**: gpt-4, gpt-3.5-turbo, etc.
- **Azure**: Your deployed model names

---

## Support & Issues

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Enable `--verbose` flag for detailed output
3. File an issue on GitHub with verbose logs
4. Contact: ICHIRO research team at ITS