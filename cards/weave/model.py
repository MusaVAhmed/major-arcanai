"""A tiny GPT in NumPy with a hand-derived backward — zero heavy deps.

The whole project's pipeline ethos is TINY 2.1's: a transformer you could
read on a printout. One shared definition is used by training and by the
JS runtime, so parity is one gradient check and one greedy-token test,
not two frameworks agreeing by luck:

  post-LN mini-GPT, learned position embeddings, tied input/output
  embeddings, GELU with the tanh approximation — the JS side implements
  the SAME formula, since exact erf is not free there.

Loss is masked next-token cross-entropy: header positions carry mask 0,
text and <eos> carry mask 1, padding carries mask 0 with a 0x00 byte, so
a padding slot never asks the model to predict anything.

Run this file directly for the gradient check:  python3 model.py
"""
import numpy as np

FT = np.float32
EPS = 1e-5
GELU_C = FT(np.sqrt(2.0 / np.pi))
GELU_P = FT(0.044715)


def gelu(x):
    u = np.tanh(GELU_C * (x + GELU_P * x * x * x))
    return (FT(0.5) * x * (FT(1.0) + u)), u


def gelu_bwd(x, u, dy):
    c3 = GELU_C * (FT(1.0) + FT(3.0) * GELU_P * x * x)
    return dy * (FT(0.5) * (FT(1.0) + u) + FT(0.5) * x * (FT(1.0) - u * u) * c3)


