#!/usr/bin/env python3
"""Prints a per-sentence table of a text of the paper (words, GPT-2 perplexity in paragraph context, structure flags: colon elaboration, semicolons, "is X by" passive, numbers, comma count, three-item list), to see which sentences carry the fingerprints an AI-text detector reacts to.

Paper only; run with the local checker's environment: local-checker/.venv/bin/python scripts/paper_ppml/ai_detect_sentences.py <text.txt> ...
"""
import sys,re,math,torch,torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForCausalLM
dev='mps' if torch.backends.mps.is_available() else 'cpu'
tok=AutoTokenizer.from_pretrained('gpt2'); m=AutoModelForCausalLM.from_pretrained('gpt2').to(dev).eval()
ABBR=['et al.','e.g.','i.e.','vs.','Fig.','Sect.','No.','cf.']
def sents(t):
    s=t
    for a in ABBR: s=s.replace(a,a.replace('.','§'))
    s=re.sub(r'(\d)\.(\d)',r'\1§\2',s)
    return [p.replace('§','.').strip() for p in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9“"(\[*])',s) if p.strip()]
for path in sys.argv[1:]:
    text=open(path).read().strip()
    print(f'\n### {path.split("/")[-1]}')
    for para in [p for p in text.split('\n\n') if p.strip()]:
        ss=sents(para); prev=''
        for s in ss:
            ctx=(prev+' '+s).strip()
            with torch.no_grad():
                e=tok(ctx,return_tensors='pt',truncation=True,max_length=1024).to(dev)
                L=m(**e).logits[0,:-1].float(); tgt=e['input_ids'][0,1:]; lp=F.log_softmax(L,-1)
                nll=-lp[torch.arange(len(tgt)),tgt]
                n_s=len(tok(' '+s if prev else s)['input_ids']); ppl=math.exp(nll[-n_s:].mean().item())
            w=len(re.findall(r"[A-Za-z][A-Za-z'’\-]*",s))
            flags=[]
            if ':' in s: flags.append('colon')
            if s.count(';')>=1: flags.append(f'semi{s.count(";")}')
            if re.search(r'\b(is|are) \w+ by\b',s): flags.append('is-X-by')
            if len(re.findall(r'\b\d+\b',s))>=2: flags.append('nums')
            if s.count(',')>=3: flags.append(f'commas{s.count(",")}')
            if re.search(r'\b\w+, \w+ and \w+\b',s): flags.append('triad?')
            print(f'{w:3d}w ppl{ppl:7.1f}  {",".join(flags):22s} {s[:110]}')
            prev=s
        print('   --')
