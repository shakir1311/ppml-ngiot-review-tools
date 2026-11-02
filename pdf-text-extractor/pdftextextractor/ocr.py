"""Local OCR of rendered pages: several engines, lines in column order, and a vote word by word.

Engines (every one runs on this computer; nothing is sent anywhere):
  RapidOCR      PaddleOCR's models on ONNX Runtime — installed with the app, on Windows and macOS alike;
  Apple Vision  on a Mac (VNRecognizeTextRequest, accurate);
  Tesseract     wherever it is installed (it is found on the PATH or in its usual places).

Every engine returns lines with their boxes (shares of the page, origin top left) and a confidence. Lines are put in column order
(the left column, then the right, band by band between lines that span the page), since engines list lines top to bottom across
the page, which on a two-column page interleaves the columns. Where two or more engines read a page, the primary engine's
reading is checked word by word against the others by position: a word of the primary engine that is not a word of the
language, where the other engines agree on a similar word that is, is taken from them.
"""
from __future__ import annotations

import collections
import csv
import difflib
import io
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float


_WORDS: set[str] | None = None


def is_word(token: str) -> bool:
    global _WORDS
    if _WORDS is None:
        try:
            from english_words import get_english_words_set
            _WORDS = get_english_words_set(["web2", "gcide"], lower=True, alpha=True)
        except Exception:  # noqa: BLE001 - fall back to the system list where there is one
            p = Path("/usr/share/dict/words")
            _WORDS = {w.strip().lower() for w in p.read_text(errors="ignore").splitlines()} if p.exists() else set()
    w = re.sub(r"[^a-z]", "", unicodedata.normalize("NFKC", token).lower())
    return len(w) >= 2 and w in _WORDS


def joined_by_neighbours(lines: list[Line]):
    """For a page without a text layer: a line that crosses the middle while both columns run on just above and just below it
    is two column lines that OCR joined across the gutter."""
    spans = lambda l: l.x0 < 0.45 and l.x1 > 0.55
    left = [l for l in lines if not spans(l) and (l.x0 + l.x1) / 2 < 0.5]
    right = [l for l in lines if not spans(l) and (l.x0 + l.x1) / 2 >= 0.5]

    def joined(l: Line) -> bool:
        h = max(0.004, l.y1 - l.y0)
        near = lambda side, lo, hi: any(lo <= (m.y0 + m.y1) / 2 <= hi for m in side)
        return (near(left, l.y0 - 2.5 * h, l.y0) and near(right, l.y0 - 2.5 * h, l.y0)
                and near(left, l.y1, l.y1 + 2.5 * h) and near(right, l.y1, l.y1 + 2.5 * h))
    return joined


def joined_by_layout(side_by_side: list[tuple[float, float]]):
    """For a page with a text layer: a line that crosses the middle is two column lines joined by OCR only where the text layer
    has a line in each column side by side at that height (side_by_side: those heights, as shares of the page)."""
    return lambda l: any(y0 <= (l.y0 + l.y1) / 2 <= y1 for y0, y1 in side_by_side)


def column_order(lines: list[Line], joined=None) -> list[Line]:
    """Lines in reading order on a page of one or two columns: band by band between the lines that span both columns, the left
    column of a band before its right one. joined(line) marks the lines that cross the middle but are two column lines OCR
    joined across the gutter: they stay with the left column, where they begin, and do not cut the page into bands."""
    spans = lambda l: l.x0 < 0.45 and l.x1 > 0.55
    glued = {id(l) for l in lines if spans(l) and joined is not None and joined(l)}
    spanning = sorted((l for l in lines if spans(l) and id(l) not in glued), key=lambda l: l.y0)
    rest = [l for l in lines if not spans(l) or id(l) in glued]
    on_left = lambda l: id(l) in glued or (l.x0 + l.x1) / 2 < 0.5
    out, top = [], -1.0
    for cut in spanning + [None]:
        bottom = cut.y0 if cut else 2.0
        band = [l for l in rest if top <= (l.y0 + l.y1) / 2 < bottom]
        out += sorted((l for l in band if on_left(l)), key=lambda l: l.y0)
        out += sorted((l for l in band if not on_left(l)), key=lambda l: l.y0)
        if cut:
            out.append(cut)
            top = cut.y0
    return out


# ------------------------------------------------------------------------------------------------------------ engines
class Engine:
    name = "engine"

    def available(self) -> bool:
        return False

    def read(self, img: Path, width: int, height: int) -> list[Line]:
        raise NotImplementedError


RAPID_THREADS: int | None = None        # set in each process of a parallel run: RapidOCR's share of the cores


class RapidOcr(Engine):
    name = "RapidOCR"
    _engine = None

    def available(self) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def read(self, img: Path, width: int, height: int) -> list[Line]:
        if RapidOcr._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            RapidOcr._engine = RapidOCR(**({"intra_op_num_threads": RAPID_THREADS, "inter_op_num_threads": 1} if RAPID_THREADS else {}))
        result, _ = RapidOcr._engine(str(img))
        out = []
        for box, text, score in result or []:
            xs, ys = [p[0] for p in box], [p[1] for p in box]
            out.append(Line(text, min(xs) / width, min(ys) / height, max(xs) / width, max(ys) / height, float(score)))
        return out


