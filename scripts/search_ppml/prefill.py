#!/usr/bin/env python3
"""Pre-filled answers for the author's screening, by a fixed rule on cue words (4 October 2026).

The author checks every pre-filled answer in the screening app, changes the wrong ones and makes every decision. The
author chose a script rule over language-model suggestions ("Script pre-fill instead"; "why dont you use python for
suggestions ... it is a text based search in the end"). The rule only looks for words; it does not judge whether
privacy is studied or merely mentioned, so its answers are a starting point, not a reading.

The rule, per record (title, abstract, keywords; terms matched as in merge.py, hyphen or space alike):
  type      secondary  a survey word in the title (strings.SUR), the Scopus type Review, or a review phrase in the
                       abstract ("this survey", "we review", "systematic review", "literature review", "PRISMA" ...)
            primary    otherwise, when the abstract has an own-work phrase ("we propose", "this paper proposes",
                       "experimental results", "simulation results", "outperforms", "we design", "we implement" ...)
            unsure     neither kind of phrase
  privacy   yes        a privacy mechanism or privacy-attack term (differential privacy, homomorphic encryption,
                       secure multi-party computation, secret sharing, secure aggregation, trusted execution,
                       anonymisation, zero-knowledge proofs, membership inference, model inversion, gradient leakage ...), or, for a survey,
                       a privacy term in the title
            unsure     privacy named in the title (primary) or abstract (survey), but no such term
            no         privacy only in the keywords
  focus     (primary studies; the PhD focus in five parts, criteria V4, merge.FOCUS_PARTS) the parts whose cue words
            appear in the title, abstract or keywords: poisoning; malicious or fake participants; free riding;
            verification (other means); zero-knowledge proofs; blockchain; ZK on blockchain (also when the
            zero-knowledge and the blockchain cues both appear). focus = yes with the parts listed (focus_parts), or no when none appears. For a
            survey the parts are recorded too, but they never exclude it (criteria V4: every survey on the topic is kept).
  ngiot     yes        an NG-IoT term (strings.NGIOT, edge device, UAV, wearable ...) in the title, or twice in the abstract
            unsure     once in the abstract
            no         only in the keywords
  reason    the cue words that set the answers

  zk_proves (a study with the zero-knowledge angle) what the proof shows, by cue words: training done; update bounded
            (norm, range, bound); update similar (cosine, similarity, distance); aggregation; identity (identity,
            authentication, credential, membership, eligibility); inference. From the title, abstract and keywords; when
            they give none and the paper is in the corpus, from the sentences of its full text that name zero-knowledge
            and the authors' own work ("we", "our", "proposed", "this paper"), else from all its sentences naming
            zero-knowledge. Added 4 October 2026 at the author's request
            ("please prefill the answers for me to help me"); optional detail, decides nothing.

Records covered: all those the app shows (to screen, set-aside corpus papers, studies via other methods).
Output: search-ppml/PREFILL-2026-10-04.csv (n, type, privacy, focus, focus_parts, ngiot, reason), read by the app.

Usage: python3 scripts/search_ppml/prefill.py
"""
import csv, pathlib, re, sys
from collections import Counter

csv.field_size_limit(10 ** 9)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402
import strings as S                                   # noqa: E402

P = M.P
OUT = P / 'PREFILL-2026-10-04.csv'
rx = lambda terms: [(t.strip('"').replace('*', '').replace('?', 's'), M.term_re(t)) for t in terms]
REVIEW = rx(['"this survey"', '"this review"', '"we survey"', '"we review"', '"we systematically review"', '"systematic review"',
             '"systematic literature review"', '"literature review"', '"scoping review"', '"mapping study"', '"systematic mapping"',
             'PRISMA', '"we summari?e"', '"comprehensive review"', '"comprehensive survey"', '"state of the art review"', '"this article reviews"',
             '"this paper reviews"', '"this paper surveys"', '"this study reviews"', '"narrative review"', '"bibliometric"'])
OWN = rx(['"we propose"', '"we present"', '"we design"', '"we develop"', '"we implement"', '"we introduce"', '"this paper proposes"',
          '"this article proposes"', '"this study proposes"', '"this work proposes"', '"is proposed"', '"are proposed"', '"proposed scheme"',
          '"proposed framework"', '"proposed method"', '"proposed model"', '"proposed approach"', '"proposed system"', '"proposed algorithm"',
          '"proposed protocol"', '"experimental results"', '"simulation results"', '"numerical results"', '"experiments show"',
          '"experiments demonstrate"', 'outperform*', '"our scheme"', '"our framework"', '"our method"', '"our approach"', '"our model"'])
