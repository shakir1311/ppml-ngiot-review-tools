#!/usr/bin/env python3
"""Check statements about a paper against the paper's own extracted text, on this Mac, with a fact-verification model.

No language model and no outside service: a BM25 word search picks the passages of the paper most like the statement, and a
natural-language-inference classifier (DeBERTa-v3-large trained on MNLI, FEVER, ANLI, LingNLI and WANLI) scores each
passage against the statement: entails / neutral / contradicts. The statement counts as
  supported     when some passage entails it with probability >= --support (default 0.80),
  contradicted  when some passage contradicts it with probability >= --contradict (default 0.80) and none supports it,
  not found     otherwise (no passage settles it).

Input  (JSONL, one statement per line): {"id": ..., "key": <study id>, "claim": <statement>, "pages": [optional pages to include]}
Output (JSONL): id, key, verdict, best entailment (score, page), best contradiction (score, page), passages scored.
The passages themselves are never written or printed: the output holds no text of the paper.

Usage: local-checker/run.sh CLAIMS.jsonl OUT.jsonl [--support 0.8] [--contradict 0.8] [--top 24]
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAPERS = Path(os.environ.get('CHECKER_PAPERS') or ROOT / 'notes-verifier' / 'data' / 'papers.json')   # tests use a made-up list
MODEL = 'MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
REVISION = 'b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'          # the exact model version that was tested (README)
WORD = re.compile(r'[a-z0-9]+(?:[.,][0-9]+)*')
SENTENCE_END = re.compile(r'(?<=[.!?;])\s+(?=[A-Z0-9(\[])')


def clean(text):
    text = unicodedata.normalize('NFKC', text).replace('­', '')
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)            # words broken across lines
    return re.sub(r'\s+', ' ', text).strip()


def tokens(text):
    return WORD.findall(text.lower())


# The word check: a passage can support a statement only if it carries the statement's numbers, its contrast words and
# most of its content words. It stops the classifier from accepting a passage that is about the same thing but says
# something else (a different number, 'public' for 'private', 'vertical' for 'horizontal').
STOP = set('''a an the and or but if of to in on at by for with from as is are was were be been being it its this that these
those there their they them we our you your he she his her which who whom whose what when where how than then so such
can could may might must shall should will would do does did done has have had having not no nor only also very more most
less least each every all any both either neither some same other another into onto over under about after before between
during through within without upon via per paper study survey authors author article work works says say said states
stated state reports reported report uses used use using show shows shown given gives give one two three four five six
seven eight nine ten'''.split())
# Words whose opposite turns a statement round. Each set is one side; a statement that uses a word from one side needs a
# passage that uses that side and not the other.
SIDES = [({'public'}, {'private'}), ({'permissioned'}, {'permissionless'}),
         ({'centralized', 'centralised'}, {'decentralized', 'decentralised'}), ({'on-chain', 'onchain'}, {'off-chain', 'offchain'}),
         ({'encrypted'}, {'unencrypted', 'plaintext'}), ({'trusted'}, {'untrusted'}), ({'honest'}, {'malicious', 'dishonest'}),
         ({'increase', 'increases', 'increased', 'increasing', 'rise', 'rises', 'rose', 'grow', 'grows', 'grew', 'higher',
           'more', 'raise', 'raises', 'raised'},
          {'decrease', 'decreases', 'decreased', 'decreasing', 'fall', 'falls', 'fell', 'drop', 'drops', 'dropped', 'lower',
           'fewer', 'less', 'reduce', 'reduces', 'reduced'}),
         ({'before'}, {'after'}), ({'always'}, {'never'}), ({'horizontal'}, {'vertical'}),
         ({'synchronous'}, {'asynchronous'}), ({'supervised'}, {'unsupervised'}), ({'outperforms'}, {'underperforms'}),
         ({'publickey', 'publickeys'}, {'privatekey', 'privatekeys'})]
FIXED_TERMS = [('public key', 'publickey'), ('private key', 'privatekey'), ('public keys', 'publickeys'),
               ('private keys', 'privatekeys'), ('public parameters', 'publicparameters')]
SYMBOLS = [('×', ' times '), ('~', ' about '), ('≈', ' about '), ('>', ' more than '), ('<', ' less than '),
           ('≥', ' at least '), ('≤', ' at most '), ('%', ' percent ')]
NUMBER_WORDS = {'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
                'ten': '10'}


def stem(w):
    return w[:6]


def words_of(text):
    for sym, word in SYMBOLS:
        text = text.replace(sym, word)
    text = text.lower()
    for term, joined in FIXED_TERMS:
        text = text.replace(term, joined)
    ws = re.findall(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*", re.sub(r'(?<=\d)[ ,\u2009\u202f](?=\d{3}\b)', '', text.lower()))
    return [NUMBER_WORDS.get(w, w) for w in ws]


NAME = re.compile(r'\b[A-Z][\w\-]*(?:\s+(?:of|for|the|in|on|over|with|and)?\s*[A-Z][\w\-]*)+')
LEADING = set('the a an in on at for this these those that our its their table figure fig section each every all no both'
              .split())
WORD_SHARE = 0.67                                      # set by main() from --words


def names_in(text):
    """Multi-word names ('Proof of Training Quality', 'Hyperledger Fabric'): they must appear in a passage as they are."""
    out = []
    for m in NAME.finditer(text):
        words = m.group(0).split()
        while words and words[0].lower() in LEADING:
            words = words[1:]
        if len(words) >= 2:
            out.append(' '.join(words))
    return out


def squashed(text):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKC', text).lower())


def word_check(claim, passage):
    """(passes, share): whether the passage may support the claim, and the share of the claim's content words it holds
    (the share alone decides whether a passage is about the same thing, for contradictions)."""
    cw, pw = words_of(claim), words_of(passage)
    p_stems, p_set, c_set = {stem(w) for w in pw}, set(pw), set(cw)
    content = [w for w in cw if len(w) >= 4 and w not in STOP and not w.isdigit()]
    share = sum(stem(w) in p_stems for w in content) / len(content) if content else 1.0
    numbers = [w for w in cw if re.fullmatch(r'\d+(?:\.\d+)?', w)]
    if any(n not in p_set for n in numbers):
        return False, share
    for one, other in SIDES:                           # a word with an opposite: the passage must use the statement's
        for mine, theirs in ((one, other), (other, one)):    # side and not also the other (left to a person)
            if (mine & c_set) and not (theirs & c_set):
                if not (mine & p_set) or (theirs & p_set):
                    return False, share
    if any(squashed(n) not in squashed(passage) for n in names_in(claim)):
        return False, share
    return share >= WORD_SHARE, share


class Paper:
    """The paper's pages, cut into every passage of one, two and three consecutive sentences."""

    def __init__(self, folder: Path):
        self.passages = []                                          # (page, text)
        self.sentences = {}                                         # page -> its sentences in order (context judge)
        pages = {}
        for sub in ('pages', 'pages_ocr'):
            for f in sorted((folder / 'text' / sub).glob('page_*.txt')):
                pages.setdefault(int(f.stem.split('_')[1]), []).append(f.read_text(encoding='utf-8', errors='ignore'))
        for n in sorted(pages):
            sentences = [s for s in SENTENCE_END.split(clean(' '.join(pages[n]))) if len(s.split()) >= 3]
            self.sentences[n] = sentences
            for size in (1, 2, 3):
                for i in range(len(sentences) - size + 1 if len(sentences) >= size else 0):
                    window = ' '.join(sentences[i:i + size])
                    self.passages.append((n, ' '.join(window.split()[:160])))
        from rank_bm25 import BM25Okapi
        self.bm25 = BM25Okapi([tokens(t) for _, t in self.passages]) if self.passages else None

    def candidates(self, claim, top, pages=()):
        """The passages most like the claim, plus those of the hint pages."""
        if not self.passages:
            return []
        scores = self.bm25.get_scores(tokens(claim))
        best = sorted(range(len(self.passages)), key=lambda i: -scores[i])[:top]
        extra = [i for i, (p, _) in enumerate(self.passages) if p in set(pages)][:top]
        return sorted(set(best) | set(extra))


