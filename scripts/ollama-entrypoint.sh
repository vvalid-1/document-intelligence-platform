#!/bin/bash
set -e

echo "[ollama-entrypoint] Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

echo "[ollama-entrypoint] Waiting for Ollama API to be ready..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
  sleep 2
done
echo "[ollama-entrypoint] Ollama API is ready."

pull_if_missing() {
  local model="$1"
  if ollama list 2>/dev/null | grep -q "^${model}"; then
    echo "[ollama-entrypoint] Model '${model}' already present, skipping pull."
  else
    echo "[ollama-entrypoint] Pulling model '${model}'..."
    ollama pull "${model}"
    echo "[ollama-entrypoint] Model '${model}' pulled successfully."
  fi
}

pull_if_missing "qwen3:8b"
pull_if_missing "bge-m3"

echo "[ollama-entrypoint] All models ready. Keeping Ollama running..."
wait $OLLAMA_PID
