#!/usr/bin/env python3
"""Review Viewer — a desktop app (Qt) for reading the review next to its sources. No web browser is involved.

Left: the review, in a native text view with a clickable contents list. Right: a PDF viewer. Clicking a reference [n]
opens that paper's PDF from the corpus (the published version where one replaces the preprint, else the included
studies' folder corpus/ppmlcorpus/included/, else the older manifests), scrolled to the cited passage where it is
known: the page of the evidence behind the sentence, or behind the table column, with the quoted words outlined in
red, the paper's section named where its outline or extraction gives one, and the record's other page-cited answers
offered as links (P1 p.3 · P2 p.5 …). How each page was settled is in scripts/review/build_pdflinks_html.resolve().
Pages are rendered by Poppler (pdftoppm) and cached per PDF (path, size and date: a replaced PDF is rendered afresh).
Optionally, references open in Preview instead ("Open in Preview"), which jumps to the page when macOS allows the app
to use Accessibility.

The paper's Word comments are the author's checks. Each highlighted passage keeps its colour (yellow VERIFY, turquoise
YOUR WORDS, green SPOT-CHECK), a flag such as ⚑V18 marks where it starts and opens the comment when clicked, and an
"Author checks" list after the contents jumps to every one.

The citation -> page links come from the audited logic in scripts/review/build_pdflinks_html.py.
Both series are listed in the Version menu: the earlier survey (V14…V28) and the systematic review of 2 October 2026
("SLR V1" …, each also "+ checks", the copy with the author checks). The default is the newest PPML version
with its checks. For that series a reference opens at the page of the evidence behind its sentence (build/LINKS-V<n>.json,
written by scripts/paper/links.py from the page-cited sheets); otherwise at the page of a distinctive fact, or page 1.
Usage: python3 review_viewer.py ["<review>.docx"]   (defaults to the newest saved version; the Version menu opens any other)
"""
import base64, hashlib, html, json, math, os, pathlib, re, shutil, subprocess, sys, threading, traceback, unicodedata

from PySide6.QtCore import Qt, QObject, QRunnable, QSettings, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut, \
    QTextCursor, QTextDocument, QTextOption
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, \
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter, QTextBrowser, QTextEdit, QToolButton, \
    QVBoxLayout, QWidget

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = pathlib.Path(__file__).resolve().parent
CACHE = APP / '.cache'
CACHE.mkdir(exist_ok=True)
os.environ['PATH'] = os.pathsep.join([os.environ.get('PATH', ''), '/opt/homebrew/bin', '/usr/local/bin'])
sys.path.insert(0, str(ROOT / 'scripts' / 'review'))
import build_pdflinks_html as BP          # noqa: E402
import paper_look                         # noqa: E402  the look shared with the Word documents

DOCDIR = ROOT / 'myliteraturereviewpaper'
# the two series of the review: the earlier survey (labels V14…V28) and the systematic review of 2 October 2026
# (labels "SLR V1", "SLR V3 + checks"); each version also has a copy "with author checks"
# the PPML series sorts last, so its newest version (with author checks) is the one opened by default (the author, 5 Oct 2026)
SERIES = [(re.compile(r'^Privacy Preserving Machine Learning in NextGeneration IoT - V(\d+)( with author checks)?\.docx$'), 1, 'V'),
          (re.compile(r'^Verifiable Privacy-Preserving FL on Blockchains - Systematic Review - V(\d+)( with author checks)?\.docx$'), 0, 'SLR V')]


def versions():
    """every saved version of the paper, oldest first, the newest series last: [(label, path)] (Word's ~$ lock files
    are skipped); the newest is the author-check copy of the newest version of the systematic review"""
    out = []
    # each series has its own folder since 4 October 2026 (scripts/organise_papers.py); files not yet moved still count
    files = [q for d in (DOCDIR, DOCDIR / 'PPML in NextGeneration IoT', DOCDIR / 'Verifiable PPFL on Blockchains - Systematic Review')
             if d.exists() for q in d.glob('*.docx')]
    for q in files:
        for rx, s, lab in SERIES:
            if (m := rx.match(q.name)):
                out.append(((s, int(m.group(1)), bool(m.group(2))), f'{lab}{m.group(1)}' + (' + checks' if m.group(2) else ''), q))
    return [(label, q) for _, label, q in sorted(out)]


DOCX = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else versions()[-1][1]       # the version on screen
REFS = json.loads((ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'references.json')
                  .read_text(encoding='utf-8'))['refs']
for _k, _v in BP.NEW_REFS.items():               # the systematic review's own bibliography (keys n####, foundations)
    REFS.setdefault(_k, {'cite': f"{_v.get('first_author_surname') or _k} {_v.get('year', '')}".strip(),
                         'title': BP._title_in(_v['ieee']) or _v['ieee']})
for _k, _v in BP.PPML_REFS.items():              # the PPML review's bibliography (V29 onwards; keys are corpus ids)
    REFS.setdefault(_k, {'cite': f"{_v.get('first_author_surname') or _k} {_v.get('year', '')}".strip(),
                         'title': BP._title_in(_v['ieee']) or _v['ieee']})
NUM = {}                                    # key -> its number [n] in the version on screen (set when a version loads)
PDFS = {k: p for k in REFS if (p := BP.pdf_for(k))}                 # key -> corpus PDF, the same in every version
PDFINFO = shutil.which('pdfinfo') or '/opt/homebrew/bin/pdfinfo'
PDFTOPPM = shutil.which('pdftoppm') or '/opt/homebrew/bin/pdftoppm'


# ================================================================= the review, prepared for Qt's text view

TARGETS = []                                # per link: [question, quotation, how] (index in the link; saved with the version)


def _make_link(token, key, page, in_refs, pdf, q='', quote='', how=''):
    if in_refs or not (q or quote or how):
        return f'<a href="ref:{key}:{page}">{token}</a>'
    TARGETS.append([q, quote, how])
    return f'<a href="ref:{key}:{page}:{len(TARGETS) - 1}">{token}</a>'


def _contents(doc):
    items, cur = [], None
    for m in re.finditer(r'<h([12])\s+id="([^"]+)"[^>]*>(.*?)</h\1>', doc, re.S):
        lvl, hid, text = int(m.group(1)), m.group(2), re.sub(r'<[^>]+>', '', m.group(3)).strip()
        if lvl == 1:
            cur = [hid, text, []]
            items.append(cur)
        elif cur is not None:
            cur[2].append((hid, text))
    rows = []
    for hid, text, subs in items:
        rows.append(f'<p class="toc1"><a href="#{hid}">{text}</a></p>')
        rows += [f'<p class="toc2"><a href="#{s}">{t}</a></p>' for s, t in subs]
    return '<p class="toch">Contents</p>' + ''.join(rows) + '<hr/>'


# kind -> (flag letter, highlight colour, flag colour, flag text colour)
KINDS = {'VERIFY': ('V', '#fff59d', '#fbc02d', '#000000'), 'YOUR WORDS': ('W', '#b2ebf2', '#00838f', '#ffffff'),
         'SPOT-CHECK': ('S', '#c5e1a5', '#558b2f', '#ffffff'), 'KEY': ('K', '#fff59d', '#fbc02d', '#000000')}
CHECKS = {}                                                         # comment id -> [kind, comment, highlighted text]
FLAG = re.compile(r'⚑[KVWS]\d+')


