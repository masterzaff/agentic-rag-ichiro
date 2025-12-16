#!/usr/bin/env bash
set -euo pipefail

# Edit this URL to the repository you want to clone (must be git-compatible)
REPO_URL="https://github.com/masterzaff/agentic-rag-ichiro.git"

# Derive repo directory name from URL (strip trailing .git if present)
REPO_DIR="$(basename "${REPO_URL%/.git}")"

# Clone if the directory does not already exist
if [ ! -d "$REPO_DIR" ]; then
  echo "Cloning $REPO_URL ..."
  git clone "$REPO_URL"
else
  echo "Directory $REPO_DIR already exists; skipping clone."
fi

echo "Entering $REPO_DIR"
cd "$REPO_DIR"

# Copy environment template if .env is missing
if [ ! -f .env ] && [ -f .env.example ]; then

  echo "Creating .env from .env.example"
  cp .env.example .env
else
  echo ".env already exists or .env.example missing; skipping copy."
fi

# Create virtual environment
if [ ! -d .venv ]; then
  echo "Creating virtual environment (.venv)"
  python3 -m venv venv
else
  echo "Virtual environment already exists; skipping creation."
fi

# Install dependencies using the venv's pip
echo "Installing dependencies from requirements-gpu.txt"
".venv/bin/pip" install --upgrade pip
".venv/bin/pip" install -r requirements-gpu.txt

echo "Setup complete. To activate the environment, run:"
echo "  source .venv/bin/activate"

# Delete setup file after installation
SCRIPT_PATH="$(readlink -f "$0")"
rm -f "$SCRIPT_PATH"