#!/usr/bin/env python3
"""Scores the paper's own prose with open-source AI-text detectors run on this Mac, so that every version is checked with local models before delivery: trained classifiers (Desklib DeBERTa, the e5 LoRA detector, Hello-SimpleAI HC3 RoBERTa, the OpenAI GPT-2 output detector, RADAR), Binoculars (Hans et al. 2024; observer/performer pair, a score below 0.9015 with the Falcon-7B pair means "AI"), Fast-DetectGPT (Bao et al. 2024; analytic criterion, calibrated probability with the Falcon-7B pair) and GPT-2 perplexity with GLTR token ranks.

Paper only: the inputs are the author's own texts (a .txt file per text, or a .json list of {name, text}); never a paper of the corpus.
GPTZero is not part of the pipeline (the author, 19 October 2026); these local models are.
Run with the local checker's environment, which holds torch and transformers:
    local-checker/.venv/bin/python scripts/paper_ppml/ai_detect.py <text.txt|items.json> ...
Environment: PAIR='["tiiuae/falcon-7b","tiiuae/falcon-7b-instruct"]' (the default; the Qwen2.5-1.5B pair is quicker but has no published threshold);
SKIP=clf,pair,gpt2 to leave a family out; CLFS=e5-LoRA,Desklib-DeBERTa to run only some classifiers (default: Desklib-DeBERTa,e5-LoRA); OUT=<scores.json>.
Models are fetched once into ~/.cache/huggingface. Readings: classifiers give P(AI) (0.5 and above = flagged); Binoculars lower = more AI-like; Fast-DetectGPT higher = more AI-like.
ai_detect_version.py imports score_items() to check every section of a built version.
"""
import gc, json, math, os, sys
import torch, torch.nn as nn, torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSequenceClassification, AutoModel, AutoConfig

DEV = 'mps' if torch.backends.mps.is_available() else 'cpu'
FALCON = ['tiiuae/falcon-7b', 'tiiuae/falcon-7b-instruct']
QWEN = ['Qwen/Qwen2.5-1.5B', 'Qwen/Qwen2.5-1.5B-Instruct']
BINOCULARS_THRESHOLD = 0.9015                                   # Falcon-7B pair, accuracy threshold of the paper
FDG_PARAMS = {'tiiuae/falcon-7b|tiiuae/falcon-7b-instruct': (-0.0707, 0.9520, 2.9306, 1.9039)}   # mu0, sigma0, mu1, sigma1 (Fast-DetectGPT local_infer.py)
CLASSIFIERS = [('Desklib-DeBERTa', 'desklib/ai-text-detector-v1.01'), ('e5-LoRA', 'MayZhou/e5-small-lora-ai-generated-detector'),
               ('HC3-RoBERTa', 'Hello-SimpleAI/chatgpt-detector-roberta'), ('OpenAI-RoBERTa-L', 'openai-community/roberta-large-openai-detector'),
               ('RADAR', 'TrustSafeAI/RADAR-Vicuna-7B')]
DEFAULT_CLFS = ['Desklib-DeBERTa', 'e5-LoRA']
COLS = ['Desklib-DeBERTa', 'e5-LoRA', 'HC3-RoBERTa', 'OpenAI-RoBERTa-L', 'RADAR', 'Binoculars', 'FastDetectGPT', 'FDG_P(AI)', 'GPT2_ppl', 'GLTR_top10']


def free(*ms):
    for m in ms:
        del m
    gc.collect()
    if DEV == 'mps':
        torch.mps.empty_cache()


def _desklib():
    from huggingface_hub import snapshot_download
    from safetensors.torch import load_file
    import glob
    d = snapshot_download('desklib/ai-text-detector-v1.01'); cfg = AutoConfig.from_pretrained(d)

    class DL(nn.Module):
        def __init__(s):
            super().__init__(); s.model = AutoModel.from_config(cfg); s.classifier = nn.Linear(cfg.hidden_size, 1)

        def forward(s, input_ids, attention_mask):
            h = s.model(input_ids=input_ids, attention_mask=attention_mask)[0]
            mk = attention_mask.unsqueeze(-1).expand(h.size()).float()
            return s.classifier((h * mk).sum(1) / mk.sum(1).clamp(min=1e-9))
    m = DL(); sd = {}
    for f in glob.glob(d + '/*.safetensors'):
        sd.update(load_file(f))
    m.load_state_dict(sd, strict=False)
    return AutoTokenizer.from_pretrained(d), m.to(DEV).eval()