def _take_comments(doc):
    """lift the Word comments out of pandoc's HTML, so they are not read as part of the paper, and leave an empty
    anchor at the start and the end of each commented passage. Returns (html, {id: (kind, comment)})."""
    found = {}

    def start(m):
        text = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', m.group(2)))).strip()
        kind = 'KEY' if text.startswith('KEY') else \
            next((k for k in ('VERIFY', 'YOUR WORDS', 'SPOT-CHECK') if text.startswith(k + ':')), 'VERIFY')
        found[m.group(1)] = (kind, text if kind == 'KEY' else text.split(':', 1)[-1].strip())
        return f'<a name="chk-{m.group(1)}"></a>'
    doc = re.sub(r'<span\s+class="comment-start"\s+id="(\d+)"[^>]*>(.*?)</span>', start, doc, flags=re.S)
    doc = re.sub(r'<span\s+class="comment-end"\s+id="(\d+)"[^>]*>\s*</span>', r'<a name="chkend-\1"></a>', doc)
    return doc, found


def _flag(cid, kind, href):
    letter, _, back, ink = KINDS[kind]
    return (f'<a href="{href}"><span style="background-color:{back}; color:{ink}; font-family:\'Helvetica Neue\'; '
            f'font-size:11px; font-weight:700;">&nbsp;⚑{letter}{int(cid) + 1}&nbsp;</span></a>')


def _excerpts(body, found):
    out = {}
    for cid in found:
        m = re.search(rf'<a name="chk-{cid}"></a>(.*?)<a name="chkend-{cid}"></a>', body, re.S)
        out[cid] = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1) if m else ''))).strip()
    return out


def _checks_list(found, excerpts):
    """the list of author checks shown after the contents: the flag opens the comment, the text jumps to the place"""
    if not found:
        return ''
    n = {k: sum(1 for kind, _ in found.values() if kind == k) for k in KINDS}
    key = ' '.join(f'<span style="background-color:{KINDS[k][1]};">&nbsp;{label} ({count})&nbsp;</span>'
                   for k, label, count in (('VERIFY', 'Yellow: VERIFY', n['VERIFY'] + n['KEY']),
                                           ('YOUR WORDS', 'Turquoise: YOUR WORDS', n['YOUR WORDS']),
                                           ('SPOT-CHECK', 'Green: SPOT-CHECK', n['SPOT-CHECK'])))
    rows = []
    for cid in sorted(found, key=int):
        ex = excerpts.get(cid, '')
        ex = ex if len(ex) <= 110 else ex[:110].rsplit(' ', 1)[0] + '…'
        rows.append(f'<p class="chk">{_flag(cid, found[cid][0], f"check:{cid}")} <a href="#chk-{cid}">{html.escape(ex)}</a></p>')
    return (f'<p class="toch"><a name="author-checks"></a>Author checks ({len(found)})</p><p class="chkkey">{key}</p>'
            '<p class="chkhelp">Click a flag to read the check; click its text to go to the place in the paper.</p>'
            + ''.join(rows) + '<hr/>')


def _paint(body, found):
    """give each highlight the colour of the comment around it, and put a clickable flag where each comment starts"""
    open_ids = []

    def tok(m):
        if m.group(1):
            open_ids.append(m.group(1))
            return f'<a name="chk-{m.group(1)}"></a>' + _flag(m.group(1), found[m.group(1)][0], f'check:{m.group(1)}')
        if m.group(2):
            if m.group(2) in open_ids:
                open_ids.remove(m.group(2))
            return m.group(0)
        if m.group(0) == '<mark>':
            colour = KINDS[found[open_ids[-1]][0]][1] if open_ids else KINDS['VERIFY'][1]
            return f'<span style="background-color:{colour};">'
        return '</span>'
    return re.sub(r'<a name="chk-(\d+)"></a>|<a name="chkend-(\d+)"></a>|<mark>|</mark>', tok, body)


def _title_author(docx):
    """the Title and Author paragraphs of a docx (pandoc writes the title and author there)"""
    import zipfile
    xml = zipfile.ZipFile(str(docx)).read('word/document.xml').decode('utf-8')
    get = lambda style: html.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', (re.search(
        rf'<w:p[ >](?:(?!</w:p>).)*?<w:pStyle w:val="{style}"\s*/>.*?</w:p>', xml, re.S) or [''])[0])))
    return get('Title') or docx.stem, get('Author')


def _lost_comments(docx, found):
    """{id: (kind, comment)} for the docx's Word comments that pandoc's HTML no longer carries (those on the title)"""
    import zipfile
    z = zipfile.ZipFile(str(docx))
    if 'word/comments.xml' not in z.namelist():
        return {}
    out = {}
    for cid, body in re.findall(r'<w:comment [^>]*w:id="(\d+)"[^>]*>(.*?)</w:comment>', z.read('word/comments.xml').decode('utf-8'), re.S):
        if cid in found:
            continue
        text = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', body))).strip()
        kind = 'KEY' if text.startswith('KEY') else \
            next((k for k in ('VERIFY', 'YOUR WORDS', 'SPOT-CHECK') if text.startswith(k + ':')), 'VERIFY')
        out[cid] = (kind, text if kind == 'KEY' else text.split(':', 1)[-1].strip())
    return out


def _takeaways(m):
    """a Key Takeaways box drawn as in the Word document (paper_look.viewer_box): pandoc keeps neither its fills nor,
    in versions before the shared look, its bullets as paragraphs; anchors of author checks move with their bullet"""
    cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', m.group(0), re.S)
    if len(cells) != 2 or 'Key Takeaways' not in cells[0]:
        return m.group(0)
    items, carry = [], ''
    trailing = re.compile(r'(?:\s*<a name="[^"]+"></a>)+\s*$')
    for i, part in enumerate(re.sub(r'</?p(?: [^>]*)?>', ' ', cells[1]).split('\u2022')):
        cut = trailing.search(part) if i else None
        text = (carry + (part[:cut.start()] if cut else part)).strip()
        carry = cut.group(0).strip() if cut else ''
        if i:
            items.append(text)
        else:
            carry = text                          # anything before the first bullet goes with it
    if items and carry:
        items[-1] += carry
    return paper_look.viewer_box(items, re.sub(r'</?strong>', '', cells[0]).strip())


