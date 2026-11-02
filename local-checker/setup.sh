#!/bin/zsh
# Sets up the local fact checker: its own Python environment and the tested model, all inside this folder.
HERE="${0:A:h}"
cd "$HERE" || exit 1
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
export HF_HOME="$HERE/.cache/huggingface"
.venv/bin/python -c "import check_claims as c; c.Verifier(); print('model ready:', c.MODEL, c.REVISION[:12])"
.venv/bin/python test_checker.py
