#!/usr/bin/env python3
"""The context judge: a local language model (run by Ollama on this Mac) reads a passage in its place on the page and
answers two closed questions — nothing else can come back from it:

  about    is the passage about the authors' OWN system, method, experiments or findings ('own'), about OTHER work —
           earlier or cited studies, the usual or traditional approach, a baseline, general background ('other') —
           or both ('mixed')?
  verdict  read in context, does the passage show that the statement holds for the authors' own work ('supports'),
           that it does not ('contradicts'), or neither ('neither')?

The model is told to reply with one JSON object of those two fields; the script keeps only the two allowed values and
treats anything else as 'invalid'. The raw reply (and any reasoning) is never printed or stored, so nothing the model
writes can carry paper text out. (The Homebrew build of Ollama runs these models on MLX without grammar-forced output,
so the shape is asked for in the instructions and enforced by the parser.)
"""
import json
import re
import time
import urllib.request

OLLAMA = 'http://127.0.0.1:11434/api/chat'
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['about', 'verdict'],
          'properties': {'about': {'type': 'string', 'enum': ['own', 'other', 'mixed']},
                         'verdict': {'type': 'string', 'enum': ['supports', 'contradicts', 'neither']}}}
SYSTEM = (
    "You check statements about one research paper against an excerpt of that paper. The excerpt is a stretch of one "
    "page; the passage to judge is marked [[[ like this ]]]. Read the surrounding text to understand who the passage is "
    "about.\n\n"
    "Question 1 (about): Is the marked passage about the authors' OWN proposed system, method, experiments or findings "
    "('own')? Or is it about OTHER work: earlier or cited studies, the usual, traditional or conventional approach, a "
    "baseline they compare against, a general description of a technology, or background ('other')? If it is about "
    "both, answer 'mixed'.\n\n"
    "Question 2 (verdict): Read in context, does the marked passage show that the statement is true of the authors' own "
    "work ('supports'), show that it is false for their own work ('contradicts'), or neither ('neither')? A passage about "
    "other work cannot support a statement about the authors' own work. Details matter: a different number, name, party "
    "or condition means it does not support.\n\n"
    'Reply with exactly one JSON object and nothing else: {"about": "own" | "other" | "mixed", '
    '"verdict": "supports" | "contradicts" | "neither"}')


def excerpt(paper, i, before=6, after=3):
    """The marked passage with the sentences around it on the same page."""
    page, text = paper.passages[i]
    same_page = [t for p, t in paper.passages if p == page]
    # one-sentence passages of the page, in order, rebuild the page; find where the marked passage sits
    singles = paper.sentences.get(page, [])
    start = next((k for k in range(len(singles)) if text.startswith(singles[k])), None)
    if start is None:
        return f'[[[ {text} ]]]'
    n = len(text.split())
    end, words = start, 0
    while end < len(singles) and words < n:
        words += len(singles[end].split())
        end += 1
    pre = ' '.join(singles[max(0, start - before):start])
    post = ' '.join(singles[end:end + after])
    return f'{pre} [[[ {text} ]]] {post}'.strip()


class Judge:
    def __init__(self, model, think=False):
        self.model, self.think = model, think

    def ask(self, paper, i, statement):
        body = {'model': self.model, 'stream': False, 'think': self.think,
                'options': {'temperature': 0, 'seed': 0, 'num_ctx': 8192},
                'messages': [{'role': 'system', 'content': SYSTEM},
                             {'role': 'user', 'content': f'Excerpt (page {paper.passages[i][0]}):\n{excerpt(paper, i)}\n\n'
                                                         f'Statement about the authors\' own work: {statement}'}]}
        req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=600) as r:
            reply = json.loads(r.read())
        content = reply['message']['content']                          # kept in memory only; 'thinking' is ignored
        m = re.search(r'\{[^{}]*\}', content)
        try:
            ans = json.loads(m.group(0)) if m else {}
            ans = {k: ans[k] for k in ('about', 'verdict') if ans.get(k) in SCHEMA['properties'][k]['enum']}
        except (json.JSONDecodeError, TypeError, AttributeError):
            ans = {}
        if len(ans) != 2:
            ans = {'about': 'invalid', 'verdict': 'invalid'}
        ans['seconds'] = round(time.time() - t0, 2)
        return ans