def prepare_review(docx=None):
    """(html, stats) for the text view of one version; cached on disk until that docx or the code changes. The
    reference numbers are read from the version's own reference list, since numbering differs between versions."""
    docx = pathlib.Path(docx or DOCX)
    links = BP.load_evidence(docx)                # the evidence pages of a version of the systematic review, if any
    records = [p.stat().st_mtime for p in BP.SHEETS.glob('*.json')] + \
              [p.stat().st_mtime for p in (BP._INC_F, BP._PUB_F) if p.exists()]   # the sheets, the included index, the published versions
    sig = hashlib.sha1(json.dumps([str(docx), docx.stat().st_mtime, docx.stat().st_size,
                                   pathlib.Path(__file__).stat().st_mtime,
                                   pathlib.Path(BP.__file__).stat().st_mtime,
                                   pathlib.Path(paper_look.__file__).stat().st_mtime,
                                   links.stat().st_mtime if links else 0, max(records, default=0), len(records)]).encode()).hexdigest()[:12]
    out, meta = CACHE / f'review-{sig}.html', CACHE / f'review-{sig}.json'
    if out.exists() and meta.exists():
        return out.read_text(encoding='utf-8'), json.loads(meta.read_text())
    raw = BP.pandoc_html(str(docx), comments=True)
    cited, unmatched = BP.cited_from_html(raw)
    doc, found = _take_comments(raw)
    TARGETS.clear()
    doc, stats = BP.annotate(doc, _make_link, cited=cited)
    stats['cited'], stats['unmatched'], stats['targets'] = cited, unmatched, list(TARGETS)
    body = re.search(r'<body[^>]*>(.*)</body>', doc, re.S).group(1)
    excerpts = _excerpts(body, found)
    body = re.sub(r'<header[^>]*>.*?</header>', '', body, flags=re.S)          # pandoc's placeholder title
    toc = re.compile(r'<p>\s*Table of Contents\s*</p>\s*<p>(.*?)</p>\s*<p>(.*?)</p>', re.S)
    if toc.search(body):                          # the earlier series: title and author follow a contents field
        body = toc.sub(lambda m: f'<h1 class="title">{m.group(1)}</h1><p class="author">{m.group(2)}</p>' + _contents(body)
                       + _checks_list(found, excerpts), body, count=1)
    else:                                         # the systematic review: title and author are the docx's own fields
        title, author = _title_author(docx)
        lost = _lost_comments(docx, found)        # pandoc drops comments on the title; show them as flags beside it
        found.update(lost)
        excerpts.update({cid: title for cid in lost})
        flags = ''.join(f' <a name="chk-{cid}"></a>' for cid in lost)          # _paint puts the flag at each anchor
        # comments on the author line lived in pandoc's header, removed above: their flags go beside the author
        orphans = [cid for cid in found if cid not in lost and f'name="chk-{cid}"' not in body]
        excerpts.update({cid: author for cid in orphans})
        aflags = ''.join(f' <a name="chk-{cid}"></a>' for cid in orphans)
        body = (f'<h1 class="title">{html.escape(title)}{flags}</h1><p class="author">{html.escape(author)}{aflags}</p>'
                + _contents(body) + _checks_list(found, excerpts) + body)
    body = re.sub(r'<figure[^>]*>', '<div align="center">', body).replace('</figure>', '</div>')
    body = re.sub(r'<figcaption[^>]*>(.*?)</figcaption>', r'<p class="figcap">\1</p>', body, flags=re.S)
    body = re.sub(r'<table[^>]*>\s*<caption[^>]*>(.*?)</caption>', r'<p class="tabcap">\1</p><table>', body,
                  flags=re.S)
    body = re.sub(r'<table[^>]*>', '<table width="98%" cellspacing="0" cellpadding="4">', body)
    body = re.sub(r'<colgroup>.*?</colgroup>', '', body, flags=re.S)
    body = re.sub(r'<table[^>]*>.*?</table>', _takeaways, body, flags=re.S)
    imgdir = CACHE / 'img'
    imgdir.mkdir(exist_ok=True)

    def save_img(m):                      # data: URIs -> cached files the text view can load
        data = base64.b64decode(m.group(2))
        f = imgdir / (hashlib.sha1(data).hexdigest()[:16] + '.' + m.group(1))
        if not f.exists():
            f.write_bytes(data)
        return f'src="{QUrl.fromLocalFile(str(f)).toString()}"'
    body = re.sub(r'src="data:image/(png|jpeg|gif);base64,([^"]+)"', save_img, body)
    body = _paint(body, found)
    stats['checks'] = {cid: [kind, text, excerpts.get(cid, '')] for cid, (kind, text) in found.items()}
    page = f'<html><body>{body}</body></html>'
    out.write_text(page, encoding='utf-8')
    meta.write_text(json.dumps(stats))
    return page, stats


REVIEW_CSS = paper_look.viewer_css() + """
.toch { font-family: 'Helvetica Neue'; font-size: 15px; font-weight: 700; color: #0f4761; margin-top: 10px; }
.toc1 { font-family: 'Helvetica Neue'; font-size: 14px; margin: 3px 0 1px 0; }
.toc2 { font-family: 'Helvetica Neue'; font-size: 13px; margin: 0 0 0 22px; }
.chkkey { font-family: 'Helvetica Neue'; font-size: 13px; margin: 2px 0 2px 0; }
.chkhelp { font-family: 'Helvetica Neue'; font-size: 12px; color: #555; margin: 0 0 4px 0; }
.chk { font-family: 'Helvetica Neue'; font-size: 12.5px; margin: 1px 0 1px 0; }
"""


class ReviewView(QTextBrowser):
    """The paper. Emits refClicked(key, page) for a reference; keeps figures fitted to the pane width."""
    refClicked = Signal(str, int, int)        # key, page, index into TARGETS (-1: none)
    checkClicked = Signal(str)

    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.document().setDefaultStyleSheet(REVIEW_CSS)
        self.document().setDocumentMargin(26)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)     # everything wraps to the pane; only 1-2 px of rounding could show
        self.anchorClicked.connect(self._on_anchor)
        self._natural, self._page, self._avail, self._laid, self._mark = {}, '', 0, False, None
        self._fit = QTimer(self, singleShot=True, interval=400, timeout=self._maybe_refit)

    def load(self, page_html):
        self._page = page_html
        self._render()

    def _render(self):
        """lay the paper out with each figure already sized to the pane. The figures are pre-scaled image files with
        fixed dimensions (and @2x files for Retina), so the document is never edited after loading - editing image
        formats in place breaks Qt's layout and hides most of the paper."""
        avail = max(240, self.viewport().width() - 2 * 26 - 16)
        top = self.cursorForPosition(self.viewport().rect().topLeft()).position() if self._laid else 0
        fitdir = CACHE / 'imgfit'
        fitdir.mkdir(exist_ok=True)

        def fit(m):
            src = QUrl(m.group(1)).toLocalFile()
            if src not in self._natural:
                self._natural[src] = QImage(src)
            img = self._natural[src]
            nw, nh = max(1, img.width()), max(1, img.height())
            w = int(min(avail, nw / 2.2))
            h = int(round(w * nh / nw))
            stem = pathlib.Path(src).stem
            f1, f2 = fitdir / f'{stem}-w{w}.png', fitdir / f'{stem}-w{w}@2x.png'
            if not f1.exists():
                img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(str(f1))
            if not f2.exists():
                img.scaled(2 * w, 2 * h, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(str(f2))
            return f'<img src="{QUrl.fromLocalFile(str(f1)).toString()}" width="{w}" height="{h}">'
        html_fitted = re.sub(r'<img[^>]*?src="(file:[^"]+)"[^>]*>', fit, self._page)
        self._avail = avail
        self.setHtml(html_fitted)
        self._laid = True
        if top:                                   # keep the reader's place after a re-layout
            c = QTextCursor(self.document())
            c.setPosition(min(top, self.document().characterCount() - 1))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + self.cursorRect(c).top())
        if self._mark:
            self.mark_link(*self._mark)

    def _on_anchor(self, url):
        s = url.toString()
        if s.startswith('ref:'):
            parts = s.split(':')
            self.refClicked.emit(parts[1], int(parts[2]), int(parts[3]) if len(parts) > 3 else -1)
        elif s.startswith('check:'):
            self.checkClicked.emit(s.split(':', 1)[1])
        elif s.startswith('#'):
            self.scrollToAnchor(s[1:])
        elif url.scheme() in ('http', 'https'):
            QDesktopServices.openUrl(url)

    def mouseReleaseEvent(self, e):
        href = self.anchorAt(e.position().toPoint())
        if href.startswith('ref:'):
            self._mark = (self.cursorForPosition(e.position().toPoint()).position(), href)
            self.mark_link(*self._mark)
        super().mouseReleaseEvent(e)

    def mark_link(self, pos, href):
        """highlight the clicked reference so the reader keeps their place"""
        block = self.document().findBlock(pos)
        it = block.begin()
        while not it.atEnd():
            fr = it.fragment()
            if fr.charFormat().anchorHref() == href and fr.position() <= pos <= fr.position() + fr.length():
                sel = QTextEdit.ExtraSelection()
                sel.cursor = QTextCursor(self.document())
                sel.cursor.setPosition(fr.position())
                sel.cursor.setPosition(fr.position() + fr.length(), QTextCursor.KeepAnchor)
                sel.format.setBackground(QColor('#ffe08a'))
                self.setExtraSelections([sel])
                return
            it += 1

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit.start()

    def _maybe_refit(self):
        if self._page and abs((self.viewport().width() - 2 * 26 - 16) - self._avail) >= 40:
            self._render()


# ================================================================= the PDF viewer

