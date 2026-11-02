#!/usr/bin/env python3
"""Save online policy pages into the workspace as evidence: raw HTML, a pandoc text copy, and a manifest line.

    fetch_policy_pages.py <list.tsv> <outdir>

<list.tsv> has one page per line: `<id>\t<url>` (lines starting with # are skipped). For each page it writes

    <outdir>/<id>.html     the page exactly as served (curl, browser user agent, redirects followed)
    <outdir>/<id>.txt      the reading text (pandoc html -> plain, no wrapping)

or, when the server returns a PDF, <outdir>/<id>.pdf (no text copy: read PDFs with extract_paper.py). It appends to
<outdir>/MANIFEST.tsv: id, url, final url, HTTP status, bytes, sha256 of the file, retrieved (UTC), and a note when
the request ended on a sign-in page. Every request is recorded before any conversion, so a refusal or a sign-in
redirect is part of the record too.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/18.0 Safari/605.1.15")
MANIFEST_HEADER = "id\turl\tfinal_url\thttp_status\tbytes\tsha256\tretrieved_utc\tnote\n"
SIGN_IN_HOSTS = ("login.microsoftonline.com", "login.live.com", "accounts.google.com")


def fetch(url: str, html_path: Path) -> tuple[str, str]:
    """Download one URL to html_path; return (HTTP status, final URL after redirects)."""
    result = subprocess.run(
        ["curl", "-sL", "--compressed", "--max-time", "90", "-A", USER_AGENT,
         "-H", "Accept: text/html,application/xhtml+xml", "-H", "Accept-Language: en-GB,en;q=0.9",
         "-o", str(html_path), "-w", "%{http_code}\t%{url_effective}", url],
        capture_output=True, text=True, check=False)
    status, _, final_url = result.stdout.partition("\t")
    return status or "curl-failed", final_url


def to_text(html_path: Path, txt_path: Path) -> None:
    subprocess.run(["pandoc", "--sandbox", "-f", "html", "-t", "plain", "--wrap=none", str(html_path), "-o", str(txt_path)],
                   check=True)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    pages = [line.rstrip("\n").split("\t", 1) for line in Path(sys.argv[1]).read_text().splitlines()
             if line.strip() and not line.startswith("#")]
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = outdir / "MANIFEST.tsv"
    if not manifest.exists():
        manifest.write_text(MANIFEST_HEADER)

    for page_id, url in pages:
        html_path, txt_path = outdir / f"{page_id}.html", outdir / f"{page_id}.txt"
        status, final_url = fetch(url, html_path)
        retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = html_path.read_bytes() if html_path.exists() else b""
        saved = html_path
        if data.startswith(b"%PDF"):
            saved = html_path.with_suffix(".pdf")
            html_path.rename(saved)
        note = "sign-in page, content not retrieved" if any(h in final_url for h in SIGN_IN_HOSTS) else ""
        with manifest.open("a") as out:
            out.write(f"{page_id}\t{url}\t{final_url}\t{status}\t{len(data)}\t"
                      f"{hashlib.sha256(data).hexdigest()}\t{retrieved}\t{note}\n")
        if data and saved.suffix == ".html" and not note:
            to_text(saved, txt_path)
        words = len(txt_path.read_text().split()) if txt_path.exists() else 0
        kind = "PDF" if saved.suffix == ".pdf" else f"{words:,} words"
        print(f"{page_id}: HTTP {status}, {len(data):,} bytes, {kind}{', ' + note if note else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