class GPT:
    def __init__(self, rng, vocab_size, d=128, n_layer=3, n_head=4, ctx=384):
        self.d, self.L, self.H, self.ctx = d, n_layer, n_head, ctx
        self.V = vocab_size
        self.p = {}
        s = 0.02
        self.p["wte"] = rng.normal(0, 0.05, (vocab_size, d)).astype(FT)
        self.p["wpe"] = rng.normal(0, 0.01, (ctx, d)).astype(FT)
        scale = np.sqrt(2.0 * n_layer)
        for i in range(n_layer):
            q = f"{i}."
            init = {
                "ln1g": np.ones(d), "ln1b": np.zeros(d),
                "ln2g": np.ones(d), "ln2b": np.zeros(d),
                "bqkv": np.zeros(3 * d), "bo": np.zeros(d),
                "b1": np.zeros(4 * d), "b2": np.zeros(d),
                "wqkv": rng.normal(0, s, (d, 3 * d)),
                "wo": rng.normal(0, s / scale, (d, d)),
                "w1": rng.normal(0, s, (d, 4 * d)),
                "w2": rng.normal(0, s / scale, (4 * d, d)),
            }
            for k, v in init.items():
                self.p[q + k] = v.astype(FT)
        self.p["lnfg"] = np.ones(d, dtype=FT)
        self.p["lnfb"] = np.zeros(d, dtype=FT)
        self.g = {k: np.zeros_like(v) for k, v in self.p.items()}
        self.ca = {}

    # ---- layer norm -------------------------------------------------------
    def _ln(self, x, g, b, tag):
        mu = x.mean(-1, keepdims=True)
        sd = np.sqrt(x.var(-1, keepdims=True) + EPS)
        xh = (x - mu) / sd
        self.ca[tag] = (xh, g, sd)
        return xh * g + b

    def _ln_bwd(self, dy, tag, gkey, bkey):
        xh, g, sd = self.ca[tag]
        flat = lambda a: a.reshape(-1, a.shape[-1])
        self.g[gkey] += (flat(dy) * flat(xh)).sum(0).astype(FT)
        self.g[bkey] += flat(dy).sum(0).astype(FT)
        gd = dy * g
        dxh = (gd - gd.mean(-1, keepdims=True)
               - xh * (gd * xh).mean(-1, keepdims=True)) / sd
        return dxh

    # ---- forward -----------------------------------------------------------
    def forward(self, X, Y=None, mask=None):
        ca = self.ca
        ca.clear()
        B, T = X.shape
        d, H, L, dh_ = self.d, self.H, self.L, self.d // self.H
        ca["X"], ca["T"] = X, T
        h = self.p["wte"][X] + self.p["wpe"][:T]
        causal = np.triu(np.ones((T, T), dtype=bool), 1)

        for i in range(L):
            q = f"{i}."
            x_in = h
            x1 = self._ln(h, self.p[q + "ln1g"], self.p[q + "ln1b"], q + "ln1")
            qkv = x1 @ self.p[q + "wqkv"] + self.p[q + "bqkv"]
            hs = lambda a: a.reshape(B, T, H, dh_).transpose(0, 2, 1, 3)
            k_, v_ = hs(qkv[..., d:2 * d]), hs(qkv[..., 2 * d:])
            att = hs(qkv[..., :d]) @ k_.transpose(0, 1, 3, 2) / FT(np.sqrt(dh_))
            att = np.where(causal, FT(-1e30), att)
            att -= att.max(-1, keepdims=True)
            e = np.exp(att)
            P = e / e.sum(-1, keepdims=True)
            ao = (P @ v_).transpose(0, 2, 1, 3).reshape(B, T, d)
            ca[q + "x1"], ca[q + "qkv"], ca[q + "P"], ca[q + "v"], ca[q + "ao"] = \
                x1, qkv, P, v_, ao
            h_mid = x_in + ao @ self.p[q + "wo"] + self.p[q + "bo"]
            x2 = self._ln(h_mid, self.p[q + "ln2g"], self.p[q + "ln2b"], q + "ln2")
            a1 = x2 @ self.p[q + "w1"] + self.p[q + "b1"]
            gg, u1 = gelu(a1)
            ca[q + "x2"], ca[q + "a1"], ca[q + "u1"], ca[q + "gg"] = x2, a1, u1, gg
            h = h_mid + gg @ self.p[q + "w2"] + self.p[q + "b2"]

        hn = self._ln(h, self.p["lnfg"], self.p["lnfb"], "lnf")
        logits = hn @ self.p["wte"].T
        if Y is None:
            return logits
        ca["hn"] = hn
        mx = logits.max(-1, keepdims=True)
        ex = np.exp(logits - mx)
        probs = ca["probs"] = ex / ex.sum(-1, keepdims=True)
        ce = -np.log(np.take_along_axis(probs, Y[..., None], -1)[..., 0] + 1e-12)
        m = (np.ones_like(Y) if mask is None else mask).astype(FT)
        ca["Y"], ca["mask"] = Y, m
        return logits, float((ce * m).sum() / max(float(m.sum()), 1.0))

    # ---- backward -----------------------------------------------------------
    def backward(self):
        ca, g = self.ca, self.g
        for v in g.values():
            v[...] = 0
        B, T = ca["mask"].shape
        d, H, L, dh_ = self.d, self.H, self.L, self.d // self.H
        probs, Y, m = ca["probs"], ca["Y"], ca["mask"]
        n = max(float(m.sum()), 1.0)

        dlog = ((probs - np.eye(self.V, dtype=FT)[Y]) * (m / n)[..., None]).astype(FT)
        hn2 = ca["hn"].reshape(-1, d)
        g["wte"] += dlog.reshape(-1, self.V).T @ hn2
        dh = (dlog @ self.p["wte"]).reshape(B, T, d)
        dh = self._ln_bwd(dh, "lnf", "lnfg", "lnfb")

        for i in range(L - 1, -1, -1):
            q = f"{i}."
            x2, a1, u1, gg = ca[q + "x2"], ca[q + "a1"], ca[q + "u1"], ca[q + "gg"]
            g[q + "w2"] += (gg.reshape(-1, 4 * d).T @ dh.reshape(-1, d)).astype(FT)
            g[q + "b2"] += dh.reshape(-1, d).sum(0)
            da1 = gelu_bwd(a1, u1, dh @ self.p[q + "w2"].T)
            g[q + "w1"] += (x2.reshape(-1, d).T @ da1.reshape(-1, 4 * d)).astype(FT)
            g[q + "b1"] += da1.reshape(-1, 4 * d).sum(0)
            dln2 = self._ln_bwd(da1 @ self.p[q + "w1"].T, q + "ln2",
                                q + "ln2g", q + "ln2b")
            dh = dh + dln2  # residual into h_mid

            ao = ca[q + "ao"]
            g[q + "wo"] += (ao.reshape(-1, d).T @ dh.reshape(-1, d)).astype(FT)
            g[q + "bo"] += dh.reshape(-1, d).sum(0)
            dao = (dh @ self.p[q + "wo"].T).reshape(B, T, H, dh_).transpose(0, 2, 1, 3)
            P, v_ = ca[q + "P"], ca[q + "v"]
            hs = lambda a: a.reshape(B, T, H, dh_).transpose(0, 2, 1, 3)
            qkv = ca[q + "qkv"]
            k_, qq = hs(qkv[..., d:2 * d]), hs(qkv[..., :d])
            dP = dao @ v_.transpose(0, 1, 3, 2)
            dpre = P * (dP - (P * dP).sum(-1, keepdims=True)) / FT(np.sqrt(dh_))
            dq, dk, dv = dpre @ k_, dpre.transpose(0, 1, 3, 2) @ qq, \
                P.transpose(0, 1, 3, 2) @ dao
            us = lambda a: a.transpose(0, 2, 1, 3).reshape(B, T, d)
            dqkv = np.concatenate([us(dq), us(dk), us(dv)], -1)
            x1h = self.ca[q + "ln1"][0]
            g[q + "wqkv"] += (x1h.reshape(-1, d).T @ dqkv.reshape(-1, 3 * d)).astype(FT)
            g[q + "bqkv"] += dqkv.reshape(-1, 3 * d).sum(0)
            dln1 = self._ln_bwd(dqkv @ self.p[q + "wqkv"].T, q + "ln1",
                                q + "ln1g", q + "ln1b")
            dh = dh + dln1  # residual into layer input

        g["wpe"][:T] += dh.sum(0).astype(FT)
        np.add.at(g["wte"], ca["X"].reshape(-1), dh.reshape(-1, d))

    # ---- one training step ---------------------------------------------------
    def step(self, X, Y, mask):
        _, loss = self.forward(X, Y, mask)
        self.backward()
        return loss


