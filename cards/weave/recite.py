#!/usr/bin/env python3
"""Recitation matrix — acceptance check 2 for the phase-A oracle.

Shows the exported model one card face (as a one-card deal), greedily
decodes, and scores the line with the bake-off's own lexical instrument:
the word bag. A line belongs to the card it was shown when the shown
card's meaning tops the word-bag table among all 92 (ties against the
distractors are what "smearing" looks like — the SPEC's risk #1,
measured per card instead of hidden in a loss number). MiniLM cosines
would grade it finer; they also need an embedding runtime this machine
has no disk quota for. The word bag is the tool the bake-off used to
catch copying, and it needs nothing.

  python3 recite.py out-whisper2 [--deals 40] [--seed 7]
"""
import argparse
import json
import os
import re
import sys

import numpy as np

from tok import Tok
from train import _gen
from model import GPT
import corpus as C

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = re.compile(r"[a-z']+")


def bag(s):
    return set(WORDS.findall(s.lower()))


def load_export(out_dir):
    meta = json.load(open(os.path.join(out_dir, "meta.json")))
    cfg, tkmeta = meta["config"], meta["tok"]
    tok = Tok(tkmeta["cards"])
    assert tok.vocab_size == tkmeta["vocab_size"]
    model = GPT(np.random.default_rng(0), tok.vocab_size, d=cfg["d"],
                n_layer=cfg["n_layer"], n_head=cfg["n_head"], ctx=cfg["ctx"])
    binf = open(os.path.join(out_dir, "weights.bin"), "rb").read()
    for e in meta["entries"]:
        if e["dtype"] == "f32":
            model.p[e["name"]] = np.frombuffer(binf, np.float32, e["shape"][0], e["off"])
        else:
            r, c = e["shape"]
            q = np.frombuffer(binf, np.int8, r * c, e["off"]).reshape(r, c)
            model.p[e["name"]] = q * np.array(e["scale"], np.float32)[:, None]
    return model, tok, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--deals", type=int, default=92)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    model, tok, meta = load_export(a.out_dir)
    deck = C.load_deck()
    assert [c["name"] for c in deck] == meta["tok"]["cards"]

    # All 92 faces with their source strings (both pools, so a model that
    # learned either still recognises itself).
    faces = []
    for i, c in enumerate(deck):
        for face in ("up", "rev"):
            faces.append((i, face, " ".join([x for x in C.pool_for(c, face) if x])))

    rng = np.random.default_rng(a.seed)
    order = rng.permutation(len(faces))[: a.deals]
    hit = miss = 0
    misses = []
    for fi in order:
        i, face, src = faces[int(fi)]
        dom = "none"
        hdr = tok.header(dom, [(deck[i]["name"], "<noseat>", face)])
        line, _ = _gen(model, tok, hdr)
        lb = bag(line)
        if not lb:
            miss += 1
            misses.append((deck[i]["name"], face, "", "(empty)"))
            continue
        scores = []
        for (j, f2, s2) in faces:
            b2 = bag(s2)
            scores.append(len(lb & b2) / max(len(lb | b2), 1))
        best = int(np.argmax(scores))
        shown_here = [k for k, (j, f2, _) in enumerate(faces)
                      if j == i and f2 == face][0]
        if best == shown_here:
            hit += 1
        else:
            miss += 1
            bj, bf, _ = faces[best]
            misses.append((deck[i]["name"], face, deck[bj]["name"] + f" ({bf})",
                           line[:90]))
        print(f"{'ok ' if best == shown_here else 'X  '}{deck[i]['name'][:26]:26s} {face:3s} → {line[:80]}",
              flush=True)

    print(f"\nrecitation: {hit}/{hit+miss} lines belong to the shown card")
    for m in misses[:12]:
        print("  X", m)


if __name__ == "__main__":
    main()