def page_sizes(key):
    """[(w, h) in points, rotation applied] for every page of the key's PDF"""
    pdf = str(PDFS[key])
    first = subprocess.run([PDFINFO, pdf], capture_output=True, text=True, timeout=30).stdout
    n = int(re.search(r'Pages:\s+(\d+)', first).group(1))
    out = subprocess.run([PDFINFO, '-f', '1', '-l', str(n), pdf], capture_output=True, text=True, timeout=60).stdout
    size = {int(a): (float(b), float(c)) for a, b, c in re.findall(r'Page\s+(\d+) size:\s+([\d.]+) x ([\d.]+)', out)}
    rot = {int(a): int(b) for a, b in re.findall(r'Page\s+(\d+) rot:\s+(\d+)', out)}
    res = []
    for i in range(1, n + 1):
        w, h = size.get(i, (612.0, 792.0))
        res.append((h, w) if rot.get(i, 0) % 180 == 90 else (w, h))
    return res


_RLOCK, _RLOCKS = threading.Lock(), {}


_SIG, _CLEANED = {}, set()


def pdf_sig(key):
    """the identity of the PDF behind a key: its real path, size and date, so that a replaced PDF (a published version
    for a preprint, a copy re-saved with highlights) is never shown from the renders of the old one"""
    if key not in _SIG:
        p = pathlib.Path(PDFS[key]).resolve()
        st = p.stat()
        _SIG[key] = hashlib.sha1(f'{p}|{st.st_size}|{st.st_mtime}'.encode()).hexdigest()[:10]
    return _SIG[key]


def render_page(key, i, dpi):
    sig = pdf_sig(key)
    out = CACHE / key / sig / f'p{i}-{dpi}.png'
    if out.exists():
        return out
    with _RLOCK:
        lock = _RLOCKS.setdefault((key, i, dpi), threading.Lock())
        if (key, sig) not in _CLEANED:                 # renders of another PDF once behind this key go
            _CLEANED.add((key, sig))
            d = CACHE / key
            for old in d.iterdir() if d.is_dir() else []:
                if old.name != sig:
                    shutil.rmtree(old, ignore_errors=True) if old.is_dir() else old.unlink(missing_ok=True)
    with lock:
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            root = out.with_name(f'p{i}-{dpi}.part')
            subprocess.run([PDFTOPPM, '-f', str(i), '-l', str(i), '-r', str(dpi), '-png', '-singlefile',
                            str(PDFS[key]), str(root)], check=True, capture_output=True, timeout=120)
            pathlib.Path(str(root) + '.png').replace(out)
    return out


# ================================================================= the quoted words on a page

_WORDS = {}


def _norm(w):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', w).lower())


def page_words(key, i):
    """[(normalised word, line index, (x0, y0, x1, y1) as fractions of the page)] in reading order, from Poppler's
    word boxes (pdftotext -bbox-layout) for page i of the key's PDF"""
    k = (key, pdf_sig(key), i)
    if k not in _WORDS:
        xml = subprocess.run([shutil.which('pdftotext') or '/opt/homebrew/bin/pdftotext', '-f', str(i), '-l', str(i),
                              '-bbox-layout', str(PDFS[key]), '-'], capture_output=True, text=True, timeout=60).stdout
        pg = re.search(r'<page width="([\d.]+)" height="([\d.]+)"', xml)
        W, H = (float(pg.group(1)), float(pg.group(2))) if pg else (612.0, 792.0)
        out, line = [], -1
        for m in re.finditer(r'<line\b|<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', xml, re.S):
            if m.group(5) is None:
                line += 1
                continue
            x0, y0, x1, y1 = (float(m.group(j)) for j in (1, 2, 3, 4))
            out.append((_norm(html.unescape(m.group(5))), line, (x0 / W, y0 / H, x1 / W, y1 / H)))
        _WORDS[k] = out
    return _WORDS[k]


def quote_boxes(key, i, quote):
    """the boxes (fractions of the page, one per line) of the longest run of the quotation's words found on page i,
    from its first words on; [] when fewer than three of them are found in a row. A word broken over a line end
    ("privacy-" + "preserving") counts as one."""
    Q = [w for w in (_norm(x) for x in re.sub(r'\.{3}|…', ' ', quote).split()) if w][:40]
    P = page_words(key, i)
    if len(Q) < 3 or not P:
        return []

    def run(i0):
        j, k = 0, i0
        while j < len(Q) and k < len(P):
            w = P[k][0]
            if not w:
                k += 1
            elif w == Q[j]:
                j, k = j + 1, k + 1
            elif k + 1 < len(P) and w + P[k + 1][0] == Q[j]:
                j, k = j + 1, k + 2
            elif j + 1 < len(Q) and w == Q[j] + Q[j + 1]:
                j, k = j + 2, k + 1
            else:
                break
        return j, k
    best = (0, 0, 0)
    for i0 in range(len(P)):
        if P[i0][0] and (P[i0][0] == Q[0] or (i0 + 1 < len(P) and P[i0][0] + P[i0 + 1][0] == Q[0])):
            j, k = run(i0)
            if j > best[0]:
                best = (j, i0, k)
    if best[0] < 3:
        return []
    lines = {}
    for w, line, (x0, y0, x1, y1) in P[best[1]:best[2]]:
        if not w:
            continue
        b = lines.get(line)
        lines[line] = (min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)) if b else (x0, y0, x1, y1)
    return [lines[k] for k in sorted(lines)]


class _Done(QObject):
    rendered = Signal(str, int, int, str)


class _Job(QRunnable):
    def __init__(self, key, i, dpi, done):
        super().__init__()
        self.key, self.i, self.dpi, self.done = key, i, dpi, done

    def run(self):
        try:
            path = str(render_page(self.key, self.i, self.dpi))
        except Exception:
            path = ''
        try:
            self.done.rendered.emit(self.key, self.i, self.dpi, path)
        except RuntimeError:                  # the window closed while this page was rendering
            pass


class PageLabel(QLabel):
    def __init__(self, i):
        super().__init__()
        self.i, self.dpi, self.path, self.marks = i, 0, '', []
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet('background:#ffffff; color:#9a9a9a; border:1px solid #3a3d41;')
        self.setText(f'Page {i}')
        self.badge = None

    def set_cited(self, on, passage=False):
        self.setStyleSheet('background:#ffffff; color:#9a9a9a; border:4px solid #f5b400;' if on else
                           'background:#ffffff; color:#9a9a9a; border:1px solid #3a3d41;')
        if on and self.badge is None:
            self.badge = QLabel('cited page', self)
            self.badge.setStyleSheet('background:#f5b400; color:#1c1c1c; font-weight:700; padding:2px 7px;'
                                     'border-radius:4px; border:none;')
        if self.badge:
            self.badge.setText('cited passage' if passage else 'cited page')
            self.badge.adjustSize()
            self.badge.setVisible(on)

    def show_render(self, path, dpi):
        """show a render of the page, with the quoted words outlined in red where the page has marks"""
        self.path, self.dpi = path, dpi
        pix = QPixmap(path)
        if self.marks and not pix.isNull():
            p = QPainter(pix)
            p.setPen(QPen(QColor('#e53935'), max(2.0, dpi / 45.0)))
            w, h = pix.width(), pix.height()
            for x0, y0, x1, y1 in self.marks:
                p.drawRect(int(x0 * w) - 3, int(y0 * h) - 2, int((x1 - x0) * w) + 6, int((y1 - y0) * h) + 4)
            p.end()
        self.setScaledContents(True)
        self.setPixmap(pix)

    def set_marks(self, marks):
        self.marks = list(marks)
        if self.dpi and self.path:
            self.show_render(self.path, self.dpi)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.badge:
            self.badge.adjustSize()
            self.badge.move(self.width() - self.badge.width() - 10, 10)


