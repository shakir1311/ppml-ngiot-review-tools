#!/usr/bin/env python3
"""Counts the structural fingerprints of a text of the paper that word-level writing rules do not touch: colon elaborations, balanced ", and" compounds, agentless "is X by" passives, fronted framing openers, aphorisms of six words or fewer, first person, question marks, hedges, parentheses and three-item lists, with the sentence-length spread.

Paper only; plain Python: python3 scripts/paper_ppml/ai_fingerprints.py <text.txt> ...
"""
import sys,re,statistics as st
ABBR=['et al.','e.g.','i.e.','vs.','Fig.','Sect.','No.','cf.']
def sents(t):
    s=t
    for a in ABBR: s=s.replace(a,a.replace('.','§'))
    s=re.sub(r'(\d)\.(\d)',r'\1§\2',s)
    return [p.replace('§','.').strip() for p in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9“"(\[*])',s) if p.strip()]
def W(s): return re.findall(r"[A-Za-z][A-Za-z'’\-]*",s)
print(f'{"text":28s} sents  mean   sd   colon  ,and  isXby  fronted  <=6w  we/our   ?   hedge  paren  triadish')
for p in sys.argv[1:]:
    t=open(p).read(); ss=[s for s in sents(t) if len(W(s))>0]; n=len(ss); L=[len(W(s)) for s in ss]
    colon=sum(1 for s in ss if re.search(r':\s',s)); comp=sum(1 for s in ss if re.search(r', and (a|the|an|any|it|one|only|which|what|where|how|in|on|by|under|with|at|its|their|every|no|\d)\b',s))
    isx=sum(1 for s in ss if re.search(r'\b(is|are|was|were) \w+(ed|en|n) by\b',s))
    fronted=sum(1 for s in ss if re.match(r'^(In|On|By|Following|Under|Where|Whether|Judged|Taken|Read|From|For|As|Among|Of|With|Within)\b[^.]{0,60}?,',s))
    short=sum(1 for l in L if l<=6); we=sum(len(re.findall(r'\b(we|our|us|I)\b',s)) for s in ss); q=sum(s.count('?') for s in ss)
    hedge=sum(len(re.findall(r'\b(may|might|can|could|seems?|likely|in part|as a rule|in most cases|perhaps|some)\b',s)) for s in ss)
    paren=sum(1 for s in ss if re.search(r'\((?![A-Z0-9][A-Za-z0-9\-]*\))[^)]{4,}\)',s)); tri=sum(1 for s in ss if re.search(r'\b\w+, \w+ and \w+\b',s))
    print(f'{p.split("/")[-1][:28]:28s} {n:4d}  {st.mean(L):5.1f} {st.pstdev(L):5.1f}  {colon:4d}  {comp:4d}  {isx:4d}   {fronted:4d}   {short:4d}  {we:4d}  {q:4d}  {hedge:4d}  {paren:4d}   {tri:4d}')
