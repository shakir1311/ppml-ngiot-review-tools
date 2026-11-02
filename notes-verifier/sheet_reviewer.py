#!/usr/bin/env python3
"""Sheet Reviewer — check every fact of each evidence sheet against the study's PDF, and record that you did.

Left: the studies cited in the review, with how many of their answers you have verified.
Middle: the study's summary (read-only; click a page cite such as [p3] to open that page — summaries are edited in the
Notes Verifier), and below it the evidence sheet, one question at a time (P1, P2, P3 for a design, one per review
question; S1 for a survey; EXTRACTION-GUIDE-V3-2026-10-15.md): the answer, its tags (they feed the paper's tables) and its
quotations with pages — all editable. An answer merged on 15 October 2026 from parts of which one was new starts
unticked and says so: tick the quotations still unticked, then the answer, once checked against the PDF. Drag the divider to give either more room.
Right: the PDF, opened at the quoted page with the quoted words outlined; the highlighter works as in the Notes Verifier,
and a highlight you make there is added to the open answer as a quotation on that page, ticked as found (since 15 October).
The sheet's quotations are highlighted in the PDFs in yellow (highlight_sheet_quotes.py; hover shows "Evidence sheet").

Your record (notes-verifier/data/sheet-review.json), with the date and time of each tick:
  - a tick per quotation: "I found this quotation on this page of the PDF". It belongs to that page and those exact
    words: if the quotation is edited, its tick is cleared. "Tick all quotations" (one answer) and "Tick all quotations
    in this study" give the ticks at once; each is recorded with its time and how it was given ("tick all (answer)",
    "tick all (study)"); "Untick all" clears an answer's ticks.
  - a tick per answer: "the answer and its tags are right". Every answer you have not decided on is ticked by default
    (recorded as "default", shown ✓ on its tab; your own ticks are ✔ and recorded "by hand"); untick it where the
    answer or its tags are wrong — the untick is recorded and the default never returns. Ticking by hand needs every
    quotation of the answer ticked first; any tick is cleared if the answer or its tags change afterwards.
  - a note per answer, for anything the paper should change.
Sheet edits save automatically; the untouched original of every sheet you change is kept in notes-verifier/history/.

Start it with  notes-verifier/run-review.sh  or "Sheet Reviewer.command".
Self-test (no real paper is opened):  notes-verifier/run-review.sh --self-test [screenshot.png]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import signal
import sys
import tempfile
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

import app as nv                                          # PDF view, safe writing, logging
from app import HERE, ROOT, log, write_atomically
from evidence_app import SheetDoc, values_to_text, text_to_values   # safe sheet saving with history; tag editing

SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
GUIDE = ROOT / 'search-ppml' / 'evidence' / 'EXTRACTION-GUIDE-V3-2026-10-15.md'
AUTOSAVE_MS = nv.AUTOSAVE_MS
CITE = re.compile(r'\[(p\d+[^\[\]]*)\]')                # [p3], [p3, p11], [p4, image], [p6–p8]
PAGE = re.compile(r'p(\d+)(?:\s*[–-]\s*p?\d+)?')


def summary_markdown(text):
    """The summary as shown: without its title line (shown above it), each line kept as a line, and each page cite a
    link to its (first) page."""
    lines = text.splitlines()
    if lines and lines[0].startswith('# '):
        lines = lines[1:]

    def link(m):
        parts = [x.strip() for x in m.group(1).split(',')]
        return '\\[' + ', '.join(f'[{x}](page:{PAGE.match(x).group(1)})' if PAGE.match(x) else x
                                 for x in parts) + '\\]'
    kept = [line + '  ' if line.strip() else line for line in lines]          # two spaces: a Markdown line break
    return CITE.sub(link, '\n'.join(kept).strip())


def question_titles():
    import re
    titles = {}
    if GUIDE.exists():
        for m in re.finditer(r'^\| ([PS]\d+[a-z]?) \| \*\*(.+?)\*\*', GUIDE.read_text(encoding='utf-8'), re.M):
            titles[m.group(1)] = m.group(2).rstrip('.')
    return titles


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def fingerprint(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------------------------------- the review record


class Review:
    """What you have verified: per study and answer, the quotations found on their page and the answer itself."""

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

    def answer(self, key, q):
        return self.data.get(key, {}).get(q, {})

    def _entry(self, key, q):
        return self.data.setdefault(key, {}).setdefault(q, {})

    def quote_ok(self, key, q, page, quote):
        return fingerprint(page, quote) in self.answer(key, q).get('quotes', {})

    def set_quote(self, key, q, page, quote, value):
        quotes = self._entry(key, q).setdefault('quotes', {})
        fp = fingerprint(page, quote)
        if value:
            quotes[fp] = {'page': page, 'verified_on': now()}
        else:
            quotes.pop(fp, None)
        self.save()

    def set_quotes(self, key, q, evidence, value, how):
        """Tick (or untick) several quotations at once; a new tick records how it was given. Returns how many changed."""
        quotes = self._entry(key, q).setdefault('quotes', {})
        changed = 0
        for ev in evidence:
            fp = fingerprint(ev.get('page'), ev.get('quote', ''))
            if value and fp not in quotes:
                quotes[fp] = {'page': ev.get('page'), 'verified_on': now(), 'how': how}
                changed += 1
            elif not value and fp in quotes:
                del quotes[fp]
                changed += 1
        self.save()
        return changed

    def answer_ok(self, key, q, ans):
        rec = self.answer(key, q)
        return bool(rec.get('verified')) and rec.get('answer_fingerprint') == fingerprint(ans.get('answer'), ans.get('values'))

    def is_default(self, key, q):
        return self.answer(key, q).get('how') == 'default'

    def set_answer(self, key, q, ans, value):
        e = self._entry(key, q)
        if value:
            e.pop('unticked_on', None)
            e.update({'verified': True, 'verified_on': now(), 'how': 'by hand',
                      'answer_fingerprint': fingerprint(ans.get('answer'), ans.get('values'))})
        else:                                               # an untick is kept, so the default never returns
            for k in ('verified_on', 'answer_fingerprint', 'how'):
                e.pop(k, None)
            e.update({'verified': False, 'unticked_on': now()})
        self.save()

    def apply_defaults(self, sheets):
        """Tick by default every answer you have not decided on yet (no tick or untick of yours), recorded as
        "default". sheets: {key: answers}. Returns how many were ticked."""
        n = 0
        for key, answers in sheets.items():
            for q, ans in answers.items():
                e = self._entry(key, q)
                if 'verified' not in e:
                    e.update({'verified': True, 'verified_on': now(), 'how': 'default',
                              'answer_fingerprint': fingerprint(ans.get('answer'), ans.get('values'))})
                    n += 1
        if n:
            self.save()
        return n

    def note(self, key, q):
        return self.answer(key, q).get('note', '')

    def set_note(self, key, q, text):
        e = self._entry(key, q)
        if text.strip():
            e.update({'note': text, 'note_on': now()})
        else:
            e.pop('note', None)
            e.pop('note_on', None)
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(self.path, json.dumps(self.data, indent=1, ensure_ascii=False))


# --------------------------------------------------------------------------------------------------- main window


class ReviewWindow(QtWidgets.QMainWindow):
    def __init__(self, paths: nv.Paths, root: Path = ROOT, sheets: Path = SHEETS,
                 settings: QtCore.QSettings | None = None):
        super().__init__()
        self.paths, self.root, self.sheets_dir = paths, root, sheets
        listing = json.loads(paths.papers.read_text())
        self.studies = [p for p in listing['papers'] if (sheets / f"{p['key']}.json").exists()]
        self.review = Review(paths.data / 'sheet-review.json')
        n = self.review.apply_defaults({p['key']: json.loads((sheets / f"{p['key']}.json").read_text(encoding='utf-8'))
                                        ['answers'] for p in self.studies})
        if n:
            log(f'  {n} answers ticked by default (recorded as "default"; untick where needed)')
        self.settings = settings or QtCore.QSettings('Abertay', 'SheetReviewer')
        self.titles = question_titles()
        self.current = self.sheet = self.q = None
        self.loading = False
        self.setWindowTitle('Sheet Reviewer — evidence sheets against the PDFs')
        self._build()
        self.autosave = QtCore.QTimer(self, singleShot=True, interval=AUTOSAVE_MS, timeout=self.save_now)
        self._fill_list()
        last = self.settings.value('last_study')
        row = next((r for r, k in enumerate(self.rows) if self.studies[k]['key'] == last), 0)
        self.list.setCurrentRow(row)
        geo = self.settings.value('geometry')
        if geo:
            self.restoreGeometry(geo)
        else:
            avail = self._available()
            self.resize(int(avail.width() * 0.94), int(avail.height() * 0.9))
        state = self.settings.value('split')
        if state:
            self.split.restoreState(state)
        state = self.settings.value('summary_split')
        if state:
            self.mid_split.restoreState(state)
        self._fit_on_screen()

    # ---- screen
    def _available(self):
        return (self.screen() or QtGui.QGuiApplication.primaryScreen()).availableGeometry()

    def _fit_on_screen(self):
        avail = self._available()
        w, h = min(self.width(), avail.width() - 20), min(self.height(), avail.height() - 20)
        self.resize(w, h)
        self.move(min(max(self.x(), avail.left()), avail.left() + avail.width() - w),
                  min(max(self.y(), avail.top()), avail.top() + avail.height() - h))
        if min(self.split.sizes()) < 150:
            self.split.setSizes([int(w * 0.16), int(w * 0.40), int(w * 0.44)])

    # ---- layout
    def _build(self):
        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 4, 8)
        self.search = QtWidgets.QLineEdit(placeholderText='Search studies')
        self.search.textChanged.connect(self._fill_list)
        self.show_filter = QtWidgets.QComboBox()
        self.show_filter.addItems(['All studies', 'Not finished', 'Finished', 'With my notes'])
        self.show_filter.currentIndexChanged.connect(self._fill_list)
        self.progress = QtWidgets.QLabel()
        self.progress.setWordWrap(True)
        self.list = QtWidgets.QListWidget()
        self.list.setWordWrap(True)
        self.list.currentRowChanged.connect(self._on_row)
        for w in (self.search, self.show_filter, self.progress):
            lv.addWidget(w)
        lv.addWidget(self.list, 1)

        middle = QtWidgets.QWidget()
        mv = QtWidgets.QVBoxLayout(middle)
        mv.setContentsMargins(4, 8, 4, 8)
        self.title = QtWidgets.QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet('font-size:15px; font-weight:600;')
        self.subtitle = QtWidgets.QLabel()
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet('color:#59616c;')
        nav = QtWidgets.QHBoxLayout()
        for text, d in (('◀ Previous study', -1), ('Next study ▶', 1)):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(lambda _=False, d=d: self._step(d))
            nav.addWidget(b)
        nav.addStretch(1)
        tick_study = QtWidgets.QPushButton('✓ Tick all quotations in this study')
        tick_study.setToolTip('Record every quotation of every answer of this study as found on its page; the answers '
                              'themselves are still ticked one by one')
        tick_study.clicked.connect(lambda: self._tick_study())
        nav.addWidget(tick_study)
        self.qbar = QtWidgets.QTabBar()
        self.qbar.setExpanding(False)
        self.qbar.currentChanged.connect(self._on_question)

        detail = QtWidgets.QWidget()
        dv = QtWidgets.QVBoxLayout(detail)
        dv.setContentsMargins(0, 4, 0, 0)
        self.qtitle = QtWidgets.QLabel()
        self.qtitle.setWordWrap(True)
        self.qtitle.setStyleSheet('font-weight:600;')
        self.answer = QtWidgets.QPlainTextEdit()
        self.answer.setMinimumHeight(110)
        self.answer.textChanged.connect(self._on_answer_edit)
        self.values_form = QtWidgets.QFormLayout()
        self.values_holder = QtWidgets.QWidget()
        self.values_holder.setLayout(self.values_form)
        self.evidence = QtWidgets.QTableWidget(0, 3)
        self.evidence.setHorizontalHeaderLabels(['Found in PDF', 'Page', 'Quotation (click a row to see it in the PDF)'])
        hh = self.evidence.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.evidence.verticalHeader().setVisible(False)
        self.evidence.setWordWrap(True)
        self.evidence.setMinimumHeight(160)
        self.evidence.itemChanged.connect(self._on_evidence_item)
        self.evidence.currentCellChanged.connect(lambda r, *_: self._show_evidence(r))
        ev_buttons = QtWidgets.QHBoxLayout()
        tick_all = QtWidgets.QPushButton('✓ Tick all quotations')
        tick_all.setToolTip('Record every quotation of this answer as found on its page (each tick is saved with the '
                            'time and "tick all")')
        untick_all = QtWidgets.QPushButton('Untick all')
        add_ev = QtWidgets.QPushButton('+ Add quotation')
        del_ev = QtWidgets.QPushButton('Remove selected quotation')
        tick_all.clicked.connect(lambda: self._tick_all(True))
        untick_all.clicked.connect(lambda: self._tick_all(False))
        add_ev.clicked.connect(self._add_evidence)
        del_ev.clicked.connect(self._remove_evidence)
        for b in (tick_all, untick_all):
            ev_buttons.addWidget(b)
        ev_buttons.addSpacing(16)
        ev_buttons.addWidget(add_ev)
        ev_buttons.addWidget(del_ev)
        ev_buttons.addStretch(1)
        self.answer_ok = QtWidgets.QCheckBox('The answer and its tags are right (verified against the PDF)')
        self.answer_ok.toggled.connect(self._on_answer_ok)
        self.answer_ok_info = QtWidgets.QLabel()
        self.answer_ok_info.setStyleSheet('color:#59616c;')
        self.note = QtWidgets.QPlainTextEdit(placeholderText='My note on this answer (what the paper should change, if '
                                                             'anything) — saved with my review')
        self.note.setMaximumHeight(70)
        self.note.textChanged.connect(self._on_note_edit)
        self.saved_label = QtWidgets.QLabel()
        dv.addWidget(self.qtitle)
        dv.addWidget(QtWidgets.QLabel('<b>Answer</b>'))
        dv.addWidget(self.answer, 2)
        dv.addWidget(QtWidgets.QLabel('<b>Tags</b> (comma-separated; they feed the paper\'s tables)'))
        dv.addWidget(self.values_holder)
        dv.addWidget(QtWidgets.QLabel('<b>Quotations</b> — tick each one you have found on its page; double-click to '
                                      'correct a page or a quotation'))
        dv.addWidget(self.evidence, 3)
        dv.addLayout(ev_buttons)
        dv.addWidget(self.answer_ok)
        dv.addWidget(self.answer_ok_info)
        dv.addWidget(self.note)
        dv.addWidget(self.saved_label)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(detail)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        sheet_part = QtWidgets.QWidget()
        sv = QtWidgets.QVBoxLayout(sheet_part)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.addWidget(self.qbar)
        sv.addWidget(scroll, 1)
        summary_part = QtWidgets.QWidget()
        smv = QtWidgets.QVBoxLayout(summary_part)
        smv.setContentsMargins(0, 0, 0, 4)
        smv.addWidget(QtWidgets.QLabel('<b>Summary</b> <span style="color:#59616c">(read-only — click a page to open it; '
                                       'edit summaries in the Notes Verifier)</span>'))
        self.summary = QtWidgets.QTextBrowser()
        self.summary.setOpenLinks(False)
        self.summary.anchorClicked.connect(self._on_summary_link)
        self.summary.setStyleSheet('QTextBrowser { font-size:13px; }')
        smv.addWidget(self.summary, 1)
        self.mid_split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.mid_split.addWidget(summary_part)
        self.mid_split.addWidget(sheet_part)
        self.mid_split.setChildrenCollapsible(False)
        summary_part.setMinimumHeight(70)
        sheet_part.setMinimumHeight(240)
        self.mid_split.setSizes([230, 620])
        mv.addWidget(self.title)
        mv.addWidget(self.subtitle)
        mv.addLayout(nav)
        mv.addWidget(self.mid_split, 1)

        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(4, 8, 8, 8)
        bar = QtWidgets.QHBoxLayout()
        self.page_box = QtWidgets.QSpinBox(minimum=1, maximum=1)
        self.page_box.setPrefix('Page ')
        self.page_box.editingFinished.connect(lambda: self.pdf.go_to_page(self.page_box.value()))
        self.page_total = QtWidgets.QLabel()
        zoom_out, zoom_in = QtWidgets.QToolButton(text='−'), QtWidgets.QToolButton(text='+')
        fit = QtWidgets.QToolButton(text='Fit width')
        self.highlighter = QtWidgets.QToolButton(text='🖍  Highlighter')
        self.highlighter.setCheckable(True)
        self.highlighter.setStyleSheet('QToolButton:checked { background:#ffe14d; border:1px solid #c9a400; }')
        self.highlighter.setToolTip('Drag across text in the PDF to highlight it (saved in the PDF). Right-click to remove.')
        self.highlighter.toggled.connect(self._toggle_highlighter)
        self.hl_count = QtWidgets.QLabel()
        preview = QtWidgets.QToolButton(text='Open in Preview')
        preview.clicked.connect(lambda: self.current and QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(self.root / self.current['pdf']))))
        for w in (self.page_box, self.page_total, zoom_out, zoom_in, fit, self.highlighter, self.hl_count):
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(preview)
        self.pdf = nv.PdfView(self.paths)
        self.pdf.pageChanged.connect(self._on_page)
        self.pdf.highlightsChanged.connect(lambda n: self.hl_count.setText(f'{n} highlight{"s" if n != 1 else ""}'))
        self.pdf.highlightAdded.connect(self._on_highlight_added)
        self.pdf.message.connect(lambda m: self.statusBar().showMessage(m, 8000))
        zoom_out.clicked.connect(lambda: self.pdf.set_zoom(1 / 1.2))
        zoom_in.clicked.connect(lambda: self.pdf.set_zoom(1.2))
        fit.clicked.connect(self.pdf.fit)
        rv.addLayout(bar)
        rv.addWidget(self.pdf, 1)

        left.setMinimumWidth(180)
        middle.setMinimumWidth(380)
        right.setMinimumWidth(320)
        self.split = QtWidgets.QSplitter()
        for w in (left, middle, right):
            self.split.addWidget(w)
        self.split.setChildrenCollapsible(False)
        self.split.setSizes([240, 660, 680])
        self.setCentralWidget(self.split)
        QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Save, self, activated=self.save_now)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Down'), self, activated=lambda: self._step(1))
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Up'), self, activated=lambda: self._step(-1))
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Right'), self, activated=lambda: self._step_q(1))
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Left'), self, activated=lambda: self._step_q(-1))
        self.statusBar().showMessage('Ready. Your ticks, notes and edits are saved automatically.', 6000)

    # ---- progress
    def _sheet_data(self, key):
        if self.current and self.current['key'] == key and self.sheet:
            return self.sheet.data
        return json.loads((self.sheets_dir / f'{key}.json').read_text(encoding='utf-8'))

    def _verified_count(self, key):
        answers = self._sheet_data(key)['answers']
        return sum(self.review.answer_ok(key, q, a) for q, a in answers.items()), len(answers)

    def _has_notes(self, key):
        return any(r.get('note') for r in self.review.data.get(key, {}).values())

    def _item_text(self, s):
        done, total = self._verified_count(s['key'])
        mark = '✅' if done == total else ('◐' if done else '·')
        note = ' ✎' if self._has_notes(s['key']) else ''
        return f"{mark} {done}/{total}{note}  [{s['n']}] {s['label']}"

    def _fill_list(self):
        want, mode = self.search.text().strip().lower(), self.show_filter.currentIndex()
        keep = self.current['key'] if self.current else None
        self.list.blockSignals(True)
        self.list.clear()
        self.rows = []
        for k, s in enumerate(self.studies):
            if want and want not in f"[{s['n']}] {s['label']} {s['key']}".lower():
                continue
            done, total = self._verified_count(s['key'])
            if (mode == 1 and done == total) or (mode == 2 and done < total) or (mode == 3 and not self._has_notes(s['key'])):
                continue
            item = QtWidgets.QListWidgetItem(self._item_text(s))
            item.setToolTip(s['key'])
            if done == total:
                item.setForeground(QtGui.QColor('#17663a'))
            self.list.addItem(item)
            self.rows.append(k)
        if keep is not None:
            row = next((r for r, k in enumerate(self.rows) if self.studies[k]['key'] == keep), None)
            if row is not None:
                self.list.setCurrentRow(row)
        self.list.blockSignals(False)
        self._update_progress()

    def _update_progress(self):
        answers = verified = finished = default = 0
        for s in self.studies:
            d, t = self._verified_count(s['key'])
            answers, verified, finished = answers + t, verified + d, finished + (d == t)
            default += sum(self.review.is_default(s['key'], q) and self.review.answer_ok(s['key'], q, a)
                           for q, a in self._sheet_data(s['key'])['answers'].items())
        self.progress.setText(f'<b>{verified} of {answers}</b> answers ticked ({verified - default} by you, {default} by '
                              f'default) · {finished} of {len(self.studies)} sheets fully ticked')

    def _refresh_item(self):
        row = next((r for r, k in enumerate(self.rows) if self.studies[k]['key'] == self.current['key']), None)
        if row is not None:
            done, total = self._verified_count(self.current['key'])
            self.list.item(row).setText(self._item_text(self.current))
            self.list.item(row).setForeground(QtGui.QColor('#17663a' if done == total else '#1b1f24'))
        self._update_progress()

    def _step(self, d):
        r = self.list.currentRow() + d
        if 0 <= r < self.list.count():
            self.list.setCurrentRow(r)

    def _step_q(self, d):
        i = self.qbar.currentIndex() + d
        if 0 <= i < self.qbar.count():
            self.qbar.setCurrentIndex(i)

    def _on_row(self, row):
        if 0 <= row < len(self.rows):
            self.open_study(self.studies[self.rows[row]])

    # ---- a study
    def open_study(self, s):
        self.save_now()
        self.current = s
        key = s['key']
        log(f"Study [{s['n']}] {key} opened")
        self.settings.setValue('last_study', key)
        self.sheet = SheetDoc(key, self.sheets_dir / f'{key}.json', self.paths)
        self.title.setText(f"[{s['n']}] {s['label']}")
        kind = 'survey' if next(iter(self.sheet.data['answers']), 'P').startswith('S') else 'primary study'
        self.subtitle.setText(f"{key} · {kind} · {Path(s['pdf']).name}")
        self.subtitle.setToolTip(str(self.root / s['pdf']))
        self._show_summary(s)
        pdf = self.root / s['pdf']
        if pdf.exists():
            self.pdf.open(key, pdf)
        self.qbar.blockSignals(True)
        while self.qbar.count():
            self.qbar.removeTab(0)
        for q in self.sheet.data['answers']:
            self.qbar.addTab(self._tab_label(q))
        self.qbar.blockSignals(False)
        first = next((i for i, (q, a) in enumerate(self.sheet.data['answers'].items())
                      if not self.review.answer_ok(key, q, a)), 0)
        self.qbar.setCurrentIndex(first)
        self._on_question(first)
        self._set_saved('All changes saved')

    def _show_summary(self, s):
        path = self.root / s['summary'] if s.get('summary') else None
        if path and path.exists():
            self.summary.setMarkdown(summary_markdown(path.read_text(encoding='utf-8')))
        else:
            self.summary.setPlainText('No summary for this study.')

    def _on_summary_link(self, url):
        if url.scheme() == 'page' and url.path().isdigit():
            log(f"  summary cite: page {url.path()}")
            self.pdf.go_to_page(int(url.path()))

    def _tab_label(self, q):
        ok = self.review.answer_ok(self.current['key'], q, self.sheet.data['answers'][q])
        note = ' ✎' if self.review.note(self.current['key'], q) else ''
        mark = (' ✓' if self.review.is_default(self.current['key'], q) else ' ✔') if ok else ''   # ✓ default, ✔ yours
        return f"{q}{mark}{note}"

    def _refresh_tab(self):
        self.qbar.setTabText(self.qbar.currentIndex(), self._tab_label(self.q))

    def _on_question(self, index):
        if self.sheet is None or index < 0:
            return
        self.save_now()
        self.q = list(self.sheet.data['answers'])[index]
        ans = self._answer()
        self.loading = True
        self.qtitle.setText(f"{self.q} — {self.titles.get(self.q, '')}")
        self.answer.setPlainText(ans.get('answer', ''))
        while self.values_form.rowCount():
            self.values_form.removeRow(0)
        self.value_edits = {}
        for k, v in (ans.get('values') or {}).items():
            e = QtWidgets.QLineEdit(values_to_text(v))
            e.textChanged.connect(lambda _t, k=k: self._on_value_edit(k))
            self.value_edits[k] = e
            self.values_form.addRow(k, e)
        if not ans.get('values'):
            self.values_form.addRow(QtWidgets.QLabel('— none for this question —'))
        self._fill_evidence()
        self.note.setPlainText(self.review.note(self.current['key'], self.q))
        self._sync_answer_ok()
        self.loading = False
        if self.evidence.rowCount():
            self.evidence.setCurrentCell(0, 2)
            self._show_evidence(0)

    def _answer(self):
        return self.sheet.data['answers'][self.q]

    # ---- quotations
    def _fill_evidence(self):
        key = self.current['key']
        self.evidence.blockSignals(True)
        self.evidence.setRowCount(0)
        for ev in self._answer().get('evidence') or []:
            r = self.evidence.rowCount()
            self.evidence.insertRow(r)
            tick = QtWidgets.QTableWidgetItem()
            tick.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            tick.setCheckState(Qt.CheckState.Checked if self.review.quote_ok(key, self.q, ev.get('page'), ev.get('quote', ''))
                               else Qt.CheckState.Unchecked)
            self.evidence.setItem(r, 0, tick)
            self.evidence.setItem(r, 1, QtWidgets.QTableWidgetItem(str(ev.get('page', ''))))
            self.evidence.setItem(r, 2, QtWidgets.QTableWidgetItem(ev.get('quote', '')))
            if ev.get('source') in ('table', 'image'):
                self.evidence.item(r, 2).setToolTip(f"Read from a {ev['source']} on that page")
        self.evidence.resizeRowsToContents()
        self.evidence.blockSignals(False)

    def _show_evidence(self, r):
        if r < 0 or self.evidence.item(r, 2) is None:
            return
        try:
            page = int(self.evidence.item(r, 1).text())
        except ValueError:
            return
        self.pdf.go_to_page(page, self.evidence.item(r, 2).text())

    def _on_evidence_item(self, item):
        if self.loading:
            return
        r, key = item.row(), self.current['key']
        evs = self._answer().setdefault('evidence', [])
        if item.column() == 0:                             # the tick: "found on this page"
            ev = evs[r]
            on = item.checkState() == Qt.CheckState.Checked
            self.review.set_quote(key, self.q, ev.get('page'), ev.get('quote', ''), on)
            log(f"  {key} {self.q} quotation {r + 1} found in PDF: {'yes' if on else 'no'}")
            self._sync_answer_ok()
            return
        page_text = self.evidence.item(r, 1).text().strip()
        if not page_text.isdigit():                        # a page must stay a number: put the old one back
            self.evidence.blockSignals(True)
            self.evidence.item(r, 1).setText(str(evs[r].get('page') or ''))
            self.evidence.blockSignals(False)
            self.statusBar().showMessage('A page must be a number (the PDF page).', 6000)
            return
        evs[r]['page'], evs[r]['quote'] = int(page_text), self.evidence.item(r, 2).text()
        self.evidence.blockSignals(True)                  # an edited quotation has not been found yet
        self.evidence.item(r, 0).setCheckState(Qt.CheckState.Checked if self.review.quote_ok(
            key, self.q, evs[r]['page'], evs[r]['quote']) else Qt.CheckState.Unchecked)
        self.evidence.blockSignals(False)
        self._changed()

    def _on_highlight_added(self, page, text):
        """A highlight made in the PDF becomes a quotation of the open answer, on that page, and is ticked as found there
        (recorded "highlighted"); the same page and words are never added twice."""
        if self.sheet is None or self.q is None or not text.strip():
            return
        squash = lambda t: re.sub(r'[^0-9a-z]', '', t.lower())
        evs = self._answer().setdefault('evidence', [])
        if any(e.get('page') == page and squash(str(e.get('quote') or '')) == squash(text) for e in evs):
            self.statusBar().showMessage(f'That quotation is already in {self.q} (page {page}).', 6000)
            return
        evs.append({'page': page, 'quote': text})
        self._changed()
        self.review.set_quotes(self.current['key'], self.q, [evs[-1]], True, 'highlighted')
        self._fill_evidence()
        self._sync_answer_ok()
        n = len(text.split())
        self.statusBar().showMessage(f'Added to {self.q} as a quotation on page {page} and ticked as found there'
                                     + (f' — {n} words; the form asks for 5 to 40.' if n > 40 or n < 5 else '.'), 8000)
        log(f"  {self.current['key']} {self.q}: highlight on page {page} added as a quotation ({n} words) and ticked")

    def _add_evidence(self):
        if self.sheet is None:
            return
        self._answer().setdefault('evidence', []).append({'page': self.pdf.current_page(), 'quote': ''})
        self._fill_evidence()
        r = self.evidence.rowCount() - 1
        self.evidence.setCurrentCell(r, 2)
        self.evidence.editItem(self.evidence.item(r, 2))
        self._changed()

    def _remove_evidence(self):
        r = self.evidence.currentRow()
        evs = self._answer().get('evidence') or []
        if 0 <= r < len(evs):
            if QtWidgets.QMessageBox.question(self, 'Remove quotation', f'Remove this quotation from {self.q}?\n\n'
                                              f'p{evs[r].get("page")}: “{evs[r].get("quote", "")[:200]}”') \
                    != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            del evs[r]
            self._fill_evidence()
            self._changed()

    def _tick_all(self, value):
        if self.sheet is None or self.q is None:
            return
        key = self.current['key']
        n = self.review.set_quotes(key, self.q, self._answer().get('evidence') or [], value, 'tick all (answer)')
        log(f"  {key} {self.q}: {'ticked' if value else 'unticked'} all quotations ({n} changed)")
        self._after_ticks(f"{n} quotation{'s' if n != 1 else ''} {'ticked' if value else 'unticked'} in {self.q}.")

    def _tick_study(self, confirm=True):
        if self.sheet is None:
            return
        key = self.current['key']
        answers = self.sheet.data['answers']
        total = sum(len(a.get('evidence') or []) for a in answers.values())
        if confirm and QtWidgets.QMessageBox.question(
                self, 'Tick all quotations in this study',
                f'Record all {total} quotations of {key} as found on their pages in the PDF?\n\nEach tick is saved with '
                'the date and time and marked "tick all (study)". The answers are still ticked one by one.') \
                != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        n = sum(self.review.set_quotes(key, q, a.get('evidence') or [], True, 'tick all (study)')
                for q, a in answers.items())
        log(f'  {key}: ticked all quotations of the study ({n} new)')
        for i, q in enumerate(answers):
            self.qbar.setTabText(i, self._tab_label(q))
        self._after_ticks(f'{n} quotation{"s" if n != 1 else ""} ticked in {key}.')

    def _after_ticks(self, message):
        self.loading = True
        self._fill_evidence()
        self.loading = False
        self._sync_answer_ok()
        self._refresh_tab()
        self._refresh_item()
        self.statusBar().showMessage(message + ' Saved in your review record.', 6000)

    # ---- the answer
    def _all_quotes_found(self):
        key = self.current['key']
        return all(self.review.quote_ok(key, self.q, e.get('page'), e.get('quote', ''))
                   for e in self._answer().get('evidence') or [])

    def _sync_answer_ok(self):
        key, ans = self.current['key'], self._answer()
        ok = self.review.answer_ok(key, self.q, ans)
        rec = self.review.answer(key, self.q)
        quotes_done = self._all_quotes_found()
        self.answer_ok.blockSignals(True)
        self.answer_ok.setChecked(ok)
        self.answer_ok.setEnabled(ok or quotes_done)
        self.answer_ok.blockSignals(False)
        if ok and rec.get('how') == 'default':
            self.answer_ok_info.setText('Ticked by default — untick it if the answer or its tags are wrong.')
        elif ok:
            self.answer_ok_info.setText(f"Verified on {rec.get('verified_on', '').replace('T', ' ')}")
        elif rec.get('verified'):
            self.answer_ok_info.setText('The answer or its tags changed after you verified them: please check again.')
        elif rec.get('new_on') and not rec.get('unticked_on'):
            n = sum(not self.review.quote_ok(key, self.q, e.get('page'), e.get('quote', ''))
                    for e in ans.get('evidence') or [])
            what = ('merged on ' + rec['new_on'][:10] + ' from parts of which one or more are new facts drafted from the notes and the page text'
                    if rec.get('how') == 'merged with new facts' else 'new answer of ' + rec['new_on'][:10] + ', drafted from the notes and the page text')
            self.answer_ok_info.setText(f"This answer was {what}: check the answer, its tags and the quotations against the PDF"
                                        + (f' ({n} quotations still to tick).' if n else ', then tick it.'))
        elif rec.get('unticked_on') and quotes_done:
            self.answer_ok_info.setText(f"You unticked this on {rec['unticked_on'].replace('T', ' ')}.")
        elif rec.get('unticked_on'):
            n = sum(not self.review.quote_ok(key, self.q, e.get('page'), e.get('quote', ''))
                    for e in ans.get('evidence') or [])
            self.answer_ok_info.setText(f"You unticked this on {rec['unticked_on'].replace('T', ' ')}. To tick it "
                                        f"again, tick its quotations first ({n} to go).")
        elif not quotes_done:
            n = sum(not self.review.quote_ok(key, self.q, e.get('page'), e.get('quote', ''))
                    for e in ans.get('evidence') or [])
            self.answer_ok_info.setText(f'Tick each quotation you have found in the PDF first ({n} to go).')
        else:
            self.answer_ok_info.setText('')
        self._refresh_tab()
        self._refresh_item()

    def _on_answer_ok(self, value):
        if self.loading or self.current is None:
            return
        self.save_now()
        self.review.set_answer(self.current['key'], self.q, self._answer(), bool(value))
        log(f"  {self.current['key']} {self.q} answer verified: {'yes' if value else 'no'}")
        self._sync_answer_ok()

    def _on_note_edit(self):
        if self.loading or self.current is None:
            return
        self.review.set_note(self.current['key'], self.q, self.note.toPlainText())
        self._refresh_tab()

    # ---- editing the sheet
    def _on_answer_edit(self):
        if self.loading or self.sheet is None:
            return
        self._answer()['answer'] = self.answer.toPlainText()
        self._changed()

    def _on_value_edit(self, k):
        if self.loading:
            return
        ans = self._answer()
        ans['values'][k] = text_to_values(self.value_edits[k].text(), ans['values'][k])
        self._changed()

    def _changed(self):
        self._set_saved('Editing…')
        self.autosave.start()
        self._sync_answer_ok()

    def save_now(self):
        if self.current is None or self.sheet is None:
            return
        self.autosave.stop()
        try:
            if self.sheet.save():
                log(f"  evidence sheet saved ({self.current['key']}, {self.q})")
        except (OSError, ValueError) as err:
            log(f'  SAVE FAILED: {err}')
            self._set_saved('NOT SAVED — see message')
            QtWidgets.QMessageBox.critical(self, 'Could not save', f'Your changes could not be saved:\n{err}\n\n'
                                           'They are still in the window; do not close the app.')
            return
        self._set_saved('All changes saved')

    def _set_saved(self, text):
        colour = '#17663a' if text.startswith('All') else ('#9a1b1b' if text.startswith('NOT') else '#7a4a00')
        self.saved_label.setText(f'<span style="color:{colour}">{text}</span>')

    # ---- PDF
    def _on_page(self, page, total):
        self.page_box.blockSignals(True)
        self.page_box.setMaximum(total)
        self.page_box.setValue(page)
        self.page_box.blockSignals(False)
        self.page_total.setText(f'of {total}')

    def _toggle_highlighter(self, on):
        log(f"  highlighter {'on' if on else 'off'}")
        self.pdf.highlighter_on = on
        for w in self.pdf.pages:
            w.setCursor(Qt.CursorShape.IBeamCursor if on else Qt.CursorShape.ArrowCursor)

    def closeEvent(self, e):
        self.save_now()
        log('Quit: everything saved')
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('split', self.split.saveState())
        self.settings.setValue('summary_split', self.mid_split.saveState())
        self.pdf.close_doc()
        super().closeEvent(e)


def _esc(text):
    return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# --------------------------------------------------------------------------------------------------- self-test


def self_test(screenshot: str | None) -> int:
    """Runs the app on generated sample files (never a real paper) and checks what it promises."""
    import pymupdf
    from PySide6.QtTest import QTest
    home = Path(tempfile.mkdtemp(prefix='.selftest-rv-', dir=str(HERE)))
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(('PASS ' if cond else 'FAIL ') + label)

    try:
        folder = home / 'papers' / 'demo1'
        folder.mkdir(parents=True)
        pdf = pymupdf.open()
        for pg in range(1, 4):
            page = pdf.new_page()
            page.insert_text((72, 100), f'Sample paper, page {pg}.', fontsize=14)
            page.insert_text((72, 140), 'The ledger is a consortium chain run by the edge servers of the operators.', fontsize=11)
        pdf.save(folder / 'demo1.pdf')
        (folder / 'SUMMARY.md').write_text('# DEMO · Sample 2026\n*Demo venue*\n\n**Ledger.** A consortium chain run by the '
                                           'edge servers. [p2] [p3, image]\n**Privacy.** None stated. [p1–p2]\n',
                                           encoding='utf-8')
        sheets = home / 'sheets'
        sheets.mkdir()
        original = json.dumps({'id': 'demo1', 'kind': 'primary', 'answers': {
            'P1': {'answer': 'IoV setting.', 'values': {'settings': ['IoV-vehicular']}, 'evidence': [], 'located_via': 'summary'},
            'P3': {'answer': 'A consortium chain.', 'values': {'ledger': ['consortium-permissioned'], 'onchain_ok': True},
                   'evidence': [{'page': 2, 'quote': 'The ledger is a consortium chain run by the edge servers'},
                                {'page': 3, 'quote': 'consortium chain run by the edge servers of the operators'}],
                   'located_via': 'notes'}}}, indent=2)
        (sheets / 'demo1.json').write_text(original, encoding='utf-8')
        paths = nv.Paths(home)
        paths.data.mkdir(parents=True)
        paths.papers.write_text(json.dumps({'paper_version': 0, 'papers': [{
            'key': 'demo1', 'n': 1, 'label': 'Sample (2026) — Demo study', 'role': 'included study (primary)',
            'folder': str(folder), 'pdf': str(folder / 'demo1.pdf'), 'notes': '',
            'summary': str(folder / 'SUMMARY.md')}]}))
        win = ReviewWindow(paths, root=Path('/'), sheets=sheets,
                           settings=QtCore.QSettings(str(home / 'settings.ini'), QtCore.QSettings.Format.IniFormat))
        win.resize(1500, 900)
        win.show()
        QTest.qWait(250)
        rec0 = json.loads((paths.data / 'sheet-review.json').read_text())['demo1']
        check('every answer is ticked by default', '2/2' in win.list.item(0).text())
        check('… and recorded as "default" with its time', all(rec0[q].get('how') == 'default' and rec0[q].get('verified_on')
                                                              for q in ('P1', 'P3')))
        check('there is no notes editor', not hasattr(win, 'editors'))
        shown = win.summary.toPlainText()
        check('the summary is shown, without its title line', 'A consortium chain run by the edge servers.' in shown
              and 'DEMO · Sample' not in shown)
        check('… read-only', win.summary.isReadOnly())
        check('… with its page cites as links', '[p2]' in shown and '[p3, image]' in shown and '[p1–p2]' in shown
              and 'href="page:3"' in win.summary.toHtml() and 'href="page:1"' in win.summary.toHtml())
        between = shown[shown.index('[p3, image]') + 11:shown.index('Privacy.')]
        check('… each labelled line on its own line', '\n' in between or ' ' in between)
        win._on_summary_link(QtCore.QUrl('page:3'))
        QTest.qWait(150)
        check('clicking a page cite opens that page in the PDF', win.pdf.current_page() == 3)
        win.qbar.setCurrentIndex(1)
        QTest.qWait(150)
        check('the first question with quotations opens on P3', win.q == 'P3')
        win.evidence.setCurrentCell(0, 2)
        win._show_evidence(0)
        QTest.qWait(200)
        check('selecting a quotation opens its page in the PDF', win.pdf.current_page() == 2)
        check('… and outlines the quoted words', bool(win.pdf.marks.get(1)))
        check('the default tick shows, and can be unticked', win.answer_ok.isChecked() and win.answer_ok.isEnabled()
              and 'by default' in win.answer_ok_info.text() and '✓' in win.qbar.tabText(1))
        win.answer_ok.setChecked(False)
        QTest.qWait(50)
        rec = json.loads((paths.data / 'sheet-review.json').read_text())['demo1']['P3']
        check('an untick is recorded with its time', rec.get('verified') is False and rec.get('unticked_on'))
        check('… and the default does not come back', win.review.apply_defaults(
            {'demo1': win.sheet.data['answers']}) == 0 and not win.review.answer_ok('demo1', 'P3', win._answer()))
        check('the answer cannot be ticked again before its quotations are found', not win.answer_ok.isEnabled())
        win.evidence.item(0, 0).setCheckState(Qt.CheckState.Checked)
        QTest.qWait(50)
        check('one quotation ticked: answer still locked', not win.answer_ok.isEnabled())
        win.evidence.item(1, 0).setCheckState(Qt.CheckState.Checked)
        QTest.qWait(50)
        check('all quotations ticked: the answer can be verified', win.answer_ok.isEnabled())
        win.answer_ok.setChecked(True)
        QTest.qWait(50)
        rec = json.loads((paths.data / 'sheet-review.json').read_text())['demo1']['P3']
        check('the answer tick is recorded with its time, as yours', rec.get('verified') and rec.get('verified_on')
              and rec.get('how') == 'by hand')
        check('each quotation tick is recorded with its time', len(rec.get('quotes', {})) == 2
              and all(v.get('verified_on') for v in rec['quotes'].values()))
        check('the tab shows the tick', '✔' in win.qbar.tabText(1))
        check('ticking changed nothing in the sheet', (sheets / 'demo1.json').read_text(encoding='utf-8') == original)
        win.note.setPlainText('Tag should also list the edge tier.')
        QTest.qWait(50)
        check('a note is recorded', json.loads((paths.data / 'sheet-review.json').read_text())['demo1']['P3']['note']
              .startswith('Tag should'))
        win.value_edits['ledger'].setText('public')
        QTest.qWait(nv.AUTOSAVE_MS + 400)
        check('editing a tag saves the sheet', json.loads((sheets / 'demo1.json').read_text())['answers']['P3']['values']
              ['ledger'] == ['public'])
        check('… keeps the original in history', (home / 'history' / 'demo1' / 'SHEET-original.json').exists())
        check('… and clears the answer\'s verified tick (it must be checked again)', not win.answer_ok.isChecked()
              and 'changed after you verified' in win.answer_ok_info.text())
        win.evidence.item(0, 2).setText('The ledger is a consortium chain')
        QTest.qWait(50)
        check('an edited quotation loses its tick', win.evidence.item(0, 0).checkState() == Qt.CheckState.Unchecked)
        check('the other quotation keeps its tick', win.evidence.item(1, 0).checkState() == Qt.CheckState.Checked)
        kept_time = json.loads((paths.data / 'sheet-review.json').read_text())['demo1']['P3']['quotes']
        current = [fingerprint(e['page'], e['quote']) for e in win._answer()['evidence']]

        def ticks():                                       # the record's ticks for the quotations as they now stand
            quotes = json.loads((paths.data / 'sheet-review.json').read_text())['demo1']['P3']['quotes']
            return {fp: quotes[fp] for fp in current if fp in quotes}
        win._tick_all(True)
        QTest.qWait(50)
        rec = ticks()
        check('"Tick all quotations" ticks every quotation of the answer',
              all(win.evidence.item(r, 0).checkState() == Qt.CheckState.Checked for r in range(win.evidence.rowCount())))
        check('… records each new tick with its time and "tick all"', len(rec) == 2 and sum(
            v.get('how') == 'tick all (answer)' and bool(v.get('verified_on')) for v in rec.values()) == 1)
        check('… and leaves an earlier tick as it was', all(rec[fp] == v for fp, v in kept_time.items() if fp in rec))
        check('… so the answer can now be verified', win.answer_ok.isEnabled())
        win._tick_all(False)
        QTest.qWait(50)
        check('"Untick all" clears them', not ticks() and win.evidence.item(0, 0).checkState() == Qt.CheckState.Unchecked)
        win._tick_study(confirm=False)
        QTest.qWait(50)
        rec = ticks()
        check('"Tick all quotations in this study" ticks every quotation, marked "tick all (study)"',
              len(rec) == 2 and all(v.get('how') == 'tick all (study)' for v in rec.values()))
        check('… but not the answers themselves', not win.answer_ok.isChecked())
        if screenshot:
            win.grab().save(screenshot)
            print(f'screenshot: {screenshot}')
        win.close()
        # a highlight made in the PDF becomes a quotation of the open answer, ticked as found on that page
        n_before = len(win.sheet.data['answers'][win.q].get('evidence') or [])
        win.pdf.highlightAdded.emit(1, 'words the author highlighted on page one')
        evs = win.sheet.data['answers'][win.q].get('evidence') or []
        check('a highlight in the PDF is added to the open answer as a quotation on that page',
              len(evs) == n_before + 1 and evs[-1]['page'] == 1 and evs[-1]['quote'] == 'words the author highlighted on page one')
        check('… ticked as found there, recorded "highlighted"',
              win.review.quote_ok('demo1', win.q, 1, 'words the author highlighted on page one')
              and win.review.answer('demo1', win.q)['quotes'][fingerprint(1, 'words the author highlighted on page one')].get('how') == 'highlighted')
        win.pdf.highlightAdded.emit(1, 'words the author highlighted on page one')
        check('… and the same words are not added twice', len(win.sheet.data['answers'][win.q].get('evidence') or []) == n_before + 1)
        win.save_now()
        check('the sheet is valid JSON after editing', json.loads((sheets / 'demo1.json').read_text())['id'] == 'demo1')
        win.settings.sync()
        win.settings = nv._NoSettings()
    finally:
        shutil.rmtree(home, ignore_errors=True)
    print('ALL PASS' if ok else 'SOME CHECKS FAILED')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='Sheet Reviewer')
    ap.add_argument('--self-test', nargs='?', const='', metavar='SCREENSHOT.png')
    args = ap.parse_args()
    nv.faulthandler.enable()
    sys.excepthook = nv.log_exception
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('Sheet Reviewer')
    if args.self_test is not None:
        sys.exit(self_test(args.self_test or None))
    paths = nv.Paths(HERE)
    if not paths.papers.exists():
        QtWidgets.QMessageBox.critical(None, 'Sheet Reviewer', 'The paper list is missing. Start the app with run-review.sh.')
        sys.exit(1)
    win = ReviewWindow(paths)
    log(f'Sheet Reviewer started ({len(win.studies)} studies with evidence sheets)')
    win.show()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: QtCore.QTimer.singleShot(0, app.closeAllWindows))
    heartbeat = QtCore.QTimer(interval=300)
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