class PdfPane(QWidget):
    TOP, GAP, BOTTOM, SIDE = 12, 14, 40, 12

    def __init__(self):
        super().__init__()
        self.key, self.sizes, self.labels, self.ypos, self.zoom = None, [], [], [], 1.0
        self._target, self._target_frac, self._chips = None, 0.0, {}
        self.pool = QThreadPool.globalInstance()
        self.done = _Done()
        self.done.rendered.connect(self._on_rendered)
        self._pending = set()

        bar = QWidget()
        bar.setStyleSheet('QWidget{background:#2c2f33;color:#eeeeee;font-size:13px}'
                          'QToolButton,QPushButton{background:#44484d;border:1px solid #5d6268;border-radius:4px;'
                          'padding:3px 10px;color:#eee} QToolButton:hover,QPushButton:hover{background:#565b61}'
                          'QToolButton:disabled,QPushButton:disabled{color:#777}'
                          'QSpinBox{background:#44484d;border:1px solid #5d6268;border-radius:4px;color:#eee;'
                          'padding:2px 4px;min-width:52px}')
        rows = QVBoxLayout(bar)
        rows.setContentsMargins(10, 6, 10, 6)
        rows.setSpacing(5)
        r1, r2 = QHBoxLayout(), QHBoxLayout()
        r1.setSpacing(10)
        r2.setSpacing(6)
        rows.addLayout(r1)
        rows.addLayout(r2)
        self.where = QLabel('')                 # how the page was settled, the section, and the record's other pages
        self.where.setWordWrap(True)
        self.where.setTextFormat(Qt.RichText)
        self.where.setOpenExternalLinks(False)
        self.where.setStyleSheet('color:#d6d6d6; font-size:12px')
        self.where.linkActivated.connect(self._chip)
        self.where.hide()
        rows.addWidget(self.where)
        self.title = QLabel('No PDF open')
        self.title.setStyleSheet('font-weight:600; font-size:14px')
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.note = QLabel('')
        r1.addWidget(self.title, 1)
        r1.addWidget(self.note)
        self.prev = QToolButton(text='‹  Prev', toolTip='Previous page')
        self.spin = QSpinBox(minimum=1, maximum=1, toolTip='Go to page')
        self.total = QLabel('of 0')
        self.next = QToolButton(text='Next  ›', toolTip='Next page')
        self.zo = QToolButton(text='−', toolTip='Zoom out')
        self.zi = QToolButton(text='+', toolTip='Zoom in')
        self.fit = QToolButton(text='Fit width', toolTip='Fit the page to the pane width')
        self.preview = QPushButton('Open in Preview', toolTip='Open this PDF in Preview at the current page')
        for w in (self.prev, QLabel('Page'), self.spin, self.total, self.next):
            r2.addWidget(w)
        r2.addStretch(1)
        for w in (self.zo, self.zi, self.fit, self.preview):
            r2.addWidget(w)
        self.prev.clicked.connect(lambda: self.go(self.current() - 1))
        self.next.clicked.connect(lambda: self.go(self.current() + 1))
        self.spin.editingFinished.connect(lambda: self.go(self.spin.value()))
        self.zo.clicked.connect(lambda: self.set_zoom(self.zoom / 1.2))
        self.zi.clicked.connect(lambda: self.set_zoom(self.zoom * 1.2))
        self.fit.clicked.connect(lambda: self.set_zoom(1.0))
        self.preview.clicked.connect(lambda: self.key and open_in_preview(self.key, self.current(), self))
        self.controls = (self.prev, self.spin, self.next, self.zo, self.zi, self.fit, self.preview)
        for w in self.controls:
            w.setEnabled(False)

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)     # a stable width, so "fit" never overflows
        self.area.setStyleSheet('QScrollArea{background:#4b4f54;border:none}')
        self.inner = QWidget()
        self.inner.setStyleSheet('background:#4b4f54')
        self.col = QVBoxLayout(self.inner)
        self.col.setContentsMargins(self.SIDE, self.TOP, self.SIDE, self.BOTTOM)
        self.col.setSpacing(self.GAP)
        self.col.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.welcome = QLabel('Click a reference [n] in the paper to open its PDF here,\nat the cited page where known.')
        self.welcome.setAlignment(Qt.AlignCenter)
        self.welcome.setStyleSheet('color:#e8e8e8; font-size:15px; padding:60px 20px;')
        self.col.addWidget(self.welcome)
        self.area.setWidget(self.inner)
        sb = self.area.verticalScrollBar()
        sb.valueChanged.connect(self._on_scroll)
        sb.rangeChanged.connect(lambda *_: self._apply_target())

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(bar)
        v.addWidget(self.area, 1)
        self._relayout = QTimer(self, singleShot=True, interval=150, timeout=self._layout_pages)

    # ---- opening a PDF at a page
    def _chip(self, href):
        if href.startswith('chip:') and self.key:
            q = href.split(':', 1)[1]
            page, quote = self._chips.get(q, (1, ''))
            self.open(self.key, page, {'q': q, 'quote': quote, 'how': 'chip'})

    def open(self, key, page, target=None):
        """show the key's PDF at `page`; `target` = {'q': sheet question, 'quote': its quotation, 'how': how the page
        was settled (build_pdflinks_html.HOW, or 'chip')}: the quoted words are outlined and scrolled into view"""
        target = target or {}
        if key != self.key:
            self.key, self.sizes = key, page_sizes(key)
            for lab in self.labels:
                lab.deleteLater()
            self.labels = []
            self.welcome.hide()
            for i in range(1, len(self.sizes) + 1):
                lab = PageLabel(i)
                self.col.addWidget(lab, 0, Qt.AlignHCenter)
                self.labels.append(lab)
            self.zoom = 1.0
            self.spin.setMaximum(len(self.sizes))
            self.total.setText(f'of {len(self.sizes)}')
            for w in self.controls:
                w.setEnabled(True)
        page = max(1, min(len(self.sizes), page))
        quote, q, how = target.get('quote', ''), target.get('q', ''), target.get('how', '')
        marks = []
        if quote:
            try:
                marks = quote_boxes(key, page, quote)
            except Exception:
                marks = []
        for lab in self.labels:
            lab.set_cited(lab.i == page and page > 1, bool(marks))
            lab.set_marks(marks if lab.i == page else [])
        ref = REFS.get(key, {})
        self.full_title = f"[{NUM.get(key, '?')}]  {ref.get('cite', key)} — {ref.get('title', '')}"
        self.title.setToolTip(self.full_title)
        self._elide()
        settled = page > 1 or how in ('sentence', 'table', 'chip')
        if settled:
            self.note.setText(f'cited page {page}' + (' — quoted words outlined' if marks else ''))
            self.note.setStyleSheet('color:#f5c542; font-weight:700')
        else:
            self.note.setText('no single cited page — opened at page 1')
            self.note.setStyleSheet('color:#b8b8b8')
        # how the page was settled, the paper's section, and the record's other page-cited answers
        parts = []
        if settled:
            what = {'chip': "the record's answer"}.get(how) or BP.HOW.get(how, '')
            parts.append(f'Page {page}: {what}' + (f' (answer {q})' if q else '') +
                         ('' if marks else (' — the quoted words were not found on the page automatically' if quote else '')))
        section = BP.section_for(key, page) if page else ''
        if section:
            parts.append(f'in section “{html.escape(section)}”')
        ev = BP.sheet_evidence(key)
        self._chips = {k: v[0] for k, v in ev.items()}
        if ev:
            chips = ' · '.join(f'<a href="chip:{html.escape(k)}" style="color:#9fd3ff;text-decoration:none">'
                               f'<b>{html.escape(k)}</b> p.{pg}</a>' for k, (pg, _) in self._chips.items())
            parts.append(f'Record: {chips}')
        self.where.setText('<br/>'.join(parts))
        self.where.setVisible(bool(parts))
        self._target, self._target_frac = page, (min(m[1] for m in marks) if marks else 0.0)
        self._layout_pages()

    def _elide(self):
        if hasattr(self, 'full_title'):
            self.title.setText(self.title.fontMetrics().elidedText(self.full_title, Qt.ElideRight,
                                                                    max(120, self.title.width())))

    # ---- layout, zoom, navigation (page positions are computed, so a jump never waits on Qt's layout pass)
    def _layout_pages(self):
        if not self.labels:
            return
        keep = self._target or self.current()
        W = max(200, self.area.viewport().width() - 2 * self.SIDE - 2) * self.zoom
        y, self.ypos = self.TOP, []
        for lab, (w, h) in zip(self.labels, self.sizes):
            lab.setFixedSize(int(W), int(W * h / w))
            self.ypos.append(y)
            y += lab.height() + self.GAP
        self.inner.setMinimumHeight(y - self.GAP + self.BOTTOM)
        self.inner.setMinimumWidth(int(W) + 2 * self.SIDE)
        self._target = keep
        self._apply_target()
        QTimer.singleShot(0, self._apply_target)

    def _apply_target(self):
        if self._target is None or not self.ypos:
            return
        lab = self.labels[self._target - 1]
        vh = self.area.viewport().height()
        # scroll to the outlined words where there are some, keeping the page the current one
        off = max(0, min(int(self._target_frac * lab.height()) - 110, int(lab.height() - 0.6 * vh))) if self._target_frac else 0
        want = self.ypos[self._target - 1] - 8 + off
        sb = self.area.verticalScrollBar()
        sb.setValue(want)
        self._sync_spin()
        self._request_visible()
        if sb.value() == want or sb.maximum() >= self.inner.minimumHeight() - self.area.viewport().height() - 2:
            if sb.value() == min(want, sb.maximum()):
                self._target = None

    def set_zoom(self, z):
        self.zoom = max(0.4, min(4.0, z))
        self._target, self._target_frac = self.current(), 0.0
        self._layout_pages()

    def go(self, n):
        if self.labels:
            self._target, self._target_frac = max(1, min(len(self.labels), n)), 0.0
            self._apply_target()

    def current(self):
        if not self.ypos:
            return 1
        mid = self.area.verticalScrollBar().value() + self.area.viewport().height() // 3
        cur = 1
        for i, y in enumerate(self.ypos, 1):
            if y <= mid:
                cur = i
        return cur

    def _sync_spin(self):
        self.spin.blockSignals(True)
        self.spin.setValue(self.current())
        self.spin.blockSignals(False)

    def _on_scroll(self, _):
        if self.labels:
            self._sync_spin()
            self._request_visible()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()
        self._relayout.start()

    # ---- rendering the pages in view (and freeing far ones)
    def _dpi_for(self, lab, w_pts):
        need = lab.width() * self.devicePixelRatioF() / (w_pts / 72.0)
        return int(min(300, max(72, math.ceil(need / 50.0) * 50)))

    def _request_visible(self):
        if not self.ypos:
            return
        vh = self.area.viewport().height()
        top = self.area.verticalScrollBar().value() - vh
        bottom = top + 3 * vh
        cur = self.current()
        for lab, (w, h), y in zip(self.labels, self.sizes, self.ypos):
            if y + lab.height() >= top and y <= bottom:
                dpi = self._dpi_for(lab, w)
                if lab.dpi < dpi and (self.key, lab.i, dpi) not in self._pending:
                    self._pending.add((self.key, lab.i, dpi))
                    self.pool.start(_Job(self.key, lab.i, dpi, self.done))
            elif lab.dpi and abs(lab.i - cur) > 8:
                lab.clear()
                lab.setText(f'Page {lab.i}')
                lab.dpi, lab.path = 0, ''

    def _on_rendered(self, key, i, dpi, path):
        self._pending.discard((key, i, dpi))
        if key != self.key or not path or i > len(self.labels):
            return
        lab = self.labels[i - 1]
        if dpi < lab.dpi:
            return
        lab.show_render(path, dpi)

    def rendered(self, n):
        """True once page n has pixels (self-test)"""
        return bool(self.labels) and 1 <= n <= len(self.labels) and self.labels[n - 1].dpi > 0


