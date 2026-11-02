#!/bin/zsh
# Starts the local model server used by the context judge, with its models kept inside this folder.
HERE="${0:A:h}"
export OLLAMA_MODELS="$HERE/.cache/ollama"
export OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_HOST=127.0.0.1:11434
exec /opt/homebrew/opt/ollama/bin/ollama serve