class Verifier:
    def __init__(self):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.torch = torch
        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.tok = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL, revision=REVISION).to(self.device).eval()
        labels = {v.lower(): int(k) for k, v in self.model.config.id2label.items()}
        self.ent, self.con = labels['entailment'], labels['contradiction']

    def score(self, premises, hypothesis, batch=16):
        out = []
        for i in range(0, len(premises), batch):
            enc = self.tok(premises[i:i + batch], [hypothesis] * len(premises[i:i + batch]), truncation='only_first',
                           max_length=512, padding=True, return_tensors='pt').to(self.device)
            with self.torch.no_grad():
                probs = self.model(**enc).logits.softmax(-1).float().cpu().tolist()
            out += [(p[self.ent], p[self.con]) for p in probs]
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('claims')
    ap.add_argument('out')
    ap.add_argument('--support', type=float, default=0.80)
    ap.add_argument('--contradict', type=float, default=0.80)
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--words', type=float, default=0.67, help='share of content words a supporting passage must hold')
    ap.add_argument('--judge', help='local model (Ollama) that reads each deciding passage in context (context_judge.py)')
    ap.add_argument('--think', action='store_true', help='let the judge model reason before answering (slower)')
    a = ap.parse_args()
    global WORD_SHARE
    WORD_SHARE = a.words
    out = Path(a.out).resolve()
    if HERE not in out.parents:
        sys.exit(f'Refusing to write {out}: results go inside {HERE} only, never next to sheets, notes, summaries or papers.')
    listing = json.loads(PAPERS.read_text())['papers']
    folders = {p['key']: ROOT / p['folder'] for p in listing}
    # a primary study's statements are about its own design; a survey's content is other work, so any passage may speak
    scopes = {p['key']: ('own' if 'primary' in p.get('role', '') else 'any') for p in listing}
    judge = None
    if a.judge:
        from context_judge import Judge
        judge = Judge(a.judge, think=a.think)
    claims = [json.loads(line) for line in Path(a.claims).read_text(encoding='utf-8').splitlines() if line.strip()]
    verifier, papers = Verifier(), {}
    t0, done = time.time(), []
    with open(a.out, 'w', encoding='utf-8') as out:
        for c in claims:
            paper = papers.get(c['key']) or papers.setdefault(c['key'], Paper(folders[c['key']]))
            idx = paper.candidates(c['claim'], a.top, c.get('pages') or ())
            scores = verifier.score([paper.passages[i][1] for i in idx], c['claim'])
            checks = [word_check(c['claim'], paper.passages[i][1]) for i in idx]
            ok = [j for j in range(len(idx)) if checks[j][0]]                     # passages that pass the word check
            relevant = [j for j in range(len(idx)) if checks[j][1] >= 0.5]        # passages about the same thing
            ent = con = 0.0
            ent_page = con_page = ent_at = con_at = None
            if ok:
                e_i = max(ok, key=lambda j: scores[j][0])
                ent, ent_page, ent_at = scores[e_i][0], paper.passages[idx[e_i]][0], idx[e_i]
            if relevant:
                c_i = max(relevant, key=lambda j: scores[j][1])
                con, con_page, con_at = scores[c_i][1], paper.passages[idx[c_i]][0], idx[c_i]
            raw = max((s[0] for s in scores), default=0.0)
            verdict = ('supported' if ent >= a.support else
                       'contradicted' if con >= a.contradict else 'not found')
            judged = {}
            if judge and verdict != 'not found':
                judged = judge_passages(judge, paper, c, idx, scores, ok, relevant, a, c.get('scope') or scopes.get(c['key'], 'any'))
                verdict = judged.pop('verdict')
                if 'at' in judged:
                    at = judged.pop('at')
                    if verdict == 'supported':
                        ent, ent_page, ent_at = scores[idx.index(at)][0], paper.passages[at][0], at
                    elif verdict == 'contradicted':
                        con, con_page, con_at = scores[idx.index(at)][1], paper.passages[at][0], at
            row = {'id': c['id'], 'key': c['key'], 'verdict': verdict,
                   'entails': round(ent, 3), 'entails_page': ent_page,
                   'contradicts': round(con, 3), 'contradicts_page': con_page, 'passages_scored': len(idx),
                   'entails_without_word_check': round(raw, 3),
                   'entails_passage': ent_at, 'contradicts_passage': con_at,   # passage numbers only, for show.py
                   **judged}
            for k in ('expected', 'group'):
                if k in c:
                    row[k] = c[k]
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
            done.append(row)
    secs = time.time() - t0
    print(f'{len(done)} statements in {secs:.0f} s ({secs / max(1, len(done)):.2f} s each) on {verifier.device}'
          + (f'; judge {a.judge}' if a.judge else ''))


