#!/usr/bin/env python3
"""Tests of the local checker on made-up text (never a paper). Run: local-checker/.venv/bin/python local-checker/test_checker.py

Checks the word check, the page reading, the search, the end-to-end run on a made-up paper, that the input files are left
byte for byte as they were, and that results cannot be written outside local-checker/.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_claims as cc

ok = True


def check(label, cond):
    global ok
    ok &= bool(cond)
    print(('PASS ' if cond else 'FAIL ') + label)


P = 'The ledger is a permissioned consortium chain. Throughput drops to ~ 378 TPS with > 20 000 concurrent transactions.'
check('same words pass', cc.word_check('The ledger is a permissioned consortium chain.', P)[0])
check('a changed number fails', not cc.word_check('Throughput drops to about 387 TPS.', P)[0])
check('a missing number fails', not cc.word_check('The chain has 12 validators.', P)[0])
check('the opposite word fails (permissionless for permissioned)',
      not cc.word_check('The ledger is a permissionless consortium chain.', P)[0])
check('symbols read as words (~ about, > more than)',
      cc.word_check('Throughput drops to about 378 TPS with more than 20,000 concurrent transactions.', P)[0])
check('thousands separators ignored (20,000 = 20 000)', '20000' in cc.words_of('20,000') and '20000' in cc.words_of('20 000'))
check('number words read as digits (six = 6)', '6' in cc.words_of('six participants'))
check('a passage about something else fails', not cc.word_check('Clients encrypt gradients with Paillier keys.', P)[0])
check('horizontal is not vertical',
      not cc.word_check('The best horizontal accuracy uses two participants.',
                        'For vertical FL, the best accuracy uses 2 participants.')[0])

home = Path(tempfile.mkdtemp(prefix='.test-', dir=str(HERE)))
try:
    folder = home / 'paper' / 'text' / 'pages'
    folder.mkdir(parents=True)
    (folder / 'page_0001.txt').write_text('Introduction. Federated learning keeps data on devices. We study privacy.\n')
    (folder / 'page_0002.txt').write_text('The ledger is a permissioned consortium chain run by edge servers. '
                                         'Each update is encrypted with Paillier before upload. The server sees only the sum.\n')
    (folder / 'page_0003.txt').write_text('Results. Accuracy reaches 97.4% after 50 rounds. Latency rises from 0.41 ms to 0.52 ms.\n')
    paper = cc.Paper(home / 'paper')
    check('pages are read and cut into passages', {p for p, _ in paper.passages} == {1, 2, 3})
    best = paper.candidates('Is the ledger a consortium chain?', top=1)
    check('the search finds the right page', paper.passages[best[0]][0] == 2)
    check('hint pages are always included', any(paper.passages[i][0] == 1 for i in paper.candidates('ledger', 1, [1])))

    papers = home / 'papers.json'
    papers.write_text(json.dumps({'papers': [{'key': 'demo', 'folder': str(home / 'paper'), 'role': 'included study (primary)'}]}))
    claims = home / 'claims.jsonl'
    rows = [('t1', 'The ledger is a permissioned consortium chain.', 'supported'),
            ('t2', 'Accuracy reaches 97.4% after 50 rounds.', 'supported'),
            ('t3', 'Accuracy reaches 99.1% after 50 rounds.', 'not supported'),
            ('t4', 'The ledger is a public chain open to anyone.', 'not supported'),
            ('t5', 'Latency rises from 0.41 ms to 0.52 ms.', 'supported'),
            ('t6', 'Latency falls from 0.52 ms to 0.41 ms.', 'not supported')]
    claims.write_text('\n'.join(json.dumps({'id': i, 'key': 'demo', 'claim': c, 'expected': e}) for i, c, e in rows))
    before = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in list(folder.glob('*')) + [claims, papers]}
    env = dict(os.environ, HF_HOME=str(HERE / '.cache' / 'huggingface'), CHECKER_PAPERS=str(papers))
    out = home / 'out.jsonl'
    r = subprocess.run([sys.executable, str(HERE / 'check_claims.py'), str(claims), str(out)], env=env,
                       capture_output=True, text=True)
    check('a run on a made-up paper finishes', r.returncode == 0 and out.exists())
    if out.exists():
        res = {x['id']: x for x in map(json.loads, out.read_text().splitlines())}
        for i, c, e in rows:
            got = res[i]['verdict']
            check(f'  {i}: "{c}" -> {got}', (got == 'supported') == (e == 'supported'))
        check('results hold no passage text', all(set(x) <= {'id', 'key', 'verdict', 'entails', 'entails_page', 'contradicts',
                                                            'contradicts_page', 'passages_scored',
                                                            'entails_without_word_check', 'expected', 'group',
                                                            'entails_passage', 'contradicts_passage'}
                                                  for x in res.values()))
    after = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in before}
    check('the paper pages and the input files are unchanged', before == after)
    bad = subprocess.run([sys.executable, str(HERE / 'check_claims.py'), str(claims), str(home.parent.parent / 'x.jsonl')],
                         env=env, capture_output=True, text=True)
    check('results cannot be written outside local-checker/', bad.returncode != 0
          and not (home.parent.parent / 'x.jsonl').exists())
finally:
    shutil.rmtree(home, ignore_errors=True)
print('ALL PASS' if ok else 'SOME CHECKS FAILED')
sys.exit(0 if ok else 1)
