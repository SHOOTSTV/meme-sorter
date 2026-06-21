#!/usr/bin/env bash
# Meme Sorter launcher for macOS / Linux
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 meme_sorter.py "$@"
elif command -v python >/dev/null 2>&1; then
  exec python meme_sorter.py "$@"
else
  echo
  echo "Python is not installed. Install it from https://www.python.org/downloads/"
  echo "Python n'est pas installe. Installez-le depuis https://www.python.org/downloads/"
  echo
  exit 1
fi