def judge_passages(judge, paper, c, idx, scores, ok, relevant, a, scope, tries=3):
    """Ask the context judge about the passages the classifier relies on, best first. A statement is supported only
    if the judge agrees that a passage supports it and (for a study's own design) is about the authors' own work;
    contradicted likewise. When the classifier found something but the judge accepts none of it: 'unclear'."""
    asked, seconds = [], 0.0
    sup = sorted((j for j in ok if scores[j][0] >= a.support), key=lambda j: -scores[j][0])[:tries]
    for j in sup:
        ans = judge.ask(paper, idx[j], c['claim'])
        seconds += ans['seconds']
        asked.append(f"{ans['about']}/{ans['verdict']}")
        if ans['verdict'] == 'supports' and (scope == 'any' or ans['about'] == 'own'):
            return {'verdict': 'supported', 'at': idx[j], 'judge': asked, 'judge_seconds': round(seconds, 1)}
    con = sorted((j for j in relevant if scores[j][1] >= a.contradict), key=lambda j: -scores[j][1])[:tries]
    for j in con:
        ans = judge.ask(paper, idx[j], c['claim'])
        seconds += ans['seconds']
        asked.append(f"{ans['about']}/{ans['verdict']}")
        if ans['verdict'] == 'contradicts' and (scope == 'any' or ans['about'] in ('own', 'mixed')):
            return {'verdict': 'contradicted', 'at': idx[j], 'judge': asked, 'judge_seconds': round(seconds, 1)}
    return {'verdict': 'unclear', 'judge': asked, 'judge_seconds': round(seconds, 1)}


if __name__ == '__main__':
    sys.exit(main())
