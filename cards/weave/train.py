#!/usr/bin/env python3
"""Trainer and exporter for weave — numpy Adam, cosine schedule, int8 export.

Tokens are bytes and entity ids from tok.py; a training row is
header + text + <eos>, loss on the text+eos span only. Export quantises
every 2-D tensor to int8 with one scale per row — TINY 2.1's trick, and
the same layout weave.js reads, so the file the browser downloads is
this file's output, nothing else.

Parity contract with weave.js: greedy sampling of a fixed prompt after
training must agree token for token up to a length both sides consider
clean (float32 paths diverge eventually; the check is "no disagreement
in the first 32 tokens", reported, not assumed).

  python3 train.py --corpus weave.jsonl --steps 4000 --tier whisper
"""
import argparse
import json
import math
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "8")
os.environ.setdefault("OMP_NUM_THREADS", "8")

import sys

import numpy as np

from model import GPT
from tok import Tok

HERE = os.path.dirname(os.path.abspath(__file__))
FT = np.float32

TIERS = {
    # whisper: TINY 2.1 territory, ~1.4M params — proves the pipeline.
    "whisper": dict(d=160, n_layer=4, n_head=4),
    # voice: the shipping candidate, ~5M params.
    "voice": dict(d=256, n_layer=6, n_head=8),
}


def load_rows(path, tok, ctx):
    rows = []
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            hdr = tok.header(rec["dom"], [(c[0], c[1], c[2]) for c in rec["cards"]])
            text = tok.encode_text(rec["text"]) + [tok.eos]
            toks = hdr + text
            if len(toks) > ctx:
                continue
            rows.append((toks, len(hdr)))
    return rows


def make_batch(rows, rng, bs, ctx):
    # Length-bucketed windows: rows arrive sorted by length, so a random
    # contiguous slice pads almost nothing — padding is the hidden tax of
    # this whole architecture's T*T tensors, and this halves it.
    s = int(rng.integers(0, max(len(rows) - bs, 1)))
    sel = rows[s:s + bs]
    L = min(max(len(t) for t, _ in sel), ctx) - 1
    X = np.zeros((bs, L), np.int64)
    Y = np.zeros((bs, L), np.int64)
    M = np.zeros((bs, L), FT)
    for b, (t, h) in enumerate(sel):
        t = t[: L + 1]
        n = len(t) - 1
        X[b, :n] = t[:n]
        Y[b, :n] = t[1:n + 1]
        pos = np.arange(1, n + 1)
        M[b, :n] = (pos >= h).astype(FT)
    return X, Y, M


def adam(model):
    state = {k: (np.zeros_like(v), np.zeros_like(v), 0) for k, v in model.p.items()}

    def step_fn(t, lr_t):
        for k, p in model.p.items():
            m, v, _ = state[k]
            g = model.g[k]
            m[:] = 0.9 * m + 0.1 * g
            v[:] = 0.999 * v + 0.001 * g * g
            c = 1 - 0.9 ** t, 1 - 0.999 ** t
            p -= lr_t * (m / c[0]) / (np.sqrt(v / c[1]) + 1e-8)
    return step_fn


def sample(model, tok, hdr_ids, max_new=220, temp=0.0, rng=None):
    ids = list(hdr_ids)
    for _ in range(max_new):
        if len(ids) >= model.ctx:
            break
        x = np.array([ids], np.int64)
        l = model.forward(x)[:, -1, :][0].astype(np.float64)
        l[:9] = -1e30
        l[13:32] = -1e30
        l[127:tok.n_bytes] = -1e30
        l[tok.n_bytes:tok.eos] = -1e30  # specials: only bytes and eos survive
        if temp <= 0:
            nxt = int(np.argmax(l))
        else:
            head = l[: tok.eos + 1] / temp
            p = np.exp(head - head.max())
            p /= p.sum()
            nxt = int(rng.choice(tok.eos + 1, p=p))
        if nxt == tok.eos:
            break
        ids.append(nxt)
    return tok.decode_text(ids[len(hdr_ids):] + [tok.eos])


def quantize_rows(arr):
    a = arr.astype(np.float64)
    scale = np.abs(a).max(axis=1, keepdims=True) / 127.0
    scale = np.maximum(scale, 1e-8)
    q = np.round(a / scale).astype(np.int8)
    return q, scale.astype(np.float32).reshape(-1)


