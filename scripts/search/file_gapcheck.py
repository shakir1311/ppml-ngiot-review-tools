#!/usr/bin/env python3
"""File the PDFs downloaded by the author for the gap check (3 October 2026) into corpus/searchcorpus/gapcheck/<id>/.

Each PDF is identified by the row of search/gapcheck/ZK-ABSTRACT-SCREEN-2026-10-03.csv it was downloaded for. A file
that is a whole book is cut down to the one chapter (its pages are taken from the book's own contents outline). The
first page of every filed PDF must carry the start of the record's title, otherwise nothing is filed for that row.
PROVENANCE.json records the source file and its SHA-256, the pages taken, the filed file's SHA-256 and the time.

Usage: scripts/.venv/bin/python scripts/search/file_gapcheck.py
"""
import csv, datetime, hashlib, json, pathlib, re, shutil, unicodedata
import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
DL = pathlib.Path('/Volumes/Stuff/Downloads')
OUT = ROOT / 'corpus' / 'searchcorpus' / 'gapcheck'
SCREEN = ROOT / 'search' / 'gapcheck' / 'ZK-ABSTRACT-SCREEN-2026-10-03.csv'
HOW = 'downloaded by the author through institutional access on 3 October 2026; filed by Claude Code'
FILES = {   # id -> (downloaded file, chapter title to cut from a book, or None)
    'n0626': ('Proof-of-Contribution-Based_Design_for_Collaborative_Machine_Learning_on_Blockchain (1).pdf', None),
    'n1034': ('Enhancing_Security_and_Privacy_in_Federated_Learning_for_Connected_Autonomous_Vehicles_With_Lightweight_Blockchain_and_Binius_ZeroKnowledge_Proofs.pdf', None),
    'n1640': ('A_Zero-Knowledge-Based_Approach_to_Resist_Poisoning_Attacks_in_Federated_Learning.pdf', None),
    'n1749': ('Blockchain-Enabled_Verifiable_Federated_Edge_AI_for_Cross-Organizational_Data_Collaboration.pdf', None),
    'n1951': ('Enabling_verifiability_in_federated_learning_utilizing_zero-knowledge_proofs_and_blockchain.pdf', None),
    'n2118': ('978-3-031-94898-5.pdf', 'FedShield'),
    'n2405': ('978-3-032-00639-4.pdf', 'Privacy-Preserving Knowledge Graph Sharing in Peer-to-Peer'),
    'n2723': ('Zero-Knowledge_Proof_Mechanisms_for_Trustless_Federated_Learning_on_Blockchain.pdf', None),
    'n2740': ('6G-Integrated_Federated_Learning_for_Trustworthy_and_Scalable_Edge-IoT_Collaboration.pdf', None),
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s).lower())


def chapter_pages(doc, title):
    toc = doc.get_toc()
    for i, (lvl, t, page) in enumerate(toc):
        if lvl == 1 and title.lower() in t.lower():
            nxt = next((p for l, _, p in toc[i + 1:] if l <= lvl), doc.page_count + 1)
            return page, nxt - 1
    raise SystemExit(f'chapter not found: {title}')


def main():
    rows = {r['n']: r for r in csv.DictReader(open(SCREEN, encoding='utf-8'))}
    for pid, (name, chapter) in FILES.items():
        src = DL / name
        if not src.exists():
            print(f'{pid}: {name} not found'); continue
        dest = OUT / pid
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f'{pid}.pdf'
        pages = None
        if chapter:
            book = pymupdf.open(src)
            a, b = chapter_pages(book, chapter)
            part = pymupdf.open()
            part.insert_pdf(book, from_page=a - 1, to_page=b - 1)
            part.save(out)
            pages = [a, b]
        else:
            shutil.copy2(src, out)
        first = pymupdf.open(out)[0].get_text()
        title = rows[pid]['title']
        if norm(title)[:40] not in norm(first):
            out.unlink()
            print(f'{pid}: first page does not carry the title "{title[:60]}" — not filed'); continue
        prov = {'id': pid, 'doi': rows[pid]['doi'], 'title': title, 'how': HOW, 'source_file': name, 'source_sha256': sha(src),
                'pages_of_source': pages, 'file': out.name, 'sha256': sha(out),
                'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
        (dest / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding='utf-8')
        print(f'{pid}: filed' + (f' (pages {pages[0]}–{pages[1]} of the book)' if pages else ''))


if __name__ == '__main__':
    main()