# ================================================================= Preview

PREVIEW_SCRIPT = '''on run argv
    set f to POSIX file (item 1 of argv)
    set pg to (item 2 of argv) as integer
    tell application "Preview"
        activate
        open f
    end tell
    if pg > 1 then
        delay 0.9
        tell application "System Events"
            tell process "Preview"
                set frontmost to true
                keystroke "g" using {option down, command down}
                delay 0.5
                keystroke (pg as text)
                delay 0.1
                key code 36
            end tell
        end tell
    end if
end run'''

class _Notify(QObject):
    """carries a message from the Preview worker thread to the window (dialogs must open on the main thread)"""
    show = Signal(str, str)


NOTIFY = None          # created by the window, on the main thread
_warned = [False]


def open_in_preview(key, page, parent=None):
    """open the PDF in Preview and jump to `page` with Preview's Go to Page. macOS asks once for permission
    (Accessibility, and Automation of System Events); until it is given, the PDF opens at its first page."""
    pdf = str(PDFS[key])

    def work():
        r = subprocess.run(['osascript', '-e', PREVIEW_SCRIPT, pdf, str(page)], capture_output=True, text=True,
                           timeout=30)
        if r.returncode != 0 and not _warned[0] and NOTIFY is not None:
            _warned[0] = True
            NOTIFY.show.emit('Allow the page jump in Preview',
                             'The PDF was opened in Preview, but macOS did not let Review Viewer move it to page '
                             f'{page}.\n\nTo allow it: System Settings → Privacy & Security → Accessibility → turn on '
                             '“Review Viewer” (and allow it under Automation if asked). Then click the reference '
                             'again. The viewer on the right always opens at the cited page.'
                             f'\n\n(macOS: {r.stderr.strip()[:200]})')
    threading.Thread(target=work, daemon=True).start()