class AppleVision(Engine):
    name = "Apple Vision"

    def available(self) -> bool:
        if sys.platform != "darwin":
            return False
        try:
            import Quartz  # noqa: F401
            import Vision  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def read(self, img: Path, width: int, height: int) -> list[Line]:
        import Quartz
        import Vision
        from Foundation import NSURL
        src = Quartz.CGImageSourceCreateWithURL(NSURL.fileURLWithPath_(str(img)), None)
        image = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
        out: list[Line] = []

        def handler(request, error):
            for obs in (request.results() or []):
                cand = obs.topCandidates_(1)
                if cand and len(cand):
                    bb = obs.boundingBox()
                    y0 = 1 - (bb.origin.y + bb.size.height)
                    out.append(Line(cand[0].string(), bb.origin.x, y0, bb.origin.x + bb.size.width, y0 + bb.size.height,
                                    float(cand[0].confidence())))
        req = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setUsesLanguageCorrection_(True)
        Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None).performRequests_error_([req], None)
        return out


class Tesseract(Engine):
    name = "Tesseract"
    PLACES = [r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
              "/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/usr/bin/tesseract"]

    def exe(self) -> str | None:
        return shutil.which("tesseract") or next((p for p in self.PLACES if os.path.exists(p)), None)

    def available(self) -> bool:
        return self.exe() is not None

    def read(self, img: Path, width: int, height: int) -> list[Line]:
        r = subprocess.run([self.exe(), str(img), "stdout", "-l", "eng", "--psm", "3", "tsv"], capture_output=True, timeout=600,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            raise RuntimeError(f"tesseract ended with code {r.returncode}")
        lines: dict = collections.OrderedDict()
        for row in csv.DictReader(io.StringIO(r.stdout.decode("utf-8", errors="replace")), delimiter="\t"):
            if row.get("level") == "5" and row.get("text", "").strip():
                k = (row["block_num"], row["par_num"], row["line_num"])
                x0, y0 = float(row["left"]), float(row["top"])
                lines.setdefault(k, []).append((row["text"], x0, y0, x0 + float(row["width"]), y0 + float(row["height"]),
                                                float(row["conf"])))
        out = []
        for ws in lines.values():
            out.append(Line(" ".join(w[0] for w in ws), min(w[1] for w in ws) / width, min(w[2] for w in ws) / height,
                            max(w[3] for w in ws) / width, max(w[4] for w in ws) / height,
                            max(0.0, sum(w[5] for w in ws) / len(ws)) / 100))
        return out


def engines() -> list[Engine]:
    """The engines available here, the most accurate first (Apple Vision on a Mac, then RapidOCR, then Tesseract)."""
    return [e for e in (AppleVision(), RapidOcr(), Tesseract()) if e.available()]


# ----------------------------------------------------------------------------------------------- a vote word by word
def words_in(box: Line, lines: list[Line]) -> list[str]:
    """The words of another engine's lines that lie inside a line's box, left to right."""
    hits = [l for l in lines if box.x0 - 0.01 <= (l.x0 + l.x1) / 2 <= box.x1 + 0.01 and box.y0 - 0.005 <= (l.y0 + l.y1) / 2 <= box.y1 + 0.005]
    return [w for l in sorted(hits, key=lambda l: l.x0) for w in l.text.split()]


def vote(primary: list[Line], others: list[list[Line]]) -> tuple[list[str], int]:
    """The primary engine's lines, word by word against the other engines' words in the same place: a word that is not a word of
    the language, where the others read a similar word that is, is taken from them. -> (lines, words taken)"""
    out, taken = [], 0
    for line in primary:
        a = line.text.split()
        new = list(a)
        for other in others:
            b = words_in(line, other)
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
                if op == "replace" and i2 - i1 == j2 - j1:
                    for k in range(i2 - i1):
                        x, y = new[i1 + k], b[j1 + k]
                        if not is_word(x) and is_word(y) and difflib.SequenceMatcher(None, x.lower(), y.lower()).ratio() >= 0.6:
                            new[i1 + k] = y
                            taken += 1
        out.append(" ".join(new) if new != a else line.text)
    return out, taken


def agreement_on_prose(primary: list[Line], others: list[list[Line]]) -> float | None:
    """Share of the words of the primary engine's prose lines (a quarter of the page wide, five words or more) that at least one
    other engine reads alike in the same place."""
    norm = lambda w: re.sub(r"[^a-z0-9]", "", w.lower())
    alike = total = 0
    for line in primary:
        if line.x1 - line.x0 < 0.25 or len(line.text.split()) < 5:
            continue
        a = [norm(w) for w in line.text.split() if norm(w)]
        hit: set[int] = set()
        for other in others:
            b = [norm(w) for w in words_in(line, other) if norm(w)]
            for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
                hit.update(range(blk.a, blk.a + blk.size))
        alike += len(hit)
        total += len(a)
    return round(alike / total, 4) if total else None