def classify(items, res, clfs=DEFAULT_CLFS):
    """P(AI) from each trained classifier named in clfs."""
    for name, repo in CLASSIFIERS:
        if name not in clfs:
            continue
        if name == 'Desklib-DeBERTa':
            tok, m = _desklib()
            for it in items:
                with torch.no_grad():
                    enc = tok(it['text'], return_tensors='pt', truncation=True, max_length=768, padding=True).to(DEV)
                    res[it['name']][name] = torch.sigmoid(m(enc['input_ids'], enc['attention_mask'])).item()
        else:
            tok = AutoTokenizer.from_pretrained(repo); m = AutoModelForSequenceClassification.from_pretrained(repo).to(DEV).eval()
            lab = {int(k): v for k, v in m.config.id2label.items()}
            ai_idx = [k for k, v in lab.items() if v.lower() in ('chatgpt', 'fake', 'ai', 'label_1', 'machine', 'ai-generated', 'generated')]
            ai_idx = 0 if name == 'RADAR' else (ai_idx[0] if ai_idx else 1)
            for it in items:
                with torch.no_grad():
                    enc = tok(it['text'], return_tensors='pt', truncation=True, max_length=512).to(DEV)
                    res[it['name']][name] = F.softmax(m(**enc).logits, -1)[0, ai_idx].item()
        free(m, tok)
    return res


def pair_scores(items, res, pair=FALCON):
    """Binoculars (performer log-perplexity over observer-performer cross-perplexity) and Fast-DetectGPT (sampling = observer, scoring = performer)."""
    tok = AutoTokenizer.from_pretrained(pair[0]); dt = torch.bfloat16
    encs = {it['name']: tok(it['text'], return_tensors='pt', truncation=True, max_length=512) for it in items}
    obs = AutoModelForCausalLM.from_pretrained(pair[0], dtype=dt).to(DEV).eval(); O = {}
    with torch.no_grad():
        for k, e in encs.items():
            O[k] = obs(input_ids=e['input_ids'].to(DEV), attention_mask=e['attention_mask'].to(DEV)).logits[0, :-1].float().cpu()
    free(obs)
    perf = AutoModelForCausalLM.from_pretrained(pair[1], dtype=dt).to(DEV).eval()
    key = '|'.join(pair)
    with torch.no_grad():
        for k, e in encs.items():
            P = perf(input_ids=e['input_ids'].to(DEV), attention_mask=e['attention_mask'].to(DEV)).logits[0, :-1].float().cpu()
            tgt = e['input_ids'][0, 1:].cpu()
            V = min(P.shape[-1], O[k].shape[-1]); P = P[:, :V]; Ok = O[k][:, :V]
            ppl = F.cross_entropy(P, tgt).item()
            xppl = (-(F.softmax(Ok, -1) * F.log_softmax(P, -1)).sum(-1)).mean().item()
            res[k]['Binoculars'] = ppl / xppl
            lp = F.log_softmax(P, -1); pr = F.softmax(Ok, -1)
            ll = lp[torch.arange(len(tgt)), tgt]; mean = (pr * lp).sum(-1); var = (pr * lp.square()).sum(-1) - mean.square()
            crit = ((ll.sum() - mean.sum()) / var.sum().sqrt()).item(); res[k]['FastDetectGPT'] = crit
            if key in FDG_PARAMS:
                from scipy.stats import norm
                mu0, s0, mu1, s1 = FDG_PARAMS[key]; p0 = norm.pdf(crit, mu0, s0); p1 = norm.pdf(crit, mu1, s1)
                res[k]['FDG_P(AI)'] = p1 / (p0 + p1)
    free(perf, tok)
    return res