def export(model, tok, cfg, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    order = ["wte", "wpe", "lnfg", "lnfb"]
    for i in range(model.L):
        q = f"{i}."
        order += [q + k for k in ("ln1g", "ln1b", "wqkv", "bqkv", "wo", "bo",
                                  "ln2g", "ln2b", "w1", "b1", "w2", "b2")]
    blobs, entries, off = [], [], 0
    for name in order:
        p = model.p[name]
        if p.ndim == 1:
            b = p.astype(np.float32).tobytes()
            blobs.append(b)
            entries.append(dict(name=name, shape=list(p.shape),
                                dtype="f32", off=off, nbytes=len(b)))
            off += len(b)
        else:
            qq, sc = quantize_rows(p)
            blobs.append(qq.tobytes())
            entries.append(dict(name=name, shape=list(p.shape), dtype="int8row",
                                off=off, nbytes=qq.nbytes, scale=sc.tolist()))
            off += qq.nbytes
    with open(os.path.join(out_dir, "weights.bin"), "wb") as f:
        for b in blobs:
            f.write(b)
    meta = dict(config=dict(d=model.d, n_layer=model.L, n_head=model.H,
                            ctx=model.ctx, tier=cfg.get("tier")),
                tok=tok.meta(), entries=entries)
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f)
    n_params = sum(v.size for v in model.p.values())
    size = os.path.getsize(os.path.join(out_dir, "weights.bin"))
    print(f"export: {n_params/1e6:.2f}M params, weights.bin {size/1e6:.2f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=os.path.join(HERE, "weave.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--tier", default="whisper", choices=list(TIERS))
    ap.add_argument("--ctx", type=int, default=384)
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--lr", type=float, default=6e-4)
    ap.add_argument("--warm", type=int, default=100)
    ap.add_argument("--eval-every", type=int, default=250)
    ap.add_argument("--seed", type=int, default=20261115)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    import corpus as corpus_mod
    deck = corpus_mod.load_deck()
    tok = Tok([c["name"] for c in deck])

    rows = load_rows(a.corpus, tok, a.ctx)
    print(f"{len(rows)} rows fit ctx {a.ctx}")
    # val is a random 400 BEFORE sorting, so sorting by length (for the
    # bucketed batches) cannot decide which hands are held out.
    perm = rng.permutation(len(rows))
    val_rows = [rows[i] for i in perm[:400]]
    train_rows = [rows[i] for i in perm[400:]]
    train_rows.sort(key=lambda r: len(r[0]))
    val_rows.sort(key=lambda r: len(r[0]))

    model = GPT(rng, tok.vocab_size, ctx=a.ctx, **TIERS[a.tier])
    step_fn = adam(model)
    for t in range(1, a.steps + 1):
        lr = a.lr * min(t / a.warm, 1.0) * 0.5 * (
            1 + math.cos(math.pi * (t / a.steps)))
        X, Y, M = make_batch(train_rows, rng, a.bs, a.ctx)
        loss = model.step(X, Y, M)
        gn = np.sqrt(sum(float((g ** 2).sum()) for g in model.g.values()))
        if gn > 1.0:
            for g in model.g.values():
                g *= 1.0 / gn
        step_fn(t, lr)
        if t % a.eval_every == 0 or t == a.steps:
            vx, vy, vm = make_batch(val_rows, rng, 8, a.ctx)
            vl = model.forward(vx, vy, vm)[1]
            ex, eh = train_rows[int(rng.integers(len(train_rows)))]
            line = sample(model, tok, ex[:eh])[:160].replace("\n", " ")
            print(f"step {t:5d}  train {loss:.3f}  val {vl:.3f}  | {line}",
                  flush=True)

    export(model, tok, dict(tier=a.tier), a.out)

    # A greedy parity case, saved for weave.js to check itself against.
    ex, eh = train_rows[0]
    ids = ex[:eh]
    with open(os.path.join(a.out, "parity.json"), "w") as f:
        json.dump(dict(header=ids, greedy=sample(model, tok, ids),
                       text=tok.decode_text(ex[eh:]),
                       config=dict(d=model.d, n_layer=model.L, n_head=model.H,
                                   ctx=a.ctx)), f)
    print("sample:", sample(model, tok, ids)[:160])


if __name__ == "__main__":
    main()
