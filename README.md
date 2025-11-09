# ICHIRO Assistant

A powerful command-line RAG (Retrieval-Augmented Generation) system for querying documentation and codebases using AI. Built for ICHIRO robotics research team at ITS (Institut Teknologi Sepuluh Nopember).

## Features

- 📚 **Document RAG System**: Query HTML documentation with semantic search
- 💻 **Codebase Analysis**: Intelligent code search and analysis with agentic workflows
- 🤖 **Multiple Query Modes**: Search, Ask, and Teach modes for different use cases
- 🔄 **Iterative Refinement**: Automatically refines searches for better answers
- 🧠 **Conversation Memory**: Maintains context across multiple queries
- 🌐 **GitHub Integration**: Direct repository fetching and analysis

## Installation

### Prerequisites

- Python 3.10+ (`venv` is **very** recommended)
- [Ollama](https://ollama.ai/) running locally with models:
  - `llama3.1` (main chat model)
  - `mistral` (helper model for classification)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd retrieval-cli/rc
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Ensure Ollama is running:
```bash
ollama serve
```

4. Pull required models:
```bash
ollama pull llama3.1
ollama pull mistral
```

## Usage

### Basic Usage

```bash
# Query HTML documentation from a zip file
python app.py ./docs.zip

# Query specific folder in zip
python app.py ./docs.zip ./html/

# Query GitHub repository
python app.py https://github.com/owner/repo

# Keep index files after exit (faster subsequent runs)
python app.py ./docs.zip --keep

# Enable verbose output
python app.py ./docs.zip --verbose
```

### Query Modes

When querying *documentation*, you can choose from three modes:

1. **Search Mode** (Mode 1): Strictly answers from knowledge base only
2. **Ask Mode** (Mode 2): Uses knowledge base, falls back to general knowledge
3. **Teach Mode** (Mode 3): Educational responses based on context

Switch modes anytime with `/mode` command.

### Commands

#### Documentation Query Mode
- `/quit` or `/exit` - Exit the program
- `/mode` - Switch between Search/Ask/Teach modes

#### Codebase Query Mode
- `/help` - Show all available commands
- `/ls [path]` - List files in directory
- `/read <file>` - Read specific file
- `/search <term>` - Search for term in files
- `/tree` - Show directory structure
- `/memory` - Show cached files
- `/clear` - Clear file cache
- `/quit` or `/exit` - Exit codebase mode

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

RAG ready with 234 chunks. Ctrl+C or '/quit' to exit. '/mode' to change query mode.

Query: How do I create a ROS2 node?

Mode: RAG search
Retrieved 5 chunks
Confidence: HIGH

Answer (from 5 chunks, 3 docs):
To create a ROS2 node, you need to:
1. Import rclpy
2. Initialize the ROS2 client library
3. Create a Node class
...
```

### Querying GitHub Repository

```bash
$ python app.py https://github.com/ros2/examples
Loading...
Fetching repository: https://github.com/ros2/examples
Downloading https://github.com/ros2/examples/archive/refs/heads/main.zip...
Codebase ready

Codebase query ready with 156 files. Type '/help' for commands.

Code Query: What examples are available for publishers?

Mode: Agentic codebase search
Loading 3 files...
  - rclpy/minimal_publisher/setup.py (loaded)
  - rclpy/minimal_publisher/README.md (loaded)
  - rclpy/minimal_publisher/minimal_publisher.py (loaded)
Confidence: HIGH

Answer (analyzed 3 files):
The repository contains several publisher examples...
```

## Architecture

```
rc/
├── app.py                 # Main entry point
├── requirements.txt       # Dependencies
├── utils/
│   ├── config.py         # Configuration settings
│   ├── functions.py      # Utility functions
│   ├── extract.py        # File extraction and preparation
│   ├── htmlcontext.py    # HTML cleaning and text extraction
│   ├── ingest.py         # Document chunking and embedding
│   ├── query.py          # Query processing and RAG logic
│   ├── codeagent.py      # Agentic code search
│   └── codecontext.py    # GitHub and codebase utilities
└── rag_tmp/              # Temporary files (auto-generated)
    ├── html/             # Extracted HTML files
    ├── data/             # Cleaned text files
    ├── chunks.jsonl      # Document chunks
    ├── index.faiss       # Vector index
    └── codebase/         # Downloaded code repositories
```

## Configuration

Edit `utils/config.py` to customize:

```python
# Embedding model
EMB_MODEL = "all-MiniLM-L6-v2"

# Chunk settings
MAX_CHARS = 1200
OVERLAP = 150

# Retrieval settings
TOP_K = 5
MAX_ITERATIONS = 3

# Ollama settings
OLLAMA_URL = "http://localhost:11434"
CHAT_MODEL = "llama3.1"
HELPER_MODEL = "mistral"

# Context windows
CHAT_CTX_WINDOW = 16000
HELPER_CTX_WINDOW = 4096
```

## How It Works

1. **Document Ingestion**
   - Extracts HTML files from zip or directory
   - Cleans and converts to plain text
   - Chunks documents with overlap
   - Generates embeddings using sentence-transformers
   - Stores in FAISS vector index

2. **Query Processing**
   - Classifies query (search KB vs. direct answer)
   - Retrieves relevant chunks using semantic search
   - Builds context-aware prompt
   - Generates answer using Ollama LLM
   - Assesses confidence and iteratively refines if needed

3. **Codebase Analysis**
   - Builds file index with metadata
   - Uses LLM to select relevant files
   - Caches file contents for efficiency
   - Performs multi-iteration analysis
   - Maintains conversation context

## Performance Tips

- Use `--keep` flag to preserve index between runs
- Use `--verbose` to see detailed timing information
- Larger context windows improve answer quality but are slower
- Adjust `TOP_K` and `MAX_ITERATIONS` for speed/quality tradeoff

## Troubleshooting

### "Cannot connect to Ollama"
- Ensure Ollama is running: `ollama serve`
- Check Ollama URL in config.py

### "No chunks created"
- Verify HTML files contain actual content
- Check if index.html exists for title mapping

### Slow performance
- Reduce `MAX_ITERATIONS` in config
- Use smaller embedding model
- Decrease `TOP_K` value

## Dependencies

- `faiss-cpu` - Vector similarity search
- `sentence-transformers` - Text embeddings
- `numpy` - Numerical operations
- `rich` - Terminal formatting
- `bs4` (BeautifulSoup) - HTML parsing
- `lxml` - XML/HTML parser
- `requests` - HTTP requests

## Evaluation (IMPORTANT!)
### Pros (+)
- Good performance on many use cases
- Tested on ICHIRO's Jira knowledgebase and ICHIRO's GitHub repositories

### Cons (-)
- Slow speed due to unoptimized RAG system
- Source code is not fully clean yet due to limited time of refactoring

### What's next?
- I'll need to improve and optimize the RAG system to improve speed
- Clean code refactoring is also needed
- Improve the CLI further and add UI if needed for user experience

## Credits

Created by Irzam. Developed for ICHIRO robotics research team at Institut Teknologi Sepuluh Nopember (ITS).