def gpt2_scores(items, res):
    """GPT-2 perplexity and the share of tokens GPT-2 ranks in its top 10 (GLTR)."""
    tok = AutoTokenizer.from_pretrained('gpt2'); m = AutoModelForCausalLM.from_pretrained('gpt2').to(DEV).eval()
    for it in items:
        with torch.no_grad():
            e = tok(it['text'], return_tensors='pt', truncation=True, max_length=1024).to(DEV)
            L = m(**e).logits[0, :-1].float(); tgt = e['input_ids'][0, 1:]; lp = F.log_softmax(L, -1)
            nll = -lp[torch.arange(len(tgt)), tgt]; rank = (lp > lp[torch.arange(len(tgt)), tgt][:, None]).sum(-1) + 1
            res[it['name']]['GPT2_ppl'] = math.exp(nll.mean().item()); res[it['name']]['GLTR_top10'] = (rank <= 10).float().mean().item()
    free(m, tok)
    return res


def score_items(items, pair=FALCON, skip=(), clfs=DEFAULT_CLFS):
    """Every detector family not in skip ('clf', 'pair', 'gpt2') on a list of {name, text}; returns {name: {detector: score}}."""
    res = {it['name']: {} for it in items}
    if 'clf' not in skip:
        classify(items, res, clfs)
    if 'pair' not in skip:
        pair_scores(items, res, pair)
    if 'gpt2' not in skip:
        gpt2_scores(items, res)
    return res


FDG_HUMAN_MEAN = FDG_PARAMS['tiiuae/falcon-7b|tiiuae/falcon-7b-instruct'][0]   # mu0 of the calibrated pair


def flags(r):
    """The detectors that call a scored text AI, by their published or conventional thresholds. Fast-DetectGPT: the calibrated
    probability is a two-Gaussian posterior, and far below the human mean (a text less predictable than human text) the wider
    AI Gaussian wins the tail; so the flag needs the criterion on the AI side of the human mean as well (20 October 2026: a short
    Key Takeaways box with a criterion of -3.8 was called AI at 0.69 by the posterior alone)."""
    out = []
    if r.get('Binoculars', 9) < BINOCULARS_THRESHOLD:
        out.append('Binoculars')
    if r.get('FDG_P(AI)', 0) >= 0.5 and r.get('FastDetectGPT', -9) > FDG_HUMAN_MEAN:
        out.append('Fast-DetectGPT')
    for c in ('Desklib-DeBERTa', 'e5-LoRA', 'HC3-RoBERTa', 'OpenAI-RoBERTa-L', 'RADAR'):
        if r.get(c, 0) >= 0.5:
            out.append(c)
    return out


def print_table(items, res):
    cols = [c for c in COLS if any(c in res[it['name']] for it in items)]
    print(f'{"text":44s}' + ''.join(f'{c:>17s}' for c in cols) + '  flagged by')
    for it in items:
        r = res[it['name']]
        print(f'{it["name"][:44]:44s}' + ''.join(f'{r[c]:17.3f}' if c in r else f'{"-":>17s}' for c in cols) + '  ' + (', '.join(flags(r)) or '-'))
    print('\nreading: classifiers = P(AI) 0..1 (0.5 and above = flagged); Binoculars lower = more AI-like (Falcon-7B threshold 0.9015, below = AI); '
          'FastDetectGPT higher = more AI-like, FDG_P(AI) its calibrated probability; GPT2_ppl lower = more predictable; GLTR_top10 = share of tokens GPT-2 ranks in its top 10')


def main(paths):
    items = []
    for p in paths:
        if p.endswith('.json'):
            items += json.load(open(p))
        else:
            items.append({'name': p.split('/')[-1], 'text': open(p).read().strip()})
    pair = json.loads(os.environ['PAIR']) if os.environ.get('PAIR') else FALCON
    skip = set(os.environ.get('SKIP', '').split(',')) - {''}
    clfs = [c for c in os.environ.get('CLFS', ','.join(DEFAULT_CLFS)).split(',') if c]
    res = score_items(items, pair, skip, clfs)
    json.dump(res, open(os.environ.get('OUT', '/tmp/detect_last.json'), 'w'), indent=1)
    print_table(items, res)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