# ================================================================= the window

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'Review Viewer — {DOCX.stem}')
        self.version = None
        # the self-test uses its own throwaway settings, so a test never changes the reader's window layout
        self.settings = QSettings('Abertay-SZ', 'ReviewViewer-selftest' if os.environ.get('SELFTEST_DIR') else 'ReviewViewer')
        self.review = ReviewView()
        self.review.setPlainText('Preparing the review…')
        self.pdf = PdfPane()

        top = QWidget()
        top.setStyleSheet('QWidget{background:#eef2f6} QLabel{color:#33475b;font-size:13px}')
        th = QHBoxLayout(top)
        th.setContentsMargins(12, 6, 12, 6)
        self.info = QLabel('Click a reference [n] to open its PDF at the cited page.')
        self.find = QLineEdit(placeholderText='Find in the paper (⌘F)…')
        self.find.setMinimumWidth(220)
        self.find.setMaximumWidth(300)
        self.info.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.find.returnPressed.connect(self._find)
        self.use_preview = QCheckBox('Open references in Preview')
        self.use_preview.setChecked(self.settings.value('use_preview', False, bool))
        self.use_preview.toggled.connect(lambda v: self.settings.setValue('use_preview', v))
        self.pick = QComboBox(toolTip='Open another saved version of the paper: each version and its copy with the author checks')
        self.pick.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        vs = versions()
        nice = lambda label: label.replace(' + checks', ' — with author checks')
        ppml = [(l, q) for l, q in vs if not l.startswith('SLR')]          # the PPML review first, newest at the top
        slr = [(l, q) for l, q in vs if l.startswith('SLR')]
        for label, path in reversed(ppml):
            self.pick.addItem('PPML review ' + nice(label), str(path))
        if ppml and slr:
            self.pick.insertSeparator(self.pick.count())
        for label, path in reversed(slr):
            self.pick.addItem('ZK review ' + nice(label).replace('SLR ', ''), str(path))
        self.pick.setCurrentIndex(max(0, self.pick.findData(str(DOCX))))
        self.pick.activated.connect(lambda i: self.open_version(self.pick.itemData(i)))
        th.addWidget(QLabel('Version'))
        th.addWidget(self.pick)
        th.addWidget(self.info, 1)
        th.addWidget(self.find)
        th.addWidget(self.use_preview)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)
        lv.addWidget(top)
        lv.addWidget(self.review, 1)

        self.split = QSplitter(Qt.Horizontal)
        self.split.addWidget(left)
        self.split.addWidget(self.pdf)
        self.split.setStretchFactor(0, 56)
        self.split.setStretchFactor(1, 44)
        self.split.setHandleWidth(7)
        self.setCentralWidget(self.split)
        self.review.refClicked.connect(self.open_ref)
        self.review.checkClicked.connect(self.show_check)
        self.last_check = None
        global NOTIFY
        NOTIFY = _Notify()
        NOTIFY.show.connect(lambda title, text: QMessageBox.information(self, title, text))
        QShortcut(QKeySequence.Find, self, activated=lambda: (self.find.setFocus(), self.find.selectAll()))

        geo = None if os.environ.get('SELFTEST_DIR') else self.settings.value('geometry')
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1560, 980)
        st = None if os.environ.get('SELFTEST_DIR') else self.settings.value('split')
        if st:
            self.split.restoreState(st)
        else:
            self.split.setSizes([860, 700])

    def load(self, page_html, stats):
        CHECKS.clear()
        CHECKS.update(stats.get('checks', {}))
        NUM.clear()
        NUM.update({k: i + 1 for i, k in enumerate(stats.get('cited', [])) if k})
        TARGETS[:] = stats.get('targets', [])
        self.version = DOCX
        self.stats = stats
        self.page_html = page_html
        self.setWindowTitle(f'Review Viewer — {DOCX.stem}')
        self.review.load(page_html)
        checks = f"{len(CHECKS)} author checks: click a flag ⚑ to read one. " if CHECKS else ''
        miss = (f" {len(stats['unmatched'])} reference(s) could not be matched and are not linked."
                if stats.get('unmatched') else '')
        by = stats.get('by') or {}
        how = ', '.join(f"{n} {w}" for n, w in ((by.get('sentence', 0), "from the sentence's evidence"),
                                                (by.get('table', 0), 'from the record behind the table column'),
                                                (by.get('wording', 0) + by.get('paragraph', 0) + by.get('fact', 0), 'from the wording'))
                        if n)
        refs = (f"{stats['linked']} citations linked to the PDFs of {sum(1 for k in NUM if k in PDFS)} references, "
                f"{stats['exact']} at a cited passage ({how}): click a reference [n]." if NUM else
                'This version has no numbered references to link.')
        self.info.setText(f'{checks}{refs}{miss}')
        if self.pdf.key:                                       # the reference number shown on the PDF is per version
            self.pdf.open(self.pdf.key, self.pdf.current())

    def open_version(self, path):
        """show another saved version; its links are built from its own reference list"""
        global DOCX
        path = pathlib.Path(path)
        if self.version and path == self.version:
            return
        DOCX = path
        self.review.setPlainText(f'Preparing {path.stem} …')
        QApplication.processEvents()
        try:
            page_html, stats = prepare_review(path)
        except Exception:
            QMessageBox.critical(self, 'Review Viewer', 'Could not prepare this version:\n\n' + traceback.format_exc()[-1500:])
            return
        self.pick.setCurrentIndex(max(0, self.pick.findData(str(path))))
        self.load(page_html, stats)

    def show_check(self, cid):
        if cid not in CHECKS:
            return
        kind, text, excerpt = CHECKS[cid]
        self.last_check = (cid, text)
        if os.environ.get('SELFTEST_DIR'):                 # the self-test reads the check instead of opening a dialog
            return
        label = 'Key to the highlights' if kind == 'KEY' else kind
        where = excerpt if len(excerpt) <= 400 else excerpt[:400].rsplit(' ', 1)[0] + '…'
        QMessageBox.information(self, f'⚑{KINDS[kind][0]}{int(cid) + 1}  {label}',
                                f'{text}\n\nHighlighted passage:\n“{where}”')

    def open_ref(self, key, page, tid=-1):
        if key not in PDFS:
            return
        t = TARGETS[tid] if 0 <= tid < len(TARGETS) else None
        self.pdf.open(key, page, {'q': t[0], 'quote': t[1], 'how': t[2]} if t else None)
        if self.use_preview.isChecked():
            open_in_preview(key, page, self)

    def _find(self):
        if not self.review.find(self.find.text()):
            c = self.review.textCursor()
            c.movePosition(QTextCursor.Start)
            self.review.setTextCursor(c)
            self.review.find(self.find.text())

    def closeEvent(self, e):
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('split', self.split.saveState())
        super().closeEvent(e)


def completeness(win):
    """(ok, message): every paragraph and table cell of the docx is displayed and nothing is laid out at zero height"""
    import html as _h, unicodedata, zipfile
    doc = win.review.document()
    lay = doc.documentLayout()
    hidden, b = 0, doc.begin()
    while b.isValid():
        if lay.blockBoundingRect(b).height() <= 0:
            hidden += len(b.text().split())
        b = b.next()

    def norm(s):
        return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s).replace('\u00ad', '')).strip().lower()
    shown = norm(FLAG.sub(' ', doc.toPlainText()))
    xml = zipfile.ZipFile(str(DOCX)).read('word/document.xml').decode('utf-8')
    paras = [t for t in (_h.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p.replace('<w:tab/>', '<w:t> </w:t>'))))   # a tab is whitespace
                         for p in re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)) if len(t.strip()) >= 3]
    missing = [q for q in paras if norm(q) not in shown]
    ok = hidden == 0 and not missing
    return ok, (f'all {len(paras)} docx paragraphs and cells shown, none hidden' if ok else
                f'{len(missing)} docx paragraphs missing, {hidden} words hidden; first: {missing[:1]}')


