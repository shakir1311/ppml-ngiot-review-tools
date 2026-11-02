#!/bin/bash
# Double-click in Finder: starts the experiments portal (this Mac only) and opens it in the browser.
cd "$(dirname "$0")"
bash portal.sh
echo; echo "If the browser did not open, go to http://127.0.0.1:8090/"; echo "Press any key to close this window."; read -n 1 -s
