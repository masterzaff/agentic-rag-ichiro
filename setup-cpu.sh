#!/usr/bin/env bash
set -euo pipefail

# Config
REPO_URL="https://github.com/ichiro-its/kaito.git"
REPO_DIR="$(basename "${REPO_URL%.git}")"

echo "== Kaito CPU setup =="

# Clone repo if needed
if [ ! -d "$REPO_DIR" ]; then
  echo "Cloning $REPO_URL ..."
  git clone "$REPO_URL"
else
  echo "Directory '$REPO_DIR' already exists; skipping clone."
fi

echo "Entering $REPO_DIR"
cd "$REPO_DIR"

# Environment file
if [ ! -f .env ] && [ -f .env.example ]; then
  echo "Creating .env from .env.example"
  cp .env.example .env
else
  echo ".env already exists or .env.example missing; skipping."
fi

# Python & venv
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found. Please install Python 3 first."
  exit 1
fi

if [ ! -d venv ]; then
  echo "Creating virtual environment (venv)"
  python3 -m venv venv
else
  echo "Virtual environment already exists; skipping."
fi

# Dependencies
echo "Installing dependencies (CPU-only)"
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements-cpu.txt

# Done
echo
echo "Setup complete!"
echo
echo "Next steps:"
echo "  cd \"$REPO_DIR\""
echo "  source venv/bin/activate"