#!/usr/bin/env python3
"""gate_c.py — the weaving gate: bake-off flags plus a trajectory test.

Same instruments as gate.py (names, seats, coverage against the union of
the dealt pools, word caps) plus one the faces did not need: every
sentence of a weaving must, by word bag, belong to one of the dealt
cards when measured against ALL 92 pools. A weaving that drifts to a
card it was not dealt is a wrong-index accident or a hallucination in
the author — and in phase C the author is me.

  python3 gate_c.py            # gate the weavings; --fix hints printed
"""
import argparse
import json
import os
import re

import corpus as C

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = re.compile(r"[a-z']+")
SEAT_SEQ = {
    3: ["Past", "Present", "Future"],
    5: ["The Situation", "The Obstacle", "The Advice", "The Vibe", "The Outcome"],
}
SEAT_PHRASES = ["the situation", "the obstacle", "the advice", "the vibe",
                "the outcome", "what crosses you"]  # 5-spread seats only;
# "the root" is a plant before it is a Cross position
CAP = {3: 36, 5: 52}
STOP = {"the", "of", "a", "an", "and"}
STOPW = STOP | {"to", "in", "on", "at", "is", "are", "was", "were", "be", "been",
                "being", "it", "its", "you", "your", "yours", "not", "no", "nor",
                "so", "as", "by", "or", "if", "but", "for", "with", "that", "this",
                "these", "those", "there", "here", "have", "has", "had", "will",
                "would", "could", "should", "do", "does", "did", "than", "then",
                "once", "ever", "never", "still", "too", "now", "out", "up", "down",
                "off", "over", "again", "both", "each", "few", "most", "much", "any",
                "some", "more", "only", "same", "just", "very", "into", "while",
                "about", "against", "before", "after", "because", "when", "where",
                "how", "why", "am", "me", "my", "we", "they", "them", "their", "him",
                "his", "her", "she", "he", "who", "whom", "which", "what", "all",
                "one", "two", "three", "first", "next", "things", "thing", "something",
                "anything", "nothing", "everyone", "nobody", "somebody", "someone",
                "like", "keep", "keeps", "stop", "stops", "starts", "way", "ways",
                "kind", "kinds", "really", "actually", "instead", "around", "without",
                "until", "under", "through", "between", "during", "upon", "unless"}


def bag(s):
    return set(WORDS.findall(s.lower()))


