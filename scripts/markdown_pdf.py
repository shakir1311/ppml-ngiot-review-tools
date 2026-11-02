#!/usr/bin/env python3
"""Markdown rendering of a PDF (headings, lists, tables) with pymupdf4llm and its layout engine.

    markdown_pdf.py <file.pdf> <out.md>

Runs in a process of its own. pymupdf4llm loads onnxruntime, whose telemetry thread can abort a process while it
exits (crash of 28 Sep 2026: "recursive_mutex lock failed" in PosixTelemetry during exit). This script switches the
telemetry off (ORT_DISABLE_TELEMETRY) and, once the file is written, leaves with os._exit, which skips the
exit-time teardown where the abort happens. Exit status: 0 written, 1 failed.
"""
import os
import sys

os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.split("\n\n")[1].strip(), file=sys.stderr)
        return 2
    pdf, dest = sys.argv[1], sys.argv[2]
    try:
        import pymupdf4llm
        md = pymupdf4llm.to_markdown(pdf, show_progress=False)
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(md)
        os.replace(tmp, dest)
        return 0
    except Exception as exc:  # noqa: BLE001 - reported to the caller through the exit status
        print(f"markdown rendering failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
