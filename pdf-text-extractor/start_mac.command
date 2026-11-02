#!/bin/bash
# PDF Text Extractor (macOS). On the first start it sets itself up: uv (which fetches Python 3.12), the packages the app needs
# (ready-built for this Mac, so no compiler is needed), a self-test and a shortcut on the desktop. After that it starts the app.
cd "$(dirname "$0")" || exit 1
UV="$(command -v uv || true)"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
if [ -z "$UV" ]; then
  echo "Installing uv (it fetches Python and the packages the app needs) ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh || { echo "Could not install uv: check the internet connection, then try again."; read -r; exit 1; }
  UV="$HOME/.local/bin/uv"
fi
# set up when never set up here, or when .venv was made on another computer and does not run here
if [ ! -f .venv/.ready ] || ! .venv/bin/python -c "import PySide6, pymupdf" >/dev/null 2>&1; then
  echo "Setting up PDF Text Extractor (first start only; a few minutes) ..."
  rm -rf .venv
  { "$UV" venv --managed-python --python 3.12 .venv || "$UV" venv --python 3.12 .venv; } &&
    "$UV" pip install --python .venv/bin/python --only-binary :all: -r pyproject.toml ||
    { echo "The set-up failed (see above). Check the internet connection, then start again."; read -r; exit 1; }
  echo "Checking the app on sample PDFs ..."
  .venv/bin/python -m pdftextextractor.selftest --quick || echo "(the self-test reported a problem; the app will still start)"
  touch .venv/.ready
  .venv/bin/python -m pdftextextractor.shortcut --if-missing
fi
nohup .venv/bin/python -m pdftextextractor >/dev/null 2>&1 &
echo "PDF Text Extractor is starting. This window can be closed."