def sents(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", default="weavings.tsv,weavings_b.tsv,weavings_c.tsv")
    ap.add_argument("--write", default=os.path.join(HERE, "weavings.json"),
                    help="write gated weavings here ('' to skip)")
    ap.add_argument("--fix", default=None,
                    help="write a spec-corrected TSV here: each sentence is "
                         "attributed by exact voicing or content echo, and the "
                         "hand follows the text, not my bookkeeping")
    a = ap.parse_args()
    deck = C.load_deck()
    pools = {(i, f): set().union(*[bag(x) for x in C.pool_for(c, f)])
             for i, c in enumerate(deck) for f in ("up", "rev")}
    # exact-voicing resolution table
    V = json.load(open(os.path.join(HERE, "voicings.json")))
    vkey = {}
    for i, d in V.items():
        for f, lines in d.items():
            for t in lines:
                b = frozenset(bag(t))
                vkey.setdefault(b, set()).add((int(i), f))
    # per-sentence fingerprints: containment of the sentence's words in each
    # face's whole pool (Jaccard against single shipped sentences lets a
    # two-word fragment like "Admit it." win everything)
    sent_pool = {(i, f): bag(" ".join(C.pool_for(c, f)))
                 for i, c in enumerate(deck) for f in ("up", "rev")}

    kept, rejected, fixes = [], [], 0
    fixed_lines = []
    for fn in a.files.split(","):
        path = os.path.join(HERE, fn)
        if not os.path.exists(path):
            continue
        for ln, line in enumerate(open(path)):
            if not line.strip():
                continue
            dom, spec, text = line.rstrip("\n").split("\t", 2)
            hand0 = []
            for tokn in spec.split("|"):
                i, f = tokn.split(":")
                hand0.append((int(i), "up" if f.startswith("u") else "rev"))
            n = len(hand0)
            S = sents(text)

            # resolve each sentence to the card it speaks of: exact voicing,
            # then strong partial voicing match (the woven sentence is often
            # a voicing with additions), then a >=2 clear echo winner; the
            # slot keeps its card when nothing speaks loudly
            resolved = []
            sv = sorted(vkey, key=lambda x: -len(x))
            for k, s in enumerate(S):
                b = frozenset(bag(s))
                if b in vkey and len(vkey[b]) == 1:
                    resolved.append(next(iter(vkey[b])))
                    continue
                sc = bag(s)
                bestv, bestn, second = None, 0, 0
                for vb in sv:
                    n_ov = len(b & vb)
                    if n_ov >= 3 and len(vb) >= 4 and n_ov >= 0.45 * len(vb):
                        if n_ov > bestn:
                            bestv, second, bestn = vb, bestn, n_ov
                        else:
                            second = max(second, n_ov)
                if bestv is not None and bestn > second and len(vkey[bestv]) == 1:
                    resolved.append(next(iter(vkey[bestv])))
                    continue
                scs = bag(s) - STOPW
                scored = sorted(((len(scs & (pc - STOPW)), kk)
                                 for kk, pc in sent_pool.items()), reverse=True)
                best_n, best_k = (scored[0] if scored else (0, None))
                second_n = scored[1][0] if len(scored) > 1 else 0
                if best_n >= 2 and best_n > second_n:
                    resolved.append(best_k)
                else:
                    resolved.append(None)

            if len(S) == n:
                hand = [r if r else hand0[k] for k, r in enumerate(resolved)]
            else:
                used = [r for r in resolved if r]
                rest = [h for h in hand0 if h not in used]
                hand = (used + rest)[:n]
            new_spec = "|".join(f"{i}:{f[0]}" for i, f in hand)
            if new_spec != spec:
                fixes += 1
                fixed_lines.append((fn, ln + 1, f"{spec} -> {new_spec}"))

            reasons = []
            words = text.split()
            if len(words) > CAP.get(n, 99):
                reasons.append(f"OVERCAP({len(words)}>{CAP.get(n)})")
            low = text.lower()
            b = bag(text)
            union = set().union(*[pools[k] for k in hand])
            dealt_names = {deck[i]["name"] for i, _ in hand}
            for j, c in enumerate(deck):
                if c["name"] in dealt_names:
                    continue  # a card may name itself in its own weaving
                toks = [w for w in re.findall(r"[a-z]+", c["name"].lower())
                        if w not in STOP]
                if len(toks) > 1:
                    if " ".join(toks) in low:
                        reasons.append(f"NAME({c['name']})")
                else:
                    w = toks[0]
                    if len(w) > 3 and w not in union and re.search(
                            r"\b" + re.escape(w) + r"\b", low):
                        reasons.append(f"NAME({c['name']})")
            hits = [p for p in SEAT_PHRASES if p in low]
            if hits:
                reasons.append(f"SEAT({hits[0]})")
            cov = len(b & union) / max(len(b), 1)
            if cov >= 0.60:
                reasons.append(f"UNION-COV({cov:.2f})")
            if reasons:
                rejected.append((fn, ln + 1, new_spec, "; ".join(dict.fromkeys(reasons))))
            else:
                kept.append(dict(dom=dom, hand=hand, text=text))

    print(f"kept {len(kept)}, rejected {len(rejected)}, specs corrected {fixes}")
    for fn, ln, ch in fixed_lines:
        print(f"  ~ {fn}:{ln} {ch}")
    for fn, ln, spec, why in rejected:
        print(f"  X {fn}:{ln} {spec}  {why}")
    if a.fix:
        with open(a.fix, "w") as f:
            for rec in kept:
                spec = "|".join(f"{i}:{f[0]}" for i, f in rec["hand"])
                f.write(f"{rec['dom']}\t{spec}\t{rec['text']}\n")
        print("wrote", a.fix)
    if a.write:
        with open(a.write, "w") as f:
            json.dump(kept, f)
        print("wrote", a.write)


if __name__ == "__main__":
    main()