MECH = rx(['"differential privacy"', '"differentially private"', '"local differential privacy"', '"homomorphic encryption"', '"homomorphic"',
           'Paillier', 'CKKS', '"multi-party computation"', '"multiparty computation"', 'SMPC', 'MPC', '"secret sharing"', '"secure aggregation"',
           '"trusted execution"', 'TEE', 'SGX', 'enclave*', 'anonymi?ation', 'anonymi?ed', 'pseudonymi?ation', '"k-anonymity"',
           '"functional encryption"', '"encrypted gradient*"', '"encrypted update*"', '"encrypted model*"', '"gradient encryption"',
           '"masked gradient*"', '"masking"', '"perturbation"', '"noise injection"', '"membership inference"', '"model inversion"',
           '"gradient leakage"', '"reconstruction attack*"', '"attribute inference"', '"inference attack*"', '"privacy leakage"',
           '"re-identification"', '"privacy attack*"', '"privacy budget"', '"privacy risk*"', '"privacy-utility"',
           '"zero-knowledge"', '"zero knowledge"', 'zk-snark*', 'zksnark*', 'zk-stark*', 'zkp*', 'bulletproof*'])   # criteria V7: ZK proofs count
PRIV = rx(S.PPML)
PARTS = {name: rx(terms) for name, terms in M.FOCUS_PARTS.items()}
NGIOT = rx(S.NGIOT + ['"edge device*"', '"edge server*"', '"edge node*"', 'UAV*', 'drone*', 'wearable*', '"sensor network*"', 'V2X',
                      '"connected vehicle*"', '"autonomous vehicle*"', '"cyber-physical"', 'IoTs', '"smart home*"'])


def found(text, terms):
    return [t for t, p in terms if p.search(text)]


def rule(title, abstract, keywords, doc_type):
    ti, ab, kw = M.norm(title), M.norm(abstract), M.norm(keywords)
    ta = ti + ab
    why = []
    sur_t, rev_a, own_a = found(ti, rx(S.SUR)), found(ab, REVIEW), found(ab, OWN)
    if sur_t or doc_type == 'Review' or rev_a:
        typ = 'secondary'
        why.append('review: ' + (sur_t or rev_a or ['Scopus type Review'])[0])
    elif own_a:
        typ = 'primary'
        why.append('own work: ' + own_a[0])
    else:
        typ = 'unsure'
        why.append('no review or own-work phrase')
    mech, priv_t, priv_a = found(ta, MECH), found(ti, PRIV), found(ab, PRIV)
    if mech:
        privacy = 'yes'
        why.append('privacy: ' + mech[0])
    elif typ == 'secondary' and priv_t:
        privacy = 'yes'
        why.append('privacy in title: ' + priv_t[0])
    elif priv_t or (typ != 'primary' and priv_a):
        privacy = 'unsure'
        why.append('privacy named, no mechanism term')
    elif priv_a:
        privacy = 'no'
        why.append('privacy only mentioned, no mechanism term')
    else:
        privacy = 'no'
        why.append('privacy only in keywords')
    parts = [name for name, terms in PARTS.items() if found(ta + kw, terms)]
    if 'zero-knowledge proofs' in parts and 'blockchain' in parts and 'ZK on blockchain' not in parts:
        parts.append('ZK on blockchain')                  # both cues present: a guess the author checks (on-chain or not)
    parts = [x for x in M.FOCUS_PARTS if x in parts]
    focus = 'yes' if parts else 'no'
    why.append('PhD angles: ' + ', '.join(parts) if parts else 'no word for any PhD angle')
    ng_t = found(ti, NGIOT)
    ng_a = sum(len(p.findall(ab)) for _, p in NGIOT)
    if ng_t or ng_a >= 2:
        ngiot = 'yes'
        why.append('NG-IoT: ' + (ng_t or found(ab, NGIOT))[0])
    elif ng_a == 1:
        ngiot = 'unsure'
        why.append('NG-IoT named once')
    else:
        ngiot = 'no'
        why.append('NG-IoT only in keywords')
    return {'type': typ, 'privacy': privacy, 'focus': focus, 'focus_parts': '; '.join(parts),
            'ngiot': ngiot, 'reason': 'Rule — ' + '; '.join(why)}


