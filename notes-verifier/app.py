#!/usr/bin/env python3
"""Notes Verifier — check each cited paper's notes and summary against its PDF, side by side, and correct them.

Left: the papers cited in the review, with your progress.  Middle: the paper's notes and summary, editable.
Right: the PDF.  Click a line of the notes that cites a page ([p7], [p6, image], [p3–5]) and the PDF opens at that page
with the quoted words outlined.  Turn on the highlighter to mark passages in the PDF; the highlights are saved in the PDF
file itself (standard PDF highlights, visible in Preview and Acrobat).

Nothing is lost:
  - notes and summaries are saved automatically a second after you stop typing, when you switch paper or tab, and on quit;
    every save writes a complete new file in one step (no half-written files);
  - before a file is first changed, its earlier text is kept in notes-verifier/history/<paper>/ (and the very first
    version as …-original.md);
  - before a PDF gets its first highlight, an untouched copy is kept in notes-verifier/originals/<paper>/.

Start it with  notes-verifier/run.sh  or by double-clicking "Notes Verifier.app".
Self-test (no real paper is opened):  notes-verifier/run.sh --self-test [screenshot.png]
"""
from __future__ import annotations

import argparse
import datetime
import faulthandler
import json
import os
import re
import shutil
import signal
import sys
import tempfile
import traceback
from collections import OrderedDict
from pathlib import Path

import pymupdf
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

PAGE_CITE = re.compile(r'\[p\d[^\]\n]{0,40}\]')           # [p7]  [p6, image]  [p3–5]  [p3, p5]  — not [12]
NUMBER = re.compile(r'\d+')
QUOTE = re.compile(r'[“"]([^”"\n]{6,})[”"]')
AUTOSAVE_MS = 1000
MARK_MS = 9000
HIGHLIGHT_RGB = (1.0, 0.89, 0.2)


def log(message: str):
    """One timestamped line on the terminal / in .cache/app.log: what you did and anything that went wrong.
    Only paper ids, page numbers and counts are logged, never text from a paper."""
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def log_exception(kind, value, tb):
    log('ERROR ' + ''.join(traceback.format_exception(kind, value, tb)).rstrip())
    app = QtWidgets.QApplication.instance()
    win = next((w for w in app.topLevelWidgets() if isinstance(w, QtWidgets.QMainWindow)), None) if app else None
    if win is not None:
        win.statusBar().showMessage(f'Something went wrong ({value}); your text is still in the window and is saved '
                                    'as usual. The details are in the log.', 15000)


def now_stamp():
    return datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')


def write_atomically(path: Path, text: str):
    """Write the whole file to a temporary file next to it, then swap it in, so a file is never half written."""
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=str(path.parent))
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def page_at(line: str, pos: int):
    """The page a click on `line` at character `pos` points to, and the quotation that goes with it.

    A click inside a page citation picks the page number nearest the click; a click elsewhere on the line picks the first
    page the line cites. Returns (page number, quotation or '') or None when the line cites no page."""
    cites = list(PAGE_CITE.finditer(line))
    if not cites:
        return None
    chosen = next((c for c in cites if c.start() <= pos <= c.end()), cites[0])
    numbers = list(NUMBER.finditer(chosen.group(0)))
    if chosen.start() <= pos <= chosen.end():
        rel = pos - chosen.start()
        number = min(numbers, key=lambda m: 0 if m.start() <= rel <= m.end() else min(abs(rel - m.start()), abs(rel - m.end())))
    else:
        number = numbers[0]
    quote = next((q.group(1) for q in QUOTE.finditer(line) if q.start() >= chosen.end()), None)
    if quote is None:
        quote = next((q.group(1) for q in QUOTE.finditer(line)), '')
    return int(number.group(0)), quote


def cited_pages(text: str):
    pages = set()
    for c in PAGE_CITE.finditer(text):
        pages.update(int(n) for n in NUMBER.findall(c.group(0)))
    return sorted(pages)


# --------------------------------------------------------------------------------------------------- storage


class Paths:
    def __init__(self, home: Path):
        self.home = home
        self.data = home / 'data'
        self.history = home / 'history'
        self.originals = home / 'originals'
        self.papers = self.data / 'papers.json'
        self.status = self.data / 'status.json'


class Status:
    """Your progress: which notes and summaries you have checked, and when a paper was last edited."""

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text()) if path.exists() else {}

    def get(self, key):
        return self.data.get(key, {})                  # looking never adds an entry; only set() does

    def set(self, key, field, value):
        entry = self.data.setdefault(key, {})
        entry[field] = value
        entry[field + '_on'] = datetime.datetime.now().isoformat(timespec='seconds')
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(self.path, json.dumps(self.data, indent=1, ensure_ascii=False))


class TextDoc:
    """One notes or summary file: loads it, saves it safely, and keeps earlier versions in history/."""

    def __init__(self, key: str, name: str, path: Path, paths: Paths):
        self.key, self.name, self.path, self.paths = key, name, path, paths
        self.saved_text = path.read_text(encoding='utf-8') if path.exists() else ''
        self.mtime = path.stat().st_mtime if path.exists() else 0
        self.backed_up = False

    def _history_dir(self):
        d = self.paths.history / self.key
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, text: str) -> bool:
        if text == self.saved_text:
            return False
        hist = self._history_dir()
        stem = self.name.upper()
        original = hist / f'{stem}-original.md'
        if self.path.exists():
            disk = self.path.read_text(encoding='utf-8')
            if not original.exists():
                original.write_text(disk, encoding='utf-8')
            if disk != self.saved_text:                         # changed by something else since it was opened
                (hist / f'{stem}-changed-on-disk-{now_stamp()}.md').write_text(disk, encoding='utf-8')
            elif not self.backed_up:                            # once per session: the version before today's edits
                (hist / f'{stem}-before-{now_stamp()}.md').write_text(disk, encoding='utf-8')
        self.backed_up = True
        write_atomically(self.path, text)
        self.saved_text = text
        self.mtime = self.path.stat().st_mtime
        return True


