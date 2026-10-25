#!/bin/bash
# Start MongoDB Agent Server

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "Starting MongoDB NL Query Agent on http://${HOST}:${PORT}"
python server.py "$@"