# ---- gradient check ------------------------------------------------------
def _gradcheck(d=16, L=2, H=2, V=40, T=12, n_checked=80, seed=0, tol=1e-4):
    # float64 everywhere: a float32 finite-difference probe on a loss around
    # log(V) drowns in its own rounding, and three of these probes would be
    # noise against a genuine 1e-5 agreement.
    import sys
    gmod = sys.modules[__name__]
    gmod.FT = np.float64
    gmod.GELU_C = np.sqrt(2.0 / np.pi)
    gmod.GELU_P = 0.044715
    rng = np.random.default_rng(seed)
    model = gmod.GPT(rng, V, d=d, n_layer=L, n_head=H, ctx=T)
    model.p = {k: v.astype(np.float64) for k, v in model.p.items()}
    model.g = {k: np.zeros_like(v) for k, v in model.p.items()}
    X = rng.integers(0, V, (2, T)).astype(np.int64)
    Y = rng.integers(0, V, (2, T)).astype(np.int64)
    Mmask = (rng.random((2, T)) > 0.3).astype(np.float64)
    Mmask[:, 0] = 1

    def loss_fn():
        return model.step(X, Y, Mmask)

    model.step(X, Y, Mmask)
    worst = 0.0
    flat_names = list(model.p.keys())
    rngf = np.random.default_rng(1)
    for name in flat_names:
        if name.endswith("g") and name.startswith("ln"):
            continue
        arr = model.p[name]
        idxs = rngf.choice(arr.size, min(3, arr.size), replace=False)
        for fi in idxs:
            fi = int(fi)
            old = arr.reshape(-1)[fi]
            e = 1e-5
            arr.reshape(-1)[fi] = old + e
            lp = loss_fn()
            arr.reshape(-1)[fi] = old - e
            lm = loss_fn()
            arr.reshape(-1)[fi] = old
            model.step(X, Y, Mmask)
            num = (lp - lm) / (2 * e)
            ana = model.g[name].reshape(-1)[fi]
            denom = max(abs(num), abs(ana), 1e-2)
            err = abs(num - ana) / denom
            worst = max(worst, err)
            n_checked -= 1
            if err > tol:
                print(f"FAIL {name}[{fi}]: num {num:.6g} vs ana {ana:.6g}")
                return False
            if n_checked <= 0:
                break
    print(f"gradcheck: worst rel err {worst:.2e} over probes — {'OK' if worst < tol else 'FAIL'}")
    return worst < tol


if __name__ == "__main__":
    import sys
    sys.exit(0 if _gradcheck() else 1)