# --------------------------------------------------------------------------------------------------- notes editor


class CiteHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self.cite = QtGui.QTextCharFormat()
        self.cite.setForeground(QtGui.QColor('#1d4f8f'))
        self.cite.setFontUnderline(True)
        self.cite.setFontWeight(QtGui.QFont.Weight.DemiBold)
        self.quote = QtGui.QTextCharFormat()
        self.quote.setForeground(QtGui.QColor('#2f6b3a'))
        self.heading = QtGui.QTextCharFormat()
        self.heading.setFontWeight(QtGui.QFont.Weight.Bold)
        self.heading.setForeground(QtGui.QColor('#222'))

    def highlightBlock(self, text):
        if text.startswith('#'):
            self.setFormat(0, len(text), self.heading)
        for m in QUOTE.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.quote)
        for m in PAGE_CITE.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.cite)


class NotesEditor(QtWidgets.QPlainTextEdit):
    pageRequested = QtCore.Signal(int, str)

    def __init__(self):
        super().__init__()
        font = self.font()
        font.setPointSize(13)
        self.setFont(font)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabStopDistance(24)
        self.highlighter = CiteHighlighter(self.document())

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if e.button() != Qt.MouseButton.LeftButton or self.textCursor().hasSelection():
            return
        cur = self.cursorForPosition(e.position().toPoint())
        target = page_at(cur.block().text(), cur.positionInBlock())
        if target:
            self.pageRequested.emit(*target)


# --------------------------------------------------------------------------------------------------- PDF view


