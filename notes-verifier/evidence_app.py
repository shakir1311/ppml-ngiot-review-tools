#!/usr/bin/env python3
"""Evidence Verifier — check each study's evidence sheet against its notes, summary and PDF, and correct it.

Left: the studies cited in the review, with how many sheet answers need attention.
Middle, top: the evidence sheet, one question at a time (P1–P8 or S1–S8): the result of the check against the notes and
summary, the answer, its tags ("values") and its quotations with pages — all editable.
Middle, bottom: the study's notes and summary; the line a quotation comes from is highlighted.
Right: the PDF, opened at the quoted page with the quoted words outlined; the highlighter works as in the Notes Verifier.

Every quotation shows, live, whether it is in the notes or summary and on which page the notes cite it.
Nothing is lost: sheets, notes and summaries save automatically; earlier versions are kept in notes-verifier/history/.

Start it with  notes-verifier/run-evidence.sh  or "Evidence Verifier.command".
Self-test (no real paper is opened):  notes-verifier/run-evidence.sh --self-test [screenshot.png]
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import re
import shutil
import signal
import sys
import tempfile
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

import app as nv                                          # the Notes Verifier: PDF view, notes editor, safe saving
from app import HERE, ROOT, log, write_atomically, now_stamp

sys.path.insert(0, str(ROOT / 'scripts' / 'paper_ppml'))
import sheets_vs_notes as svn                              # the same matching as the systematic check

SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
CHECK = ROOT / 'search-ppml' / 'evidence' / 'sheets-vs-notes'
AUTOSAVE_MS = nv.AUTOSAVE_MS

VERDICTS = {                     # verdict of the reading against the notes: symbol, colour, words
    'agrees': ('✓', '#17663a', 'agrees with the notes/summary'),
    'partly-in-notes': ('◐', '#1d4f8f', 'partly in the notes; the rest is not mentioned there'),
    'not-in-notes': ('○', '#59616c', 'not in the notes or summary — check it in the PDF'),
    'differs': ('⚠', '#a35a00', 'differs from the notes/summary in a detail'),
    'conflicts': ('✖', '#b3261e', 'contradicts the notes/summary'),
}


def attention(verdict):
    return verdict in ('differs', 'conflicts')


# --------------------------------------------------------------------------------------------------- the sheet file


class SheetDoc:
    """One evidence sheet: edited in memory, saved whole and safely, earlier versions kept in history/<id>/."""

    def __init__(self, key: str, path: Path, paths: nv.Paths):
        self.key, self.path, self.paths = key, path, paths
        self.text = path.read_text(encoding='utf-8')
        self.data = json.loads(self.text)
        self.saved_data = copy.deepcopy(self.data)     # what the file holds: only a real edit is ever written
        indent = re.match(r'\{\n( +)"', self.text)
        self.indent = len(indent.group(1)) if indent else 1
        self.backed_up = False

    def save(self) -> bool:
        if self.data == self.saved_data:
            return False                               # nothing edited: the file is left exactly as it is
        new = json.dumps(self.data, indent=self.indent, ensure_ascii=False) + ('\n' if self.text.endswith('\n') else '')
        hist = self.paths.history / self.key
        hist.mkdir(parents=True, exist_ok=True)
        disk = self.path.read_text(encoding='utf-8')
        original = hist / 'SHEET-original.json'
        if not original.exists():
            original.write_text(disk, encoding='utf-8')
        if disk != self.text:
            (hist / f'SHEET-changed-on-disk-{now_stamp()}.json').write_text(disk, encoding='utf-8')
        elif not self.backed_up:
            (hist / f'SHEET-before-{now_stamp()}.json').write_text(disk, encoding='utf-8')
        self.backed_up = True
        write_atomically(self.path, new)
        self.text, self.saved_data = new, copy.deepcopy(self.data)
        return True


def values_to_text(v):
    if isinstance(v, list):
        return ', '.join(str(x) for x in v)
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return '' if v is None else str(v)


def text_to_values(text, like):
    """Turn what was typed back into the type the sheet had (list, true/false, number or text)."""
    text = text.strip()
    if isinstance(like, list):
        return [x.strip() for x in re.split(r',(?![^()]*\))', text) if x.strip()]
    if isinstance(like, bool):
        return text.lower() in ('true', 'yes', 'y', '1')
    if isinstance(like, int) and re.fullmatch(r'-?\d+', text):
        return int(text)
    return text


# --------------------------------------------------------------------------------------------------- main window


class EvidenceWindow(QtWidgets.QMainWindow):
    def __init__(self, paths: nv.Paths, root: Path = ROOT, sheets: Path = SHEETS, check: Path = CHECK,
                 settings: QtCore.QSettings | None = None):
        super().__init__()
        self.paths, self.root, self.sheets_dir, self.check_dir = paths, root, sheets, check
        listing = json.loads(paths.papers.read_text())
        self.studies = [p for p in listing['papers'] if (sheets / f"{p['key']}.json").exists()]
        self.status = nv.Status(paths.data / 'evidence-status.json')
        self.settings = settings or QtCore.QSettings('Abertay', 'EvidenceVerifier')
        self.titles = svn.question_titles() if svn.GUIDE.exists() else {}
        self.current = None
        self.sheet = None
        self.docs = {}
        self.q = None
        self.loading = False
        self.setWindowTitle('Evidence Verifier — evidence sheets against notes, summaries and PDFs')
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
        for name, split in (('split', self.split), ('vsplit', self.vsplit)):
            state = self.settings.value(name)
            if state:
                split.restoreState(state)
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
        sizes = self.split.sizes()
        if min(sizes) < 150:
            self.split.setSizes([int(w * 0.16), int(w * 0.42), int(w * 0.42)])

    # ---- layout
    def _build(self):
        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 4, 8)
        self.search = QtWidgets.QLineEdit(placeholderText='Search studies')
        self.search.textChanged.connect(self._fill_list)
        self.show_filter = QtWidgets.QComboBox()
        self.show_filter.addItems(['All studies', 'Need attention (differs / contradicts)', 'Not finished', 'Finished'])
        self.show_filter.currentIndexChanged.connect(self._fill_list)
        self.progress = QtWidgets.QLabel()
        self.progress.setWordWrap(True)
        self.list = QtWidgets.QListWidget()
        self.list.setWordWrap(True)
        self.list.currentRowChanged.connect(self._on_row)
        for w in (self.search, self.show_filter, self.progress):
            lv.addWidget(w)
        lv.addWidget(self.list, 1)
        legend = QtWidgets.QLabel('  '.join(f'<span style="color:{c}">{s}</span> {k.replace("-", " ")}'
                                            for k, (s, c, _) in VERDICTS.items()))
        legend.setWordWrap(True)
        legend.setStyleSheet('color:#59616c; font-size:11px;')
        lv.addWidget(legend)

        # middle top: the sheet, one question at a time
        sheet_box = QtWidgets.QWidget()
        sv = QtWidgets.QVBoxLayout(sheet_box)
        sv.setContentsMargins(4, 8, 4, 4)
        self.title = QtWidgets.QLabel()
        self.title.setWordWrap(True)
        self.title.setStyleSheet('font-size:15px; font-weight:600;')
        self.subtitle = QtWidgets.QLabel()
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet('color:#59616c;')
        nav = QtWidgets.QHBoxLayout()
        prev_btn = QtWidgets.QPushButton('◀ Previous study')
        next_btn = QtWidgets.QPushButton('Next study ▶')
        prev_btn.clicked.connect(lambda: self._step(-1))
        next_btn.clicked.connect(lambda: self._step(1))
        nav.addWidget(prev_btn)
        nav.addWidget(next_btn)
        nav.addStretch(1)
        self.qbar = QtWidgets.QTabBar()
        self.qbar.setExpanding(False)
        self.qbar.currentChanged.connect(self._on_question)
        detail = QtWidgets.QWidget()
        dv = QtWidgets.QVBoxLayout(detail)
        dv.setContentsMargins(0, 4, 0, 0)
        self.qtitle = QtWidgets.QLabel()
        self.qtitle.setWordWrap(True)
        self.qtitle.setStyleSheet('font-weight:600;')
        self.verdict_box = QtWidgets.QLabel()
        self.verdict_box.setWordWrap(True)
        self.verdict_box.setTextFormat(Qt.TextFormat.RichText)
        self.verdict_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.answer = QtWidgets.QPlainTextEdit()
        self.answer.setMinimumHeight(90)
        self.answer.textChanged.connect(self._on_answer_edit)
        self.values_form = QtWidgets.QFormLayout()
        self.values_holder = QtWidgets.QWidget()
        self.values_holder.setLayout(self.values_form)
        self.evidence = QtWidgets.QTableWidget(0, 3)
        self.evidence.setHorizontalHeaderLabels(['Page', 'Quotation (click a row to see it in the PDF and the notes)',
                                                 'In the notes / summary?'])
        hh = self.evidence.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.evidence.verticalHeader().setVisible(False)
        self.evidence.setWordWrap(True)
        self.evidence.setMinimumHeight(140)
        self.evidence.itemChanged.connect(self._on_evidence_edit)
        self.evidence.currentCellChanged.connect(lambda r, *_: self._show_evidence(r))
        ev_buttons = QtWidgets.QHBoxLayout()
        add_ev = QtWidgets.QPushButton('+ Add quotation')
        del_ev = QtWidgets.QPushButton('Remove selected quotation')
        add_ev.clicked.connect(self._add_evidence)
        del_ev.clicked.connect(self._remove_evidence)
        self.answer_checked = QtWidgets.QCheckBox('This answer is checked')
        self.answer_checked.toggled.connect(self._set_answer_checked)
        self.saved_label = QtWidgets.QLabel()
        ev_buttons.addWidget(add_ev)
        ev_buttons.addWidget(del_ev)
        ev_buttons.addStretch(1)
        ev_buttons.addWidget(self.answer_checked)
        ev_buttons.addWidget(self.saved_label)
        dv.addWidget(self.qtitle)
        dv.addWidget(self.verdict_box)
        dv.addWidget(QtWidgets.QLabel('<b>Answer</b>'))
        dv.addWidget(self.answer, 2)
        dv.addWidget(QtWidgets.QLabel('<b>Tags</b> (comma-separated; they feed the paper\'s tables)'))
        dv.addWidget(self.values_holder)
        dv.addWidget(QtWidgets.QLabel('<b>Quotations</b> (double-click to correct a page or a quotation)'))
        dv.addWidget(self.evidence, 3)
        dv.addLayout(ev_buttons)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(detail)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        sv.addWidget(self.title)
        sv.addWidget(self.subtitle)
        sv.addLayout(nav)
        sv.addWidget(self.qbar)
        sv.addWidget(scroll, 1)

        # middle bottom: notes and summary
        notes_box = QtWidgets.QWidget()
        nvb = QtWidgets.QVBoxLayout(notes_box)
        nvb.setContentsMargins(4, 4, 4, 8)
        self.tabs = QtWidgets.QTabWidget()
        self.editors = {}
        for name, label in (('notes', 'Notes'), ('summary', 'Summary')):
            ed = nv.NotesEditor()
            ed.textChanged.connect(self._on_notes_edit)
            ed.pageRequested.connect(self._go)
            self.editors[name] = ed
            self.tabs.addTab(ed, label)
        nvb.addWidget(self.tabs, 1)

        self.vsplit = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.vsplit.addWidget(sheet_box)
        self.vsplit.addWidget(notes_box)
        self.vsplit.setChildrenCollapsible(False)
        self.vsplit.setSizes([620, 330])

        # right: PDF
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
        self.pdf.message.connect(lambda m: self.statusBar().showMessage(m, 8000))
        zoom_out.clicked.connect(lambda: self.pdf.set_zoom(1 / 1.2))
        zoom_in.clicked.connect(lambda: self.pdf.set_zoom(1.2))
        fit.clicked.connect(self.pdf.fit)
        rv.addLayout(bar)
        rv.addWidget(self.pdf, 1)

        left.setMinimumWidth(180)
        self.vsplit.setMinimumWidth(380)
        right.setMinimumWidth(320)
        self.split = QtWidgets.QSplitter()
        for w in (left, self.vsplit, right):
            self.split.addWidget(w)
        self.split.setChildrenCollapsible(False)
        self.split.setSizes([240, 700, 640])
        self.setCentralWidget(self.split)

        QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Save, self, activated=self.save_now)
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Down'), self, activated=lambda: self._step(1))
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Up'), self, activated=lambda: self._step(-1))
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Right'), self, activated=lambda: self._step_q(1))
        QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Left'), self, activated=lambda: self._step_q(-1))
        self.statusBar().showMessage('Ready. Your changes are saved automatically.', 6000)

    # ---- check results
    def _verdicts(self, key):
        f = self.check_dir / 'verdicts' / f'{key}.json'
        try:
            return json.loads(f.read_text(encoding='utf-8')).get('answers', {}) if f.exists() else {}
        except json.JSONDecodeError:
            return {}

    def _counts(self, key):
        v = self._verdicts(key)
        return sum(1 for a in v.values() if a.get('verdict') == 'conflicts'), \
            sum(1 for a in v.values() if a.get('verdict') == 'differs'), len(v)

    def _finished(self, s):
        st = self.status.get(s['key'])
        sheet = json.loads((self.sheets_dir / f"{s['key']}.json").read_text(encoding='utf-8'))
        return all(st.get(q) for q in sheet['answers'])

    # ---- the list
    def _item_text(self, s):
        conflicts, differs, checked = self._counts(s['key'])
        flags = (f'✖{conflicts} ' if conflicts else '') + (f'⚠{differs} ' if differs else '')
        mark = '✅' if self._finished(s) else ('·' if not checked else '○')
        return f"{mark} {flags}[{s['n']}] {s['label']}"

    def _fill_list(self):
        want, mode = self.search.text().strip().lower(), self.show_filter.currentIndex()
        keep = self.current['key'] if self.current else None
        self.list.blockSignals(True)
        self.list.clear()
        self.rows = []
        for k, s in enumerate(self.studies):
            text = f"[{s['n']}] {s['label']} {s['key']}".lower()
            if want and want not in text:
                continue
            conflicts, differs, _ = self._counts(s['key'])
            done = self._finished(s)
            if (mode == 1 and not (conflicts or differs)) or (mode == 2 and done) or (mode == 3 and not done):
                continue
            item = QtWidgets.QListWidgetItem(self._item_text(s))
            item.setToolTip(s['key'])
            if done:
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
        done = sum(1 for s in self.studies if self._finished(s))
        attention_n = sum(1 for s in self.studies if any(self._counts(s['key'])[:2]))
        self.progress.setText(f'<b>{done} of {len(self.studies)}</b> sheets finished · {attention_n} with answers to look at')

    def _refresh_item(self):
        row = next((r for r, k in enumerate(self.rows) if self.studies[k]['key'] == self.current['key']), None)
        if row is not None:
            self.list.item(row).setText(self._item_text(self.current))
            self.list.item(row).setForeground(QtGui.QColor('#17663a' if self._finished(self.current) else '#1b1f24'))
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

    # ---- opening a study
    def open_study(self, s):
        self.save_now()
        self.current = s
        log(f"Study [{s['n']}] {s['key']} opened (evidence sheet)")
        self.settings.setValue('last_study', s['key'])
        key = s['key']
        self.sheet = SheetDoc(key, self.sheets_dir / f'{key}.json', self.paths)
        self.docs = {'notes': nv.TextDoc(key, 'notes', self.root / s['notes'], self.paths),
                     'summary': nv.TextDoc(key, 'summary', self.root / s['summary'], self.paths)}
        for name, ed in self.editors.items():
            ed.blockSignals(True)
            ed.setPlainText(self.docs[name].saved_text)
            ed.blockSignals(False)
        self.title.setText(f"[{s['n']}] {s['label']}")
        kind = 'survey' if next(iter(self.sheet.data['answers']), 'P').startswith('S') else 'primary study'
        self.subtitle.setText(f"{key} · {kind} · {Path(s['pdf']).name}")
        self.subtitle.setToolTip(str(self.root / s['pdf']))
        pdf = self.root / s['pdf']
        if pdf.exists():
            self.pdf.open(key, pdf)
        self.verdicts = self._verdicts(key)
        self.qbar.blockSignals(True)
        while self.qbar.count():
            self.qbar.removeTab(0)
        for q in self.sheet.data['answers']:
            self.qbar.addTab(self._tab_label(q))
        self.qbar.blockSignals(False)
        first = next((i for i, q in enumerate(self.sheet.data['answers'])
                      if attention(self.verdicts.get(q, {}).get('verdict'))), 0)
        self.qbar.setCurrentIndex(first)
        self._on_question(first)
        self._set_saved('All changes saved')

    def _tab_label(self, q):
        v = self.verdicts.get(q, {}).get('verdict') if hasattr(self, 'verdicts') else None
        sym = VERDICTS.get(v, ('', '', ''))[0]
        tick = ' ✔' if self.status.get(self.current['key']).get(q) else ''
        return f'{q} {sym}{tick}'.strip()

    def _on_question(self, index):
        if self.sheet is None or index < 0:
            return
        self.save_now()
        qs = list(self.sheet.data['answers'])
        self.q = qs[index]
        ans = self.sheet.data['answers'][self.q]
        self.loading = True
        self.qtitle.setText(f"{self.q} — {self.titles.get(self.q, '')}   ·   taken from: {ans.get('located_via', '?')}")
        self._show_verdict()
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
        self.answer_checked.blockSignals(True)
        self.answer_checked.setChecked(bool(self.status.get(self.current['key']).get(self.q)))
        self.answer_checked.blockSignals(False)
        self.loading = False
        if self.evidence.rowCount():
            self.evidence.setCurrentCell(0, 1)
            self._show_evidence(0)

    def _show_verdict(self):
        v = self.verdicts.get(self.q)
        if not v:
            self.verdict_box.setText('<span style="color:#59616c">No reading against the notes recorded for this answer yet.</span>')
            return
        sym, colour, words = VERDICTS.get(v.get('verdict'), ('?', '#59616c', v.get('verdict', '')))
        html = [f'<div style="border-left:4px solid {colour}; padding-left:6px"><b style="color:{colour}">{sym} {words}</b>'
                f' — {_esc(v.get("comment", ""))}']
        for p in v.get('points', []):
            st = p.get('status', '')
            if st == 'agrees':
                continue
            c = VERDICTS.get({'not-in-notes': 'not-in-notes', 'differs': 'differs', 'conflicts': 'conflicts'}.get(st, ''),
                             ('', '#59616c', ''))[1]
            html.append(f'<br><span style="color:{c}">• <b>{st}</b></span>: sheet “{_esc(p.get("sheet", ""))}”'
                        + (f' · {p.get("where") or "notes"}: “{_esc(p.get("notes", ""))}”' if p.get('notes') else '')
                        + (f'<br>&nbsp;&nbsp;<i>suggested: {_esc(p.get("fix", ""))}</i>' if p.get('fix') else ''))
        html.append('</div>')
        self.verdict_box.setText(''.join(html))

    # ---- quotations
    def _fill_evidence(self):
        ans = self.sheet.data['answers'][self.q]
        self.evidence.blockSignals(True)
        self.evidence.setRowCount(0)
        for ev in ans.get('evidence') or []:
            r = self.evidence.rowCount()
            self.evidence.insertRow(r)
            self.evidence.setItem(r, 0, QtWidgets.QTableWidgetItem(str(ev.get('page', ''))))
            self.evidence.setItem(r, 1, QtWidgets.QTableWidgetItem(ev.get('quote', '')))
            status = QtWidgets.QTableWidgetItem()
            status.setFlags(status.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.evidence.setItem(r, 2, status)
            self._update_status_cell(r)
        self.evidence.resizeRowsToContents()
        self.evidence.blockSignals(False)

    def _link_status(self, page, quote):
        notes, summary = self.editors['notes'].toPlainText(), self.editors['summary'].toPlainText()
        in_n, in_s = svn.find(quote, notes), svn.find(quote, summary)
        if not (in_n or in_s):
            return '○ not in notes or summary', '#59616c'
        where = 'notes' if in_n else 'summary'
        pages = svn.pages_on_lines(quote, notes) if in_n else []
        if pages and page not in pages:
            return f'⚠ in the {where}, but the notes cite p{", p".join(map(str, pages))}', '#a35a00'
        return f'✓ in the {where}' + (f' (p{page})' if pages else ''), '#17663a'

    def _update_status_cell(self, r):
        page_item, quote_item = self.evidence.item(r, 0), self.evidence.item(r, 1)
        try:
            page = int(page_item.text())
        except (ValueError, AttributeError):
            page = None
        text, colour = self._link_status(page, quote_item.text() if quote_item else '')
        cell = self.evidence.item(r, 2)
        cell.setText(text)
        cell.setForeground(QtGui.QColor(colour))

    def _show_evidence(self, r):
        if r < 0 or self.evidence.item(r, 1) is None:
            return
        quote = self.evidence.item(r, 1).text()
        try:
            page = int(self.evidence.item(r, 0).text())
        except ValueError:
            page = None
        if page:
            self.pdf.go_to_page(page, quote)
        self._mark_in_notes(quote)

    def _mark_in_notes(self, quote):
        """Highlight the notes or summary line the quotation comes from."""
        for ed in self.editors.values():
            ed.setExtraSelections([])
        q = svn.norm(quote).strip(' ".\'')
        words = q.split()
        head, need = ' '.join(words[:8]), min(8, len(words))
        for i, name in enumerate(('notes', 'summary')):
            ed = self.editors[name]
            block = ed.document().firstBlock()
            while block.isValid():
                ln = svn.norm(block.text())
                if head and (head in ln or (need >= 5 and svn.longest_shared_run(words, ln.split()) >= need)):
                    sel = QtWidgets.QTextEdit.ExtraSelection()
                    sel.format.setBackground(QtGui.QColor('#fff3a8'))
                    sel.format.setProperty(QtGui.QTextFormat.Property.FullWidthSelection, True)
                    sel.cursor = QtGui.QTextCursor(block)
                    ed.setExtraSelections([sel])
                    self.tabs.setCurrentIndex(i)
                    cur = QtGui.QTextCursor(block)
                    ed.setTextCursor(cur)
                    ed.centerCursor()
                    return True
                block = block.next()
        return False

    # ---- editing the sheet
    def _answer(self):
        return self.sheet.data['answers'][self.q]

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

    def _on_evidence_edit(self, item):
        if self.loading or item.column() == 2:
            return
        r = item.row()
        evs = self._answer().setdefault('evidence', [])
        while len(evs) <= r:
            evs.append({'page': None, 'quote': ''})
        page_text = self.evidence.item(r, 0).text().strip() if self.evidence.item(r, 0) else ''
        if not page_text.isdigit():                       # a page must stay a number: put the old one back
            self.evidence.blockSignals(True)
            self.evidence.item(r, 0).setText(str(evs[r].get('page') or ''))
            self.evidence.blockSignals(False)
            self.statusBar().showMessage('A page must be a number (the PDF page).', 6000)
            return
        evs[r]['page'] = int(page_text)
        evs[r]['quote'] = self.evidence.item(r, 1).text() if self.evidence.item(r, 1) else ''
        self.evidence.blockSignals(True)
        self._update_status_cell(r)
        self.evidence.blockSignals(False)
        self._changed()

    def _add_evidence(self):
        if self.sheet is None:
            return
        self._answer().setdefault('evidence', []).append({'page': self.pdf.current_page(), 'quote': ''})
        self._fill_evidence()
        r = self.evidence.rowCount() - 1
        self.evidence.setCurrentCell(r, 1)
        self.evidence.editItem(self.evidence.item(r, 1))
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

    def _changed(self):
        self._set_saved('Editing…')
        self.autosave.start()

    def _on_notes_edit(self):
        self._set_saved('Editing…')
        self.autosave.start()
        if self.evidence.rowCount():
            self.evidence.blockSignals(True)
            for r in range(self.evidence.rowCount()):
                self._update_status_cell(r)
            self.evidence.blockSignals(False)

    def save_now(self):
        if self.current is None or self.sheet is None:
            return
        self.autosave.stop()
        try:
            if self.sheet.save():
                log(f"  evidence sheet saved ({self.current['key']}, {self.q})")
                self.status.set(self.current['key'], 'sheet_edited', True)
            for name, ed in self.editors.items():
                if self.docs[name].save(ed.toPlainText()):
                    log(f"  {name} saved ({self.current['key']})")
                    self.status.set(self.current['key'], 'edited', True)
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

    def _set_answer_checked(self, value):
        if self.current is None or self.q is None:
            return
        self.save_now()
        self.status.set(self.current['key'], self.q, bool(value))
        log(f"  {self.current['key']} {self.q} checked: {'yes' if value else 'no'}")
        self.qbar.setTabText(self.qbar.currentIndex(), self._tab_label(self.q))
        self._refresh_item()

    # ---- PDF
    def _go(self, page, quote):
        self.pdf.go_to_page(page, quote)

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
        self.settings.setValue('vsplit', self.vsplit.saveState())
        self.pdf.close_doc()
        super().closeEvent(e)


def _esc(text):
    return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# --------------------------------------------------------------------------------------------------- self-test


def self_test(screenshot: str | None) -> int:
    """Runs the app on generated sample files (never a real paper) and checks what it promises."""
    import pymupdf
    from PySide6.QtTest import QTest
    home = Path(tempfile.mkdtemp(prefix='.selftest-ev-', dir=str(HERE)))
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(('PASS ' if cond else 'FAIL ') + label)

    try:
        folder = home / 'papers' / 'demo1'
        (folder / 'notes').mkdir(parents=True)
        pdf = pymupdf.open()
        for pg in range(1, 4):
            page = pdf.new_page()
            page.insert_text((72, 100), f'Sample paper, page {pg}.', fontsize=14)
            page.insert_text((72, 140), 'The ledger is a consortium chain run by the edge servers of the operators.', fontsize=11)
        pdf.save(folder / 'demo1.pdf')
        (folder / 'notes' / 'NOTES.md').write_text(
            '# Notes\n- The ledger is permissioned. [p2] "The ledger is a consortium chain run by the edge servers"\n',
            encoding='utf-8')
        (folder / 'notes' / 'SUMMARY.md').write_text('The study uses a consortium blockchain [p2].\n', encoding='utf-8')
        sheets = home / 'sheets'
        sheets.mkdir()
        (sheets / 'demo1.json').write_text(json.dumps({'id': 'demo1', 'kind': 'primary', 'answers': {
            'P1': {'answer': 'IoV setting.', 'values': {'settings': ['IoV-vehicular']}, 'evidence': [], 'located_via': 'summary'},
            'P3': {'answer': 'A public chain.', 'values': {'ledger': ['public'], 'onchain_ok': True},
                   'evidence': [{'page': 2, 'quote': 'The ledger is a consortium chain run by the edge servers'},
                                {'page': 3, 'quote': 'words that the notes do not contain at all'}], 'located_via': 'notes'}}},
            indent=1), encoding='utf-8')
        # a second sheet laid out differently (two-space indent, escaped non-ASCII): opening it must not rewrite it
        other = json.dumps({'id': 'demo2', 'kind': 'primary', 'answers': {
            'P1': {'answer': 'Smart grid — edge.', 'values': {'settings': ['smart-grid']},
                   'evidence': [{'page': 1, 'quote': 'Sample paper, page 1.'}], 'located_via': 'full text'}}},
            indent=2, ensure_ascii=True)
        (sheets / 'demo2.json').write_text(other, encoding='utf-8')
        check_dir = home / 'check'
        (check_dir / 'verdicts').mkdir(parents=True)
        (check_dir / 'verdicts' / 'demo1.json').write_text(json.dumps({'key': 'demo1', 'answers': {
            'P1': {'verdict': 'agrees', 'comment': 'Setting as in the summary.', 'points': []},
            'P3': {'verdict': 'conflicts', 'comment': 'The notes say consortium, the sheet public.', 'points': [
                {'sheet': 'A public chain', 'notes': 'consortium chain', 'where': 'notes', 'status': 'conflicts',
                 'fix': 'A consortium (permissioned) chain'}]}}}), encoding='utf-8')
        paths = nv.Paths(home)
        paths.data.mkdir(parents=True)
        paths.papers.write_text(json.dumps({'paper_version': 0, 'papers': [{
            'key': 'demo1', 'n': 1, 'label': 'Sample (2026) — Demo study', 'role': 'included study (primary)',
            'folder': str(folder), 'pdf': str(folder / 'demo1.pdf'), 'notes': str(folder / 'notes' / 'NOTES.md'),
            'summary': str(folder / 'notes' / 'SUMMARY.md')}, {
            'key': 'demo2', 'n': 2, 'label': 'Sample (2026) — Second study', 'role': 'included study (primary)',
            'folder': str(folder), 'pdf': str(folder / 'demo1.pdf'), 'notes': str(folder / 'notes' / 'NOTES.md'),
            'summary': str(folder / 'notes' / 'SUMMARY.md')}]}))
        win = EvidenceWindow(paths, root=Path('/'), sheets=sheets, check=check_dir,
                             settings=QtCore.QSettings(str(home / 'settings.ini'), QtCore.QSettings.Format.IniFormat))
        win.resize(1500, 900)
        win.show()
        QTest.qWait(250)
        check('the study list shows the study with its contradiction', '✖1' in win.list.item(0).text())
        check('the question that needs attention opens first', win.q == 'P3')
        check('the reading against the notes is shown', 'contradicts' in win.verdict_box.text()
              and 'consortium' in win.verdict_box.text())
        check('a quotation found in the notes is marked as such', win.evidence.item(0, 2).text().startswith('✓'))
        check('a quotation not in the notes is marked as such', win.evidence.item(1, 2).text().startswith('○'))
        win.evidence.setCurrentCell(0, 1)
        win._show_evidence(0)
        QTest.qWait(200)
        check('selecting a quotation opens its page in the PDF', win.pdf.current_page() == 2)
        check('… outlines the quoted words', bool(win.pdf.marks.get(1)))
        check('… and highlights the notes line it comes from',
              bool(win.editors['notes'].extraSelections()) and win.tabs.currentIndex() == 0)

        # correcting the sheet
        win.answer.setPlainText('A consortium (permissioned) chain.')
        win.value_edits['ledger'].setText('consortium-permissioned')
        win.value_edits['onchain_ok'].setText('no')
        QTest.qWait(nv.AUTOSAVE_MS + 400)
        saved = json.loads((sheets / 'demo1.json').read_text(encoding='utf-8'))
        check('a corrected answer is saved to the sheet', saved['answers']['P3']['answer'] == 'A consortium (permissioned) chain.')
        check('tags keep their type (list, true/false)', saved['answers']['P3']['values'] ==
              {'ledger': ['consortium-permissioned'], 'onchain_ok': False})
        check('the original sheet is kept in history', (home / 'history' / 'demo1' / 'SHEET-original.json').exists())
        win.evidence.item(1, 1).setText('The ledger is a consortium chain run by the edge servers of the operators')
        win.evidence.item(1, 0).setText('2')
        QTest.qWait(nv.AUTOSAVE_MS + 400)
        saved = json.loads((sheets / 'demo1.json').read_text(encoding='utf-8'))
        check('a corrected quotation and page are saved', saved['answers']['P3']['evidence'][1] ==
              {'page': 2, 'quote': 'The ledger is a consortium chain run by the edge servers of the operators'})
        check('its link to the notes is re-checked at once', win.evidence.item(1, 2).text().startswith('✓'))
        win.answer_checked.setChecked(True)
        check('ticking an answer is saved', json.loads((home / 'data' / 'evidence-status.json').read_text())['demo1']['P3'])
        check('the tick shows on the question tab', '✔' in win.qbar.tabText(win.qbar.currentIndex()))
        if screenshot:
            win.grab().save(screenshot)
            print(f'screenshot: {screenshot}')
        win.qbar.setCurrentIndex(0)
        win.answer_checked.setChecked(True)
        check('a sheet with every answer ticked counts as finished', '1 of 2' in win.progress.text())
        for row in (1, 0, 1):                          # open the second study, look through it, leave it, come back
            win.list.setCurrentRow(row)
            QTest.qWait(150)
            for i in range(win.qbar.count()):
                win.qbar.setCurrentIndex(i)
                QTest.qWait(50)
        win.list.setCurrentRow(0)
        QTest.qWait(nv.AUTOSAVE_MS + 400)
        check('a sheet that is only looked at stays byte for byte as it was',
              (sheets / 'demo2.json').read_text(encoding='utf-8') == other and not (home / 'history' / 'demo2').exists())
        check('… and gets no entry in the progress file',
              'demo2' not in json.loads((home / 'data' / 'evidence-status.json').read_text()))
        win.close()
        check('the sheet is still valid JSON after editing', json.loads((sheets / 'demo1.json').read_text())['id'] == 'demo1')
        win.settings.sync()
        win.settings = nv._NoSettings()
        import gc
        gc.collect()
    finally:
        shutil.rmtree(home, ignore_errors=True)
    print('ALL PASS' if ok else 'SOME CHECKS FAILED')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description='Evidence Verifier')
    ap.add_argument('--self-test', nargs='?', const='', metavar='SCREENSHOT.png')
    args = ap.parse_args()
    nv.faulthandler.enable()
    sys.excepthook = nv.log_exception
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName('Evidence Verifier')
    if args.self_test is not None:
        sys.exit(self_test(args.self_test or None))
    paths = nv.Paths(HERE)
    if not paths.papers.exists():
        QtWidgets.QMessageBox.critical(None, 'Evidence Verifier', 'The paper list is missing. Start the app with run-evidence.sh.')
        sys.exit(1)
    win = EvidenceWindow(paths)
    log(f'Evidence Verifier started ({len(win.studies)} studies with evidence sheets)')
    win.show()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: QtCore.QTimer.singleShot(0, app.closeAllWindows))
    heartbeat = QtCore.QTimer(interval=300)
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
