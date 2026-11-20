#!/usr/bin/env python3
"""eval_b.py — the rewrite matrix, acceptance check 2 for phase B.

Phase A asked: can it say the card's line? Phase B asks the harder
question: will it say the card's line *differently* — and stay on the
card while doing it? Same instrument as the bake-off bench and gate.py
(word bags, coverage ≥ 0.70 = COPY-EXPANSION), now pointed at model
output across the whole 46×2 face matrix, plus two new readings:

  OFF   — the line's word bag matches a DIFFERENT card's meaning better
          than the one shown (drift; the grief attractor's species)
  PARROT— the output is an exact shipped or voicing string: fine for
          whisper, noted for voice so we can see paraphrase exist

  python3 eval_b.py out-whisper-b
"""
import argparse
import json
import os
import re
import sys

import numpy as np

import corpus as C
from model import GPT
from tok import Tok
from train import load_model, sample

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = re.compile(r"[a-z']+")


def bag(s):
    return set(WORDS.findall(s.lower()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--cap", type=int, default=120)
    a = ap.parse_args()

    tok = Tok()
    rng = np.random.default_rng(0)
    model, cfg = load_model(a.out_dir, rng, tok.vocab_size)
    deck = C.load_deck()
    all_voicings = json.load(open(os.path.join(HERE, "voicings.json")))
    shipped = {f"{i}|{f}": set(C.pool_for(c, f)) for i, c in enumerate(deck)
               for f in ("up", "rev")}
    all_src = set()
    for s in shipped.values():
        all_src |= s
    for d in all_voicings.values():
        for lines in d.values():
            for t in lines:
                all_src |= bag(t)

    heads = {}
    for i, c in enumerate(deck):
        for face in ("up", "rev"):
            heads[f"{i}|{face}"] = tok.header("work", [
                (tok.card_ids[c["name"]], tok.seat_ids["The Situation"], face)])

    results, fails = {}, []
    for i, c in enumerate(deck):
        for face in ("up", "rev"):
            line = sample(model, tok, heads[f"{i}|{face}"], max_new=a.cap)
            line = line.strip()
            b = bag(line)
            own = bag(" ".join(C.pool_for(c, face)))
            cov = len(b & own) / max(len(b), 1)
            # nearest other card
            best, bestj = None, 0.0
            for j, d in enumerate(deck):
                for g in ("up", "rev"):
                    if (j, g) == (i, face):
                        continue
                    p = bag(" ".join(C.pool_for(d, g)))
                    jv = len(b & p) / max(len(b | p), 1)
                    if jv > bestj:
                        best, bestj = deck[j]["name"] + f" ({g})", jv
            flags = []
            if cov >= 0.70:
                flags.append(f"COPY({cov:.2f})")
            if best and bestj > cov + 0.05 and bestj > 0.25:
                flags.append(f"OFF->{best}({bestj:.2f})")
            if bestj > 0.60:
                flags.append(f"OVER20sim({bestj:.2f})")
            nm = re.sub(r"\b(the|of|a|an|and)\b", "", c["name"].lower()).strip()
            nm = " ".join(nm.split())
            if nm and re.search(r"\b" + re.escape(nm) + r"\w*\b", line.lower()):
                flags.append("NAME")
            if len(line.split()) > 20:
                flags.append("OVER20")
            known = set(C.pool_for(c, face)) | set(all_voicings.get(str(i), {}).get(face, []))
            parrot = line in known
            results[f"{i}|{face}"] = dict(line=line, cov=round(cov, 2), flags=flags)
            if flags:
                fails.append((c["name"], face, flags, line))

    n = len(results)
    print(f"{'card':>22}  face  cov   line")
    for i, c in enumerate(deck):
        for face in ("up", "rev"):
            r = results[f"{i}|{face}"]
            mark = "X " if r["flags"] else "  "
            print(f"{mark}{c['name']:>20}  {face}  {r['cov']:.2f}  {r['line'][:88]}")
    copy_f = sum(1 for r in results.values() if any(x.startswith('COPY') for x in r['flags']))
    off_f = sum(1 for r in results.values() if any(x.startswith('OFF') for x in r['flags']))
    parrots = sum(1 for k, r in results.items() if r['line'] in
                  (set(C.pool_for(deck[int(k.split('|')[0])], k.split('|')[1])) |
                   set(all_voicings.get(k.split('|')[0], {}).get(k.split('|')[1], []))))
    print(f"\nflags: {len(fails)}  (COPY {copy_f}, OFF {off_f}) of {n}; "
          f"exact-known-string outputs (parrots): {parrots}")


if __name__ == "__main__":
    main()