class PageWidget(QtWidgets.QWidget):
    def __init__(self, view: 'PdfView', index: int):
        super().__init__()
        self.view, self.index = view, index
        self.retired = False                       # set when its PDF is closed: the page is never drawn again
        self.setMouseTracking(False)

    def sizeHint(self):
        return QtCore.QSize(0, 0) if self.retired else self.view.page_pixel_size(self.index)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _):
        if self.retired:
            return
        p = QtGui.QPainter(self)
        try:
            img = self.view.page_image(self.index)
            if img is not None:
                p.drawImage(0, 0, img)
            p.setPen(QtGui.QPen(QtGui.QColor('#c9ced6'), 1))
            p.drawRect(self.rect().adjusted(0, 0, -1, -1))
            for r in self.view.marks.get(self.index, []):                # where the quoted words are (temporary)
                p.setPen(QtGui.QPen(QtGui.QColor('#d2322d'), 2.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(r.adjusted(-3, -2, 3, 2))
            if self.view.drag and self.view.drag['index'] == self.index:  # highlight being drawn
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QtGui.QColor(255, 220, 40, 110))
                for r in self.view.drag['preview']:
                    p.drawRect(r)
        finally:
            p.end()

    def mousePressEvent(self, e):
        self.view.mouse_press(self.index, e)

    def mouseMoveEvent(self, e):
        self.view.mouse_move(self.index, e)

    def mouseReleaseEvent(self, e):
        self.view.mouse_release(self.index, e)

    def contextMenuEvent(self, e):
        self.view.context_menu(self.index, e)


class PdfView(QtWidgets.QScrollArea):
    pageChanged = QtCore.Signal(int, int)          # current page (1-based), page count
    highlightsChanged = QtCore.Signal(int)
    highlightAdded = QtCore.Signal(int, str)       # page (1-based) and the words just highlighted (Sheet Reviewer: a quotation)
    message = QtCore.Signal(str)

    def __init__(self, paths: Paths):
        super().__init__()
        self.paths = paths
        self.doc = None
        self.path = None
        self.key = None
        self.zoom = 1.0
        self.fit_width = True
        self.highlighter_on = False
        self.cache = OrderedDict()
        self.words = {}
        self.marks = {}
        self.drag = None
        self.pages = []
        self.container = QtWidgets.QWidget()
        self.container.setStyleSheet('background:#e9ecef;')
        self.layout_ = QtWidgets.QVBoxLayout(self.container)
        self.layout_.setContentsMargins(12, 12, 12, 12)
        self.layout_.setSpacing(12)
        self.layout_.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.setWidget(self.container)
        self.setWidgetResizable(True)
        self.verticalScrollBar().valueChanged.connect(self._report_page)
        self.mark_timer = QtCore.QTimer(self, singleShot=True, interval=MARK_MS, timeout=self.clear_marks)
        self.resize_timer = QtCore.QTimer(self, singleShot=True, interval=150, timeout=self._refit)

    # ---- document
    def open(self, key: str, path: Path):
        self.close_doc()
        self.key, self.path = key, path
        self.doc = pymupdf.open(path)
        log(f'  PDF opened: {self.doc.page_count} pages, {self.highlight_count()} highlights')
        self.fit_width = True
        self._build_pages()
        self._refit(force=True)
        self.verticalScrollBar().setValue(0)
        self.highlightsChanged.emit(self.highlight_count())

    def close_doc(self):
        for w in self.pages:
            w.retired = True
            w.hide()
            self.layout_.removeWidget(w)
            w.deleteLater()
        self.pages = []
        self.cache.clear()
        self.words.clear()
        self.marks.clear()
        if self.doc is not None:
            self.doc.close()
        self.doc = None

    def _build_pages(self):
        for i in range(self.doc.page_count):
            w = PageWidget(self, i)
            self.pages.append(w)
            self.layout_.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)

    def page_pixel_size(self, i):
        r = self.doc[i].rect
        return QtCore.QSize(int(r.width * self.zoom), int(r.height * self.zoom))

    def page_image(self, i):
        if self.doc is None or not 0 <= i < self.doc.page_count:
            return None
        key = (i, round(self.zoom, 4))
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        dpr = self.devicePixelRatioF() or 1.0
        pix = self.doc[i].get_pixmap(matrix=pymupdf.Matrix(self.zoom * dpr, self.zoom * dpr), alpha=False, annots=True)
        img = QtGui.QImage(pix.samples, pix.width, pix.height, pix.stride, QtGui.QImage.Format.Format_RGB888).copy()
        img.setDevicePixelRatio(dpr)
        self.cache[key] = img
        while len(self.cache) > 14:
            self.cache.popitem(last=False)
        return img

    def _forget(self, i):
        for k in [k for k in self.cache if k[0] == i]:
            del self.cache[k]
        self.words.pop(i, None)

    # ---- zoom and layout
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.fit_width:
            self.resize_timer.start()

    def _refit(self, force=False):
        if self.doc is None:
            return
        if self.fit_width:
            widest = max(self.doc[i].rect.width for i in range(min(self.doc.page_count, 5)))
            z = max(0.2, (self.viewport().width() - 32) / widest)
            if not force and abs(z - self.zoom) < 0.01:
                return
            self.zoom = z
        self._relayout()

    def set_zoom(self, factor):
        if self.doc is None:
            return
        page = self.current_page()
        self.fit_width = False
        self.zoom = max(0.2, min(5.0, self.zoom * factor))
        self._relayout()
        self.go_to_page(page)

    def fit(self):
        page = self.current_page()
        self.fit_width = True
        self._refit(force=True)
        self.go_to_page(page)

    def _relayout(self):
        self.cache.clear()
        for w in self.pages:
            w.setFixedSize(w.sizeHint())
            w.update()

    # ---- navigation
    def current_page(self):
        if not self.pages:
            return 1
        mid = self.verticalScrollBar().value() + self.viewport().height() // 3
        for w in self.pages:
            if w.y() + w.height() + 6 >= mid:
                return w.index + 1
        return len(self.pages)

    def _report_page(self):
        if self.doc is not None:
            self.pageChanged.emit(self.current_page(), self.doc.page_count)

    def go_to_page(self, page: int, quote: str = ''):
        if self.doc is None:
            return False
        if not 1 <= page <= self.doc.page_count:
            self.message.emit(f'The notes cite page {page}, but this PDF has {self.doc.page_count} pages.')
            log(f'  page {page} cited, but the PDF has {self.doc.page_count} pages')
            return False
        QtWidgets.QApplication.processEvents()
        w = self.pages[page - 1]
        y = w.y() - 6
        self.clear_marks()
        if quote:
            rects = self.find_quote(page - 1, quote)
            log(f'  jump to page {page}: quoted words {"found" if rects else "NOT found automatically"}')
            if rects:
                self.marks[page - 1] = rects
                y = w.y() + max(0, int(min(r.top() for r in rects)) - 120)
                self.mark_timer.start()
            else:
                self.message.emit(f'Page {page}: the quoted words were not found automatically; look on the page.')
        self.verticalScrollBar().setValue(y)
        w.update()
        self._report_page()
        return True

    def clear_marks(self):
        changed = list(self.marks)
        self.marks.clear()
        for i in changed:
            if i < len(self.pages):
                self.pages[i].update()

    def find_quote(self, i, quote):
        page = self.doc[i]
        words = re.findall(r"[^\s…]+", quote.replace('...', ' '))
        for n in (10, 7, 5, 3):
            if len(words) < min(n, 3):
                continue
            phrase = ' '.join(words[:n])
            hits = page.search_for(phrase)
            if hits:
                return [self._to_screen(i, r) for r in hits]
        return []

    # ---- coordinates (PDF points <-> widget pixels)
    def _to_screen(self, i, rect):
        r = pymupdf.Rect(rect) * self.doc[i].rotation_matrix
        return QtCore.QRectF(r.x0 * self.zoom, r.y0 * self.zoom, r.width * self.zoom, r.height * self.zoom)

    def _to_page(self, i, pos: QtCore.QPointF):
        return pymupdf.Point(pos.x() / self.zoom, pos.y() / self.zoom) * self.doc[i].derotation_matrix

    # ---- highlighting
    def page_words(self, i):
        if i not in self.words:
            self.words[i] = self.doc[i].get_text('words')
        return self.words[i]

    def _nearest_word(self, i, point):
        words = self.page_words(i)
        if not words:
            return None
        def dist(w):
            dx = max(w[0] - point.x, 0, point.x - w[2])
            dy = max(w[1] - point.y, 0, point.y - w[3])
            return dx * dx + 4 * dy * dy
        return min(range(len(words)), key=lambda k: dist(words[k]))

    def _line_rects(self, i, a, b):
        words = self.page_words(i)[min(a, b):max(a, b) + 1]
        lines = OrderedDict()
        for w in words:
            r = pymupdf.Rect(w[:4])
            k = (w[5], w[6])
            lines[k] = lines[k] | r if k in lines else r
        return list(lines.values())

    def mouse_press(self, i, e):
        if not self.highlighter_on or e.button() != Qt.MouseButton.LeftButton:
            return
        start = self._nearest_word(i, self._to_page(i, e.position()))
        if start is None:
            self.message.emit('This page has no selectable text (it may be a scanned image).')
            return
        self.drag = {'index': i, 'start': start, 'end': start, 'preview': []}
        self._update_preview()

    def mouse_move(self, i, e):
        if not self.drag or self.drag['index'] != i:
            return
        end = self._nearest_word(i, self._to_page(i, e.position()))
        if end is not None and end != self.drag['end']:
            self.drag['end'] = end
            self._update_preview()

    def mouse_release(self, i, e):
        if not self.drag or self.drag['index'] != i:
            return
        drag, self.drag = self.drag, None
        self.add_highlight(i, drag['start'], drag['end'])

    def _update_preview(self):
        d = self.drag
        d['preview'] = [self._to_screen(d['index'], r) for r in self._line_rects(d['index'], d['start'], d['end'])]
        self.pages[d['index']].update()

    def add_highlight(self, i, a, b):
        rects = self._line_rects(i, a, b)
        if not rects:
            return False
        self._keep_original()
        page = self.doc[i]
        annot = page.add_highlight_annot(rects)
        annot.set_colors(stroke=HIGHLIGHT_RGB)
        annot.update()
        self._save_pdf()
        self._forget(i)
        self.pages[i].update()
        self.highlightsChanged.emit(self.highlight_count())
        self.message.emit(f'Highlight saved in the PDF (page {i + 1}).')
        log(f'  highlight added on page {i + 1} ({len(rects)} line(s)); saved in the PDF')
        self.highlightAdded.emit(i + 1, self.words_text(i, a, b))
        return True

    def words_text(self, i, a, b):
        """the words from a to b on page i as one line of text; a word broken at a line end ("pri-" + "vacy") is joined"""
        words = self.page_words(i)[min(a, b):max(a, b) + 1]
        out = ''
        for k, w in enumerate(words):
            t = w[4]
            nxt = words[k + 1] if k + 1 < len(words) else None
            if nxt is not None and t.endswith('-') and (w[5], w[6]) != (nxt[5], nxt[6]):
                out += t[:-1]
            else:
                out += t + ' '
        return ' '.join(out.split())

    def highlight_at(self, i, point, page=None):
        page = page if page is not None else self.doc[i]
        for annot in page.annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT]):
            v = annot.vertices or []
            quads = [pymupdf.Quad(v[k:k + 4]) for k in range(0, len(v) - 3, 4)]
            if any(point in q.rect for q in quads) or (not quads and point in annot.rect):
                return annot
        return None

    def remove_highlight(self, i, point):
        page = self.doc[i]
        annot = self.highlight_at(i, point, page)
        if annot is None:
            return False
        self._keep_original()
        page.delete_annot(annot)
        self._save_pdf()
        self._forget(i)
        self.pages[i].update()
        self.highlightsChanged.emit(self.highlight_count())
        self.message.emit(f'Highlight removed (page {i + 1}).')
        log(f'  highlight removed on page {i + 1}; saved in the PDF')
        return True

    def context_menu(self, i, e):
        point = self._to_page(i, QtCore.QPointF(e.pos()))
        if self.highlight_at(i, point) is None:
            return
        menu = QtWidgets.QMenu(self)
        act = menu.addAction('Remove this highlight')
        if menu.exec(e.globalPos()) == act:
            self.remove_highlight(i, point)

    def highlight_count(self):
        if self.doc is None:
            return 0
        return sum(1 for pg in self.doc for _ in pg.annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT]))

    def _keep_original(self):
        dest = self.paths.originals / self.key / self.path.name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.path, dest)
            log(f'  untouched copy of the PDF kept: {dest}')

    def _save_pdf(self):
        try:                                     # normal case: append the change to the end of the file
            if self.doc.can_save_incrementally():
                self.doc.save(self.doc.name, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
                return
        except Exception as err:
            log(f'  incremental save not possible ({err}); writing a complete new copy')
        fd, tmp = tempfile.mkstemp(prefix='.' + self.path.name + '.', suffix='.pdf', dir=str(self.path.parent))
        os.close(fd)
        self.doc.save(tmp, garbage=1, deflate=True)
        self.doc.close()
        os.replace(tmp, self.path)
        self.doc = pymupdf.open(self.path)
        self.cache.clear()
        self.words.clear()


# --------------------------------------------------------------------------------------------------- main window


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, paths: Paths, root: Path = ROOT, settings: QtCore.QSettings | None = None):
        super().__init__()
        self.paths, self.root = paths, root
        listing = json.loads(paths.papers.read_text())
        self.papers = listing['papers']
        self.paper_version = listing.get('paper_version')
        self.status = Status(paths.status)
        self.current = None
        self.docs = {}
        self.settings = settings or QtCore.QSettings('Abertay', 'NotesVerifier')
        self.setWindowTitle('Notes Verifier' + (f' — papers cited in the review (V{self.paper_version})' if self.paper_version else ''))
        self._build()
        self.autosave = QtCore.QTimer(self, singleShot=True, interval=AUTOSAVE_MS, timeout=self.save_now)
        self._fill_list()
        last = self.settings.value('last_paper')
        start = next((k for k, p in enumerate(self.papers) if p['key'] == last), 0)
        self.list.setCurrentRow(self._row_of(start))
        geo = self.settings.value('geometry')
        if geo:
            self.restoreGeometry(geo)
        else:
            avail = self._available()
            self.resize(int(avail.width() * 0.92), int(avail.height() * 0.9))
        split = self.settings.value('splitter')
        if split:
            self.split.restoreState(split)
        self.split.setChildrenCollapsible(False)
        self._fit_on_screen()

    def _available(self):
        screen = self.screen() or QtGui.QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def _fit_on_screen(self):
        """Keep the whole window on the screen, whatever size it was left at last time."""
        avail = self._available()
        w = min(self.width(), avail.width() - 20)
        h = min(self.height(), avail.height() - 20)
        self.resize(w, h)
        x = min(max(self.x(), avail.left()), avail.left() + avail.width() - w)
        y = min(max(self.y(), avail.top()), avail.top() + avail.height() - h)
        self.move(x, y)
        sizes = self.split.sizes()
        if len(sizes) == 3 and min(sizes) < 150:      # a pane saved as collapsed: give it its share back
            self.split.setSizes([int(w * 0.2), int(w * 0.36), int(w * 0.44)])

    # ---- layout
    def _build(self):
        # left: papers
        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 4, 8)
        self.search = QtWidgets.QLineEdit(placeholderText='Search papers (author, title, id, number)')
        self.search.textChanged.connect(self._fill_list)
        self.show_filter = QtWidgets.QComboBox()
        self.show_filter.addItems(['All papers', 'Not finished', 'Finished', 'Edited'])
        self.show_filter.currentIndexChanged.connect(self._fill_list)
        self.progress = QtWidgets.QLabel()
        self.list = QtWidgets.QListWidget()
        self.list.setWordWrap(True)
        self.list.setUniformItemSizes(False)
        self.list.currentRowChanged.connect(self._on_row)
        lv.addWidget(self.search)
        lv.addWidget(self.show_filter)
        lv.addWidget(self.progress)
        lv.addWidget(self.list, 1)

        # middle: notes and summary
        mid = QtWidgets.QWidget()
        mv = QtWidgets.QVBoxLayout(mid)
        mv.setContentsMargins(4, 8, 4, 8)
        self.title = QtWidgets.QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet('font-size:15px; font-weight:600;')
        self.subtitle = QtWidgets.QLabel()
        self.subtitle.setWordWrap(True)                 # a long line here must never widen the window
        self.subtitle.setStyleSheet('color:#59616c;')
        self.subtitle.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        nav = QtWidgets.QHBoxLayout()
        self.prev_btn = QtWidgets.QPushButton('◀ Previous paper')
        self.next_btn = QtWidgets.QPushButton('Next paper ▶')
        self.prev_btn.clicked.connect(lambda: self._step(-1))
        self.next_btn.clicked.connect(lambda: self._step(1))
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        self.tabs = QtWidgets.QTabWidget()
        self.editors = {}
        for name, label in (('notes', 'Notes'), ('summary', 'Summary')):
            ed = NotesEditor()
            ed.textChanged.connect(self._on_edit)
            ed.pageRequested.connect(self._go)
            self.editors[name] = ed
            self.tabs.addTab(ed, label)
        self.tabs.currentChanged.connect(self._on_tab)
        hint = QtWidgets.QLabel('Click a line with a page citation such as <b style="color:#1d4f8f">[p7]</b> to open that '
                                'page; the quoted words are outlined in red.')
        hint.setStyleSheet('color:#59616c;')
        hint.setWordWrap(True)
        chips_row = QtWidgets.QHBoxLayout()
        chips_row.addWidget(QtWidgets.QLabel('Pages cited:'))
        self.chips_area = QtWidgets.QScrollArea()
        self.chips_area.setWidgetResizable(True)
        self.chips_area.setFixedHeight(40)
        self.chips_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.chips_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chips_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chips_row.addWidget(self.chips_area, 1)
        checks = QtWidgets.QHBoxLayout()
        self.check_notes = QtWidgets.QCheckBox('Notes checked')
        self.check_summary = QtWidgets.QCheckBox('Summary checked')
        self.check_notes.toggled.connect(lambda v: self._set_check('notes_checked', v))
        self.check_summary.toggled.connect(lambda v: self._set_check('summary_checked', v))
        self.saved_label = QtWidgets.QLabel()
        checks.addWidget(self.check_notes)
        checks.addWidget(self.check_summary)
        checks.addStretch(1)
        checks.addWidget(self.saved_label)
        mv.addWidget(self.title)
        mv.addWidget(self.subtitle)
        mv.addLayout(nav)
        mv.addWidget(self.tabs, 1)
        mv.addWidget(hint)
        mv.addLayout(chips_row)
        mv.addLayout(checks)

        # right: PDF
        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(4, 8, 8, 8)
        bar = QtWidgets.QHBoxLayout()
        self.page_box = QtWidgets.QSpinBox(minimum=1, maximum=1)
        self.page_box.setPrefix('Page ')
        self.page_box.editingFinished.connect(lambda: self.pdf.go_to_page(self.page_box.value()))
        self.page_total = QtWidgets.QLabel()
        zoom_out = QtWidgets.QToolButton(text='−')
        zoom_in = QtWidgets.QToolButton(text='+')
        fit = QtWidgets.QToolButton(text='Fit width')
        self.highlighter = QtWidgets.QToolButton(text='🖍  Highlighter')
        self.highlighter.setCheckable(True)
        self.highlighter.setToolTip('When on, drag across text in the PDF to highlight it (saved in the PDF). '
                                    'Right-click a highlight to remove it. Shortcut: H')
        self.highlighter.setStyleSheet('QToolButton:checked { background:#ffe14d; border:1px solid #c9a400; }')
        self.highlighter.toggled.connect(self._toggle_highlighter)
        self.hl_count = QtWidgets.QLabel()
        preview = QtWidgets.QToolButton(text='Open in Preview')
        preview.clicked.connect(self._open_in_preview)
        for w in (self.page_box, self.page_total, zoom_out, zoom_in, fit, self.highlighter, self.hl_count):
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(preview)
        self.pdf = PdfView(self.paths)
        self.pdf.pageChanged.connect(self._on_page)
        self.pdf.highlightsChanged.connect(lambda n: self.hl_count.setText(f'{n} highlight{"s" if n != 1 else ""}'))
        self.pdf.message.connect(lambda m: self.statusBar().showMessage(m, 8000))
        zoom_out.clicked.connect(lambda: self.pdf.set_zoom(1 / 1.2))
        zoom_in.clicked.connect(lambda: self.pdf.set_zoom(1.2))
        fit.clicked.connect(self.pdf.fit)
        rv.addLayout(bar)
        rv.addWidget(self.pdf, 1)

        left.setMinimumWidth(200)
        mid.setMinimumWidth(320)
        right.setMinimumWidth(320)
        self.mid = mid
        self.split = QtWidgets.QSplitter()
        for w in (left, mid, right):
            self.split.addWidget(w)
        self.split.setChildrenCollapsible(False)        # a pane can be made narrow but never disappears
        self.split.setSizes([280, 540, 680])
        self.setCentralWidget(self.split)

        QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Save, self, activated=self.save_now)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+1'), self, activated=lambda: self.tabs.setCurrentIndex(0))
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+2'), self, activated=lambda: self.tabs.setCurrentIndex(1))
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Down'), self, activated=lambda: self._step(1))
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Up'), self, activated=lambda: self._step(-1))
        QtGui.QShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.ZoomIn), self, activated=lambda: self.pdf.set_zoom(1.2))
        QtGui.QShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.ZoomOut), self, activated=lambda: self.pdf.set_zoom(1 / 1.2))
        hl = QtGui.QShortcut(QtGui.QKeySequence('H'), self.pdf, activated=self.highlighter.toggle)
        hl.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.statusBar().showMessage('Ready. Your changes are saved automatically.', 6000)

    # ---- the paper list
    def _mark(self, p):
        st = self.status.get(p['key'])
        if st.get('notes_checked') and st.get('summary_checked'):
            return '✅'
        if st.get('notes_checked') or st.get('summary_checked'):
            return '◐'
        if st.get('edited'):
            return '✎'
        return '○'

    def _finished(self, p):
        st = self.status.get(p['key'])
        return bool(st.get('notes_checked') and st.get('summary_checked'))

    def _fill_list(self):
        want = self.search.text().strip().lower()
        mode = self.show_filter.currentIndex()
        keep = self.current['key'] if self.current else None
        self.list.blockSignals(True)
        self.list.clear()
        self.rows = []
        for k, p in enumerate(self.papers):
            text = f"[{p['n']}] {p['label']}  ·  {p['key']}"
            if want and want not in text.lower():
                continue
            if mode == 1 and self._finished(p) or mode == 2 and not self._finished(p) \
                    or mode == 3 and not self.status.get(p['key']).get('edited'):
                continue
            item = QtWidgets.QListWidgetItem(f"{self._mark(p)}  [{p['n']}] {p['label']}")
            item.setToolTip(f"{p['key']} — {p['folder']}")
            if self._finished(p):
                item.setForeground(QtGui.QColor('#17663a'))
            self.list.addItem(item)
            self.rows.append(k)
        self.list.blockSignals(False)
        if keep is not None:
            idx = next((r for r, k in enumerate(self.rows) if self.papers[k]['key'] == keep), None)
            if idx is not None:
                self.list.blockSignals(True)
                self.list.setCurrentRow(idx)
                self.list.blockSignals(False)
        done = sum(1 for p in self.papers if self._finished(p))
        self.progress.setText(f'<b>{done} of {len(self.papers)}</b> papers finished (notes and summary checked)')

    def _row_of(self, paper_index):
        return next((r for r, k in enumerate(self.rows) if k == paper_index), 0)

    def _refresh_item(self):
        if self.current is None:
            return
        row = next((r for r, k in enumerate(self.rows) if self.papers[k]['key'] == self.current['key']), None)
        if row is not None:
            item = self.list.item(row)
            item.setText(f"{self._mark(self.current)}  [{self.current['n']}] {self.current['label']}")
            item.setForeground(QtGui.QColor('#17663a' if self._finished(self.current) else '#1b1f24'))
        done = sum(1 for p in self.papers if self._finished(p))
        self.progress.setText(f'<b>{done} of {len(self.papers)}</b> papers finished (notes and summary checked)')

    def _step(self, d):
        row = self.list.currentRow() + d
        if 0 <= row < self.list.count():
            self.list.setCurrentRow(row)

    def _on_row(self, row):
        if row < 0 or row >= len(self.rows):
            return
        self.open_paper(self.papers[self.rows[row]])

    # ---- opening and saving
    def open_paper(self, p):
        self.save_now()
        self.current = p
        log(f"Paper [{p['n']}] {p['key']} opened")
        self.settings.setValue('last_paper', p['key'])
        key = p['key']
        self.docs = {
            'notes': TextDoc(key, 'notes', self.root / p['notes'], self.paths),
            'summary': TextDoc(key, 'summary', self.root / p['summary'], self.paths),
        }
        for name, ed in self.editors.items():
            ed.blockSignals(True)
            ed.setPlainText(self.docs[name].saved_text)
            ed.moveCursor(QtGui.QTextCursor.MoveOperation.Start)
            ed.blockSignals(False)
        st = self.status.get(key)
        for box, field in ((self.check_notes, 'notes_checked'), (self.check_summary, 'summary_checked')):
            box.blockSignals(True)
            box.setChecked(bool(st.get(field)))
            box.blockSignals(False)
        self.title.setText(f"[{p['n']}] {p['label']}")
        kind = {'included study (primary)': 'primary study', 'included study (secondary)': 'survey'}.get(p['role'], p['role'])
        self.subtitle.setText(f"{key} · {kind} · {Path(p['pdf']).name}")
        self.subtitle.setToolTip(str(self.root / p['pdf']))
        pdf = self.root / p['pdf']
        if pdf.exists():
            self.pdf.open(key, pdf)
        else:
            self.pdf.close_doc()
            self.statusBar().showMessage(f'PDF not found: {pdf}')
            log(f'  PDF NOT FOUND: {pdf}')
        self._update_chips()
        self._set_saved('All changes saved')

    def _on_edit(self):
        self._set_saved('Editing…')
        self.autosave.start()

    def _on_tab(self, _):
        self.save_now()
        self._update_chips()

    def save_now(self):
        if self.current is None or not self.docs:
            return
        self.autosave.stop()
        changed = False
        try:
            for name, ed in self.editors.items():
                if self.docs[name].save(ed.toPlainText()):
                    changed = True
                    log(f"  {name} saved ({self.current['key']}, {len(ed.toPlainText())} characters)")
        except OSError as err:
            log(f'  SAVE FAILED: {err}')
            self._set_saved('NOT SAVED — see message')
            QtWidgets.QMessageBox.critical(self, 'Could not save', f'Your text could not be saved:\n{err}\n\n'
                                           'It is still in the window; do not close the app. Copy it somewhere safe.')
            return
        if changed:
            self.status.set(self.current['key'], 'edited', True)
            self._refresh_item()
            self._update_chips()
        self._set_saved('All changes saved')

    def _set_saved(self, text):
        colour = '#17663a' if text.startswith('All') else ('#9a1b1b' if text.startswith('NOT') else '#7a4a00')
        self.saved_label.setText(f'<span style="color:{colour}">{text}</span>')

    def _set_check(self, field, value):
        if self.current is None:
            return
        self.save_now()
        self.status.set(self.current['key'], field, bool(value))
        log(f"  {field.replace('_', ' ')}: {'yes' if value else 'no'} ({self.current['key']})")
        self._refresh_item()

    # ---- pages
    def _update_chips(self):
        holder = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        ed = self.tabs.currentWidget()
        pages = cited_pages(ed.toPlainText()) if ed else []
        for pg in pages:
            b = QtWidgets.QToolButton(text=f'p{pg}')
            b.clicked.connect(lambda _=False, pg=pg: self._go(pg, ''))
            row.addWidget(b)
        if not pages:
            row.addWidget(QtWidgets.QLabel('none'))
        row.addStretch(1)
        self.chips_area.setWidget(holder)

    def _go(self, page, quote):
        if self.pdf.go_to_page(page, quote):
            self.statusBar().showMessage(f'Page {page}' + (' — quoted words outlined in red' if quote and self.pdf.marks else ''), 6000)

    def _on_page(self, page, total):
        self.page_box.blockSignals(True)
        self.page_box.setMaximum(total)
        self.page_box.setValue(page)
        self.page_box.blockSignals(False)
        self.page_total.setText(f'of {total}')

    def _toggle_highlighter(self, on):
        log(f"  highlighter {'on' if on else 'off'}")
        self.pdf.highlighter_on = on
        self.pdf.viewport().setCursor(Qt.CursorShape.IBeamCursor if on else Qt.CursorShape.ArrowCursor)
        for w in self.pdf.pages:
            w.setCursor(Qt.CursorShape.IBeamCursor if on else Qt.CursorShape.ArrowCursor)
        self.statusBar().showMessage('Highlighter on: drag across text to highlight it; right-click a highlight to remove it.'
                                     if on else 'Highlighter off.', 6000)

    def _open_in_preview(self):
        if self.current:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.root / self.current['pdf'])))

    def closeEvent(self, e):
        self.save_now()
        log('Quit: everything saved')
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('splitter', self.split.saveState())
        self.pdf.close_doc()
        super().closeEvent(e)


