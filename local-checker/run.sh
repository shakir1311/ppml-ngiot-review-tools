#!/bin/zsh
# Runs the local fact checker with its own Python and keeps the downloaded model inside this folder.
HERE="${0:A:h}"
export HF_HOME="$HERE/.cache/huggingface"
export TOKENIZERS_PARALLELISM=false
exec "$HERE/.venv/bin/python" "$HERE/check_claims.py" "$@"