ZK_SHOWS = {   # what a zero-knowledge proof shows: cue patterns (regular expressions on norm() text)
    'training': r'proof of (?:training|learning)|zkpot|verifiable training|(?:prove|proves|proving) (?:that )?(?:the )?(?:local )?(?:model )?(?:was |is )?(?:correctly )?train|correct(?:ly|ness of) (?:local )?training|training (?:was|is) (?:performed|executed|done) correctly',
    'bounded': r'\bnorm\b|norm bound|l2|range proof|\brange\b|bound(?:ed|s)? (?:on|of) (?:the )?(?:update|gradient|parameter)|within (?:a|the|an) (?:range|bound|interval)|bulletproof',
    'similarity': r'cosine|similarity|euclidean distance|distance (?:to|from|between)',
    'aggregation': r'verifiable aggregation|aggregat\w* (?:is |was |are )?(?:correct|verifi)|correct(?:ness of|ly) (?:the )?aggregat|proof of aggregation|aggregation proof',
    'identity': r'identit|authenticat|credential|membership(?! inference)|anonymous|eligib|\bsignature',
    'inference': r'(?<!membership )\binference\b(?! attack)|prediction (?:is |was )?correct|proof of inference|verifiable inference|zkml',
}
ZK_RX = {k: re.compile(v) for k, v in ZK_SHOWS.items()}
ZK_WORD = re.compile(r'zero knowledge|zk snark|zksnark|zk stark|\bzkp|\bzk\b|groth16|plonk|bulletproof|succinct non interactive')
OWN_WORK = re.compile(r'\bwe\b|\bour\b|proposed|this paper|this article|this work')


def zk_shows(text, full_text=''):
    """what the zero-knowledge proof shows, from cue words: first the record's own text, then own-work sentences of the full text"""
    hits = [k for k, rx in ZK_RX.items() if rx.search(M.norm(text))]
    if not hits and full_text:
        sentences = [M.norm(s) for s in re.split(r'(?<=[.!?])\s+', full_text)]
        zk = [s for s in sentences if ZK_WORD.search(s)]
        own = ' '.join(s for s in zk if OWN_WORK.search(s))
        hits = [k for k, rx in ZK_RX.items() if rx.search(own)] or [k for k, rx in ZK_RX.items() if rx.search(' '.join(zk))]
    return '; '.join(hits)


def corpus_full_text():
    """the full text of each record that is a corpus paper (record number -> text)"""
    idx = {r['id']: r for r in csv.DictReader(open(P / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))}
    ids = {m['n']: m['corpus_id'] for m in csv.DictReader(open(P / 'CORPUS-MATCHES-2026-10-04.csv', encoding='utf-8'))}
    ids.update({k['n']: k['corpus_id'] for k in csv.DictReader(open(P / 'OTHER-METHODS-2026-10-04.csv', encoding='utf-8'))})
    out = {}
    for n, cid in ids.items():
        if cid in idx and idx[cid]['pdf']:
            f = M.ROOT / pathlib.Path(idx[cid]['pdf']).parent / 'text' / 'full.txt'
            if f.exists():
                out[int(n)] = f.read_text(encoding='utf-8', errors='replace')
    return out


def records():
    R = list(csv.DictReader(open(P / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8')))
    aside = {m['n'] for m in csv.DictReader(open(P / 'CORPUS-MATCHES-2026-10-04.csv', encoding='utf-8')) if m['set_aside']}
    out = [(int(r['n']), r['title'], r['abstract'], r['keywords'], r['type'])
           for r in R if not r['auto_excluded'] or (r['auto_excluded'].startswith('IEEE') and r['n'] in aside)]
    out += [(int(k['n']), k['title'], k['abstract'], k['keywords'], 'Review' if k['kind'] == 'survey' else '')
            for k in csv.DictReader(open(P / 'OTHER-METHODS-2026-10-04.csv', encoding='utf-8'))]
    return out


def main():
    full = corpus_full_text()
    rows = []
    for n, t, a, k, d in records():
        row = {'n': n, **rule(t, a, k, d)}
        zk_here = 'zero-knowledge proofs' in row['focus_parts'] or ZK_WORD.search(M.norm(full.get(n, '')[:200000]))
        row['zk_proves'] = zk_shows(' '.join([t, a, k]), full.get(n, '')) if zk_here else ''
        rows.append(row)
    with open(OUT, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['n', 'type', 'privacy', 'focus', 'focus_parts', 'zk_proves', 'ngiot', 'reason'])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r['n']))
    print(len(rows), 'records pre-filled ->', OUT.name)
    for k in ('type', 'privacy', 'focus', 'ngiot'):
        print(' ', k, dict(Counter(r[k] for r in rows)))
    print('  focus parts', dict(Counter(p for r in rows for p in r['focus_parts'].split('; ') if p)))
    print('  zk shows', dict(Counter(p for r in rows for p in r['zk_proves'].split('; ') if p)), '| ZK records without a cue',
          sum(1 for r in rows if 'zero-knowledge proofs' in r['focus_parts'] and not r['zk_proves']))


if __name__ == '__main__':
    main()
