#!/usr/bin/env python3
"""gate.py — the bake-off flags, pointed at the corpus instead of the model.

The WP4 lesson: the source text is what gets copied, so keep it out of
the output. Rather than trusting that (or the generator's discretion),
every candidate re-voicing passes the bench's own instruments at
corpus-build time — NEAR-COPY as word-bag coverage against the face's
own shipped strings, the 20-word cap, the seat-name and card-name
flags. A rejected line is rejected loudly, with its coverage printed;
nothing is quietly kept.

  python3 gate.py            # gate the TSVs, write voicings.json
"""
import json
import os
import re
import sys

import corpus as C

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = re.compile(r"[a-z']+")
STOP_EXTRA = {"the", "of", "a", "an", "and"}
SEAT_PHRASES = ["the situation", "the obstacle", "the advice", "the vibe",
                "the outcome", "what crosses you", "the crown", "the root",
                "hopes and fears", "the self", "the house", "the recent past",
                "the near future"]


def bag(s):
    return set(WORDS.findall(s.lower()))


def main():
    deck = C.load_deck()
    pool = {}   # (i, face) -> src bag
    name = {}
    for i, c in enumerate(deck):
        for face in ("up", "rev"):
            pool[(i, face)] = set().union(*[bag(x) for x in C.pool_for(c, face)])
        name[i] = c["name"]

    # every card name's content words, for the name flag
    rows, seen = [], set()
    for fn in ("faces_a.tsv", "faces_b.tsv", "faces_c.tsv", "faces_d.tsv"):
        path = os.path.join(HERE, fn)
        if not os.path.exists(path):
            continue
        for ln, line in enumerate(open(path)):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            i, face, text = line.split("\t", 2)
            i = int(i)
            rows.append((i, face, text, fn, ln + 1))

    kept, rejected = [], []
    for i, face, text, fn, ln in rows:
        key = (i, face, text)
        if key in seen:
            rejected.append((i, face, text, fn, ln, "duplicate"))
            continue
        seen.add(key)
        reasons = []
        b = bag(text)
        if not b:
            reasons.append("empty")
        if len(text.split()) > 20:
            reasons.append(f"OVER20({len(text.split())})")
        cov = len(b & pool[(i, face)]) / max(len(b), 1)
        if cov >= 0.70:
            reasons.append(f"COPY-EXPANSION({cov:.2f})")
        low = text.lower()
        nm = re.sub(r"\b(the|of|a|an|and)\b", "", name[i].lower()).strip()
        nm = " ".join(nm.split())
        if nm and re.search(r"\b" + re.escape(nm) + r"\w*\b", low):
            reasons.append("NAME-IN-LINE")
        hits = [p for p in SEAT_PHRASES if p in low]
        if hits:
            reasons.append("SEAT-NAME-IN-LINE:" + hits[0])
        if not re.search(r"[.!?]$", text.strip()):
            reasons.append("UNTERMINATED")
        (kept if not reasons else rejected).append(
            (i, face, text) if not reasons else (i, face, text, fn, ln, reasons[0]))

    out = {}
    for i, face, text in [(k[0], k[1], k[2]) for k in kept]:
        out.setdefault(f"{i}", {}).setdefault(face, []).append(text)
    with open(os.path.join(HERE, "voicings.json"), "w") as f:
        json.dump(out, f, indent=1)

    print(f"kept {len(kept)} of {len(rows)} candidates ({len(rows)-len(kept)} rejected)")
    by = {}
    for r in rejected:
        why = r[5].split("(")[0]
        by[why] = by.get(why, 0) + 1
        print(f"  X {r[0]:>2} {r[1]:3s} {r[5]:24s} {r[2][:70]}")
    print("tally:", by)
    per = [len(v.get('up', [])) + len(v.get('rev', [])) for v in out.values()]
    print(f"per-card totals: min {min(per)}, max {max(per)}, cards under 8: {sum(1 for p in per if p < 8)}")


if __name__ == "__main__":
    main()