def self_test(win, outdir):
    """Scripted run: clicks references the way a reader does and saves a screenshot per step. A step passes only when
    the viewer is scrolled to the cited page and that page has rendered."""
    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    refs = json.loads(os.environ.get('SELFTEST_REFS', '[["O096",13],["O082",7],["O005",1],["O101",1],["O096",1]]'))
    rb, pane = win.review, win.pdf
    results = []

    def click(u):
        return lambda: rb.anchorClicked.emit(QUrl(u))                 # the same path as a real click

    def find(text, at_bottom=False):
        def f():
            c = rb.textCursor()
            c.movePosition(QTextCursor.Start)
            rb.setTextCursor(c)
            rb.find(text)
            rb.ensureCursorVisible()
            sb = rb.verticalScrollBar()
            top = rb.cursorRect().top()
            sb.setValue(sb.value() + (top - rb.viewport().height() + 80 if at_bottom else top - 30))
        return f

    comp = {}

    def complete():
        comp['r'] = completeness(win)
        return comp['r'][0]

    def block_visible(text):
        def f():
            doc = rb.document()
            pos = doc.toPlainText().find(text)
            if pos < 0:
                return False
            c = QTextCursor(doc)
            c.setPosition(pos)
            r = rb.cursorRect(c)
            return 0 <= r.top() < rb.viewport().height() and \
                doc.documentLayout().blockBoundingRect(doc.findBlock(pos)).height() > 0
        return f

    steps = [('01-start', None, complete, 'whole paper laid out')]
    for k, (key, pg) in enumerate(refs, 2):
        steps.append((f'{k:02d}-{key}-p{pg}', click(f'ref:{key}:{pg}'),
                      (lambda key=key, pg=pg: pane.key == key and pane.rendered(pg) and pane.current() == pg),
                      f'[{NUM.get(key)}] {key} shown at page {pg}'))
    # a citation whose evidence is known opens at the page with the quoted words outlined: one settled by a table
    # column, one by its sentence (the first of each whose words Poppler finds on the page)
    for how in ('table', 'sentence'):
        for key, pg, tid in re.findall(r'href="ref:([^:"]+):(\d+):(\d+)"', getattr(win, 'page_html', '')):
            pg, tid = int(pg), int(tid)
            if TARGETS[tid][2] == how and TARGETS[tid][1] and quote_boxes(key, pg, TARGETS[tid][1]):
                steps.append((f'{len(steps) + 1:02d}-outline-{how}', click(f'ref:{key}:{pg}:{tid}'),
                              (lambda key=key, pg=pg: pane.key == key and pane.rendered(pg) and pane.current() == pg
                               and bool(pane.labels[pg - 1].marks) and pane.where.isVisible()),
                              f'[{NUM.get(key)}] {key} at page {pg}: the quoted words behind a {how} citation are outlined'))
                break
    n = len(steps) + 1
    # the targets below are read from the version on screen, so the test runs on either series
    plain_now = rb.document().toPlainText()
    toc = (re.search(r'href="(#[^"]*related-surveys[^"]*)"', win.page_html)                 # Section II, whatever its title
           or re.search(r'href="(#ii\.[^"]*)"', win.page_html)) if getattr(win, 'page_html', '') else None
    first_ref = (re.search(r'(?m)^\[1\] .{0,8}', plain_now) or [None])[0] or '[1] J. Cook'
    steps.append((f'{n:02d}-toc-related-surveys', click(toc.group(1) if toc else '#ii.-related-surveys'),
                  lambda: rb.verticalScrollBar().value() > 0, 'contents link scrolls to II'))
    steps.append((f'{n + 1:02d}-table-ii', find('TABLE II.'), lambda: True, 'Table II in the paper'))
    steps.append((f'{n + 2:02d}-figure-1', find('Fig. 1.', at_bottom=True), lambda: True, 'Figure 1 in the paper'))
    steps.append((f'{n + 3:02d}-references', click('#references'), block_visible(first_ref),
                  'contents link to References shows the reference list'))
    gd = f"[{NUM['gdpr2016']}] European Parliament"
    steps.append((f'{n + 4:02d}-ref-gdpr', find(gd), block_visible(gd),
                  f"reference {gd.split(']')[0]}] (the GDPR) visible in the list"))
    import zipfile
    ncom = zipfile.ZipFile(str(DOCX)).read('word/comments.xml').decode('utf-8').count('<w:comment ') \
        if 'word/comments.xml' in zipfile.ZipFile(str(DOCX)).namelist() else 0
    steps.append((f'{n + 5:02d}-checks-list', click('#author-checks'),
                  lambda: len(FLAG.findall(rb.document().toPlainText())) == 2 * ncom == 2 * len(CHECKS),
                  f'{ncom} author checks: a flag in the paper and one in the list for each'))
    src_text = next((s for s in ('IEEE Xplore', 'Claude in Chrome', 'ran the searches') if any(s in v[1] for v in CHECKS.values())),
                    'search')                           # the comment on the search sources (its wording differs between series)
    src = next((c for c, v in CHECKS.items() if src_text in v[1]), None)
    if src is None and CHECKS:                          # a version without a search-sources comment: the first check in the body
        title, author = _title_author(DOCX)
        src = next((c for c in sorted(CHECKS, key=int) if CHECKS[c][2] not in (title, author)), sorted(CHECKS, key=int)[0])
        src_text = CHECKS[src][1][:30]

    def flag_in_paper_visible(cid):                     # the second copy of a flag is the one in the paper
        token = re.compile(f'⚑{KINDS[CHECKS[cid][0]][0]}{int(cid) + 1}(?!\\d)')   # toPlainText turns &nbsp; into spaces

        def f():
            hits = [m.start() for m in token.finditer(rb.document().toPlainText())]
            if len(hits) < 2:
                return False
            pos = hits[1]
            c = QTextCursor(rb.document())
            c.setPosition(pos)
            r = rb.cursorRect(c)
            return r.bottom() > 0 and r.top() < rb.viewport().height()   # the flag's line is on screen
        return f
    steps.append((f'{n + 6:02d}-check-jump', click(f'#chk-{src}'), flag_in_paper_visible(src),
                  'a check in the list jumps to its place in the Method'))
    steps.append((f'{n + 7:02d}-check-open', click(f'check:{src}'),
                  lambda: bool(win.last_check) and win.last_check[0] == src and src_text in win.last_check[1],
                  'clicking a flag opens that check (the search-sources comment)'))
    steps.append((f'{n + 8:02d}-resized', lambda: win.split.setSizes([1050, 510]), complete,
                  'paper still complete after resizing the panes'))
    # other saved versions (SELFTEST_VERSIONS="22,23,24"): each must load, match every reference to its paper, show all
    # of its docx, and give RoFL the number that its own reference list gives it (the numbers differ between versions)
    vers = [int(v.strip().lstrip('Vv')) for v in os.environ.get('SELFTEST_VERSIONS', '').split(',') if v.strip()]
    paths = dict(versions())
    for k, num in enumerate(vers):
        path = paths.get(f'V{num}')

        def ready(path=path):
            if path is None or win.version != path or win.stats.get('unmatched') or not complete():
                return False
            n_rofl = NUM.get('O096')
            if n_rofl is None:
                return True
            entry = re.search(rf'(?m)^\[{n_rofl}\] [^\n]*', rb.document().toPlainText())
            return bool(entry) and 'RoFL' in entry.group(0)
        steps.append((f'{n + 9 + k:02d}-version-V{num}', (lambda path=path: win.open_version(path)), ready,
                      f'V{num} loads: every reference matched, nothing hidden, RoFL numbered as in its own list'))
    if vers:
        newest = versions()[-1][1]
        steps.append((f'{n + 9 + len(vers):02d}-back-to-newest', lambda: win.open_version(newest),
                      lambda: win.version == newest and not win.stats.get('unmatched'),
                      f'back to the newest version, {newest.stem.rsplit(" - ", 1)[-1]}'))
    state = {'i': 0, 'tries': 0}

    def tick():
        name, action, ready, what = steps[state['i']]
        if state['tries'] == 0 and action:
            action()
        state['tries'] += 1
        ok = ready()
        if ok or state['tries'] > 80:
            QApplication.processEvents()
            win.grab().save(str(out / f'{name}.png'))
            hbar = rb.horizontalScrollBar().maximum()
            if ready is complete and 'r' in comp:
                what = what + ' - ' + comp['r'][1]
            results.append((name, ok, what))
            print(f"{'PASS' if ok else 'FAIL'}  {name}: {what}", flush=True)
            state['i'] += 1
            state['tries'] = 0
            if state['i'] >= len(steps):
                print(f"SELFTEST {'PASSED' if all(r[1] for r in results) else 'FAILED'}: "
                      f"{sum(r[1] for r in results)}/{len(results)}", flush=True)
                QTimer.singleShot(200, QApplication.quit)
                return
        QTimer.singleShot(200, tick)
    QTimer.singleShot(1000, tick)


def main():
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Review Viewer')
    win = Main()
    win.show()
    QApplication.processEvents()
    try:
        page_html, stats = prepare_review()
    except Exception:
        QMessageBox.critical(win, 'Review Viewer', 'Could not prepare the review:\n\n' + traceback.format_exc()[-1500:])
        raise
    win.load(page_html, stats)
    app.aboutToQuit.connect(lambda: (QThreadPool.globalInstance().clear(),
                                     QThreadPool.globalInstance().waitForDone(5000)))
    if os.environ.get('SELFTEST_DIR'):
        self_test(win, os.environ['SELFTEST_DIR'])
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