# --------------------------------------------------------------------------------------------------- self-test


class _NoSettings:
    def value(self, *_):
        return None

    def setValue(self, *_):
        pass


def self_test(screenshot: str | None) -> int:
    """Runs the app on generated sample files (never a real paper) and checks every promise it makes."""
    from PySide6.QtTest import QTest
    home = Path(tempfile.mkdtemp(prefix='.selftest-', dir=str(HERE)))
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(('PASS ' if cond else 'FAIL ') + label)

    try:
        papers = []
        for n, key in ((1, 'demo1'), (2, 'demo2')):
            folder = home / 'papers' / key
            (folder / 'notes').mkdir(parents=True)
            pdf = pymupdf.open()
            for pg in range(1, 4):
                page = pdf.new_page()
                page.insert_text((72, 100), f'Sample paper {key}, page {pg}.', fontsize=14)
                page.insert_text((72, 140), 'The authors propose a verifiable aggregation scheme for edge devices.', fontsize=11)
                page.insert_text((72, 160), 'Each client proves its update with a short zero knowledge proof.', fontsize=11)
            pdf.save(folder / f'{key}.pdf')
            (folder / 'notes' / 'NOTES.md').write_text(
                '# Notes\n- The scheme verifies aggregation. [p2] "propose a verifiable aggregation scheme"\n'
                '- Clients prove updates. [p3, image] "proves its update with a short zero knowledge proof"\n', encoding='utf-8')
            (folder / 'notes' / 'SUMMARY.md').write_text('A sample summary that cites [p1].\n', encoding='utf-8')
            papers.append({'key': key, 'n': n, 'label': f'Sample (2026) — Demo paper {n}', 'role': 'included study (primary)',
                           'folder': str(folder), 'pdf': str(folder / f'{key}.pdf'),
                           'notes': str(folder / 'notes' / 'NOTES.md'), 'summary': str(folder / 'notes' / 'SUMMARY.md')})
        paths = Paths(home)
        paths.data.mkdir(parents=True)
        paths.papers.write_text(json.dumps({'paper_version': 0, 'papers': papers}))

        win = MainWindow(paths, root=Path('/'),            # own settings file: your real app settings are not touched
                         settings=QtCore.QSettings(str(home / 'settings.ini'), QtCore.QSettings.Format.IniFormat))
        win.resize(1500, 900)
        win.show()
        win.list.setCurrentRow(0)
        QTest.qWait(200)
        check('the paper list shows both sample papers', win.list.count() == 2)
        check('the notes are loaded into the editor', 'verifies aggregation' in win.editors['notes'].toPlainText())

        line = win.editors['notes'].document().findBlockByNumber(1).text()
        check('a click on a statement finds its page and quotation',
              page_at(line, 3) == (2, 'propose a verifiable aggregation scheme'))
        check('a click on a page citation picks that page', page_at('- x. [p3, p5] "abc defgh"', 11) == (5, 'abc defgh'))
        check('ordinary reference numbers like [12] are not page links', page_at('as shown in [12] and [3]', 14) is None)
        win._go(2, 'propose a verifiable aggregation scheme')
        QTest.qWait(200)
        check('the PDF jumps to the cited page', win.pdf.current_page() == 2)
        check('the quoted words are found and outlined', bool(win.pdf.marks.get(1)))

        # a real mouse click on the notes line
        ed = win.editors['notes']
        cur = ed.textCursor()
        cur.setPosition(ed.document().findBlockByNumber(2).position() + 4)
        rect = ed.cursorRect(cur)
        QTest.mouseClick(ed.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        QTest.qWait(200)
        check('clicking the third line in the editor opens page 3', win.pdf.current_page() == 3)

        # editing and saving
        notes_path = Path(papers[0]['notes'])
        ed.setPlainText(ed.toPlainText() + '- An added statement. [p1]\n')
        QTest.qWait(AUTOSAVE_MS + 400)
        check('changes are saved automatically', 'An added statement' in notes_path.read_text(encoding='utf-8'))
        hist = home / 'history' / 'demo1'
        check('the original notes are kept in history', (hist / 'NOTES-original.md').exists()
              and 'An added statement' not in (hist / 'NOTES-original.md').read_text(encoding='utf-8'))
        check('the paper is marked as edited', win.status.get('demo1').get('edited') is True)

        # resizing: nothing may force the window wider than a laptop screen, and no pane may vanish
        check('the middle pane does not demand a huge width', win.mid.minimumSizeHint().width() < 700)
        win.resize(1000, 650)
        QTest.qWait(150)
        check('at 1000 px wide every pane is still visible', min(win.split.sizes()) >= 150 and win.width() <= 1100)
        win.split.setSizes([0, 0, 1000])
        QTest.qWait(100)
        check('dragging a divider cannot make the notes disappear', win.split.sizes()[1] >= 300)
        win.resize(1500, 900)
        QTest.qWait(150)

        # checking off
        win.check_notes.setChecked(True)
        win.check_summary.setChecked(True)
        saved = json.loads(paths.status.read_text())
        check('ticks are saved', saved['demo1']['notes_checked'] and saved['demo1']['summary_checked'])
        check('the progress counts the finished paper', '1 of 2' in win.progress.text())

        # highlighting with the mouse
        win.highlighter.setChecked(True)
        win.pdf.go_to_page(2)
        QTest.qWait(150)
        words = win.pdf.page_words(1)
        target = [k for k, w in enumerate(words) if w[4] in ('propose', 'scheme')]
        a = win.pdf._to_screen(1, pymupdf.Rect(words[target[0]][:4])).center().toPoint()
        b = win.pdf._to_screen(1, pymupdf.Rect(words[target[-1]][:4])).center().toPoint()
        pw = win.pdf.pages[1]
        QTest.mousePress(pw, Qt.MouseButton.LeftButton, pos=a)
        QTest.mouseMove(pw, b)
        ev = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, QtCore.QPointF(b), QtCore.QPointF(pw.mapToGlobal(b)),
                               Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QtWidgets.QApplication.sendEvent(pw, ev)
        QTest.mouseRelease(pw, Qt.MouseButton.LeftButton, pos=b)
        QTest.qWait(200)
        pdf_path = Path(papers[0]['pdf'])
        check_doc = pymupdf.open(pdf_path)
        n_hl = sum(1 for _ in check_doc[1].annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT]))
        hl_text = ''
        for annot in check_doc[1].annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT]):
            hl_text = check_doc[1].get_textbox(annot.rect)
        check_doc.close()
        check('a dragged highlight is saved in the PDF file', n_hl == 1)
        check('the highlight covers the dragged words', 'verifiable aggregation' in hl_text)
        original = home / 'originals' / 'demo1' / pdf_path.name
        orig_doc = pymupdf.open(original) if original.exists() else None
        check('an untouched copy of the PDF is kept before the first highlight',
              orig_doc is not None and sum(1 for pg in orig_doc for _ in pg.annots()) == 0)
        if orig_doc:
            orig_doc.close()
        if screenshot:
            win.grab().save(screenshot)
            print(f'screenshot: {screenshot}')

        # removing a highlight
        point = pymupdf.Point(*((words[target[0]][0] + words[target[0]][2]) / 2, (words[target[0]][1] + words[target[0]][3]) / 2))
        win.pdf.remove_highlight(1, point)
        reopened = pymupdf.open(pdf_path)
        check('a highlight can be removed', sum(1 for _ in reopened[1].annots()) == 0)
        reopened.close()

        # switching papers keeps everything
        win.list.setCurrentRow(1)
        QTest.qWait(150)
        win.list.setCurrentRow(0)
        QTest.qWait(150)
        check('edits are still there after switching papers', 'An added statement' in win.editors['notes'].toPlainText())
        win.close()
        check('quitting keeps the edits', 'An added statement' in notes_path.read_text(encoding='utf-8'))
        win.settings.sync()
        win.settings = _NoSettings()             # release the test settings file before the test folder is deleted
        import gc
        gc.collect()
    finally:
        shutil.rmtree(home, ignore_errors=True)
    print('ALL PASS' if ok else 'SOME CHECKS FAILED')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='Notes Verifier')
    ap.add_argument('--self-test', nargs='?', const='', metavar='SCREENSHOT.png',
                    help='run the checks on generated sample files (no real paper) and exit')
    args = ap.parse_args()
    faulthandler.enable()                         # a hard crash still prints where it happened
    sys.excepthook = log_exception                # any error is logged with its traceback, and the app keeps running
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('Notes Verifier')
    if args.self_test is not None:
        sys.exit(self_test(args.self_test or None))
    paths = Paths(HERE)
    if not paths.papers.exists():
        QtWidgets.QMessageBox.critical(None, 'Notes Verifier', 'The paper list is missing. Start the app with run.sh.')
        sys.exit(1)
    log(f'Notes Verifier started ({len(json.loads(paths.papers.read_text())["papers"])} papers)')
    win = MainWindow(paths)
    win.show()
    # A quit request from the terminal (Ctrl+C, or kill) closes the window normally, so everything is saved first.
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: QtCore.QTimer.singleShot(0, app.closeAllWindows))
    heartbeat = QtCore.QTimer(interval=300)        # lets Python notice such a request while Qt is waiting
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
