/* ── weave.js · the small voice ────────────────────────────────────────
   Runs a trained weave model in the browser: no build step, no runtime
   beyond fetch, weights read straight out of train.py's export
   (weights.bin + meta.json, int8 with one scale per row — TINY 2.1's
   layout). The forward pass steps ONE token at a time and caches K/V
   per layer, so the cost per emitted byte is linear in the context and
   the whole file stays readable; no batched GEMM, no attention matrix.

   Classic script, loads after DECK exists, exposes window.ARCANAI_WEAVE:
     .ready                 → true once weights are up
     .boot(urlBase)         → Promise<boolean>; never rejects, resolves
                              false on any failure (offline, 404, old
                              browser) — the page then keeps the template
                              verdict exactly as it does today for attune.
     .reading(deal)         → string | null, SYNCHRONOUS once ready:
        deal = { dom:'love', cards:[{ i:5, seat:'The Situation', rev:false }, …] }
        i is the DECK index — card tokens are deck order by contract,
        the same order tok.py was handed.
     .readingAsync(deal)    → promise resolving to reading() or null,
                              refuses to boot on its own — vecFor's rule:
                              the page never downloads a feature it has
                              not been told to use.

   Generation contract (python and JS enforce the same one):
   greedy; only printable ASCII bytes 32..126 and <eos> may be emitted.
   A special token can never appear in a line because the logit never
   proposes one. Parity with train.py's sample() is "same tokens in
   order until float paths diverge at a near-tie", checked, not assumed.
   ─────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  const W = (window.ARCANAI_WEAVE = {
    ready: false,
    boot: boot,
    reading: reading,
    readingAsync: readingAsync,
    config: { maxNew: 220 },
  });

  let M = null;

  function boot(urlBase) {
    if (M && M.ok) return Promise.resolve(true);
    urlBase = urlBase || 'weave-out/';
    return (async () => {
      const meta = await (await fetch(urlBase + 'meta.json')).json();
      const bin = new Uint8Array(await (await fetch(urlBase + 'weights.bin')).arrayBuffer());
      const P = {};
      for (const e of meta.entries) {
        if (e.dtype === 'f32') {
          // copy, not view: byte offsets from an int8 stream need not be
          // 4-aligned, and one startup copy is cheaper than that bug class
          P[e.name] = new Float32Array(bin.buffer.slice(e.off, e.off + e.nbytes));
        } else {
          const [r, c] = e.shape;
          const src = new Int8Array(bin.buffer, e.off, e.nbytes);
          const out = new Float32Array(r * c);
          for (let j = 0; j < r; j++) {
            const s = e.scale[j];
            const o = j * c;
            for (let k = 0; k < c; k++) out[o + k] = src[o + k] * s;
          }
          P[e.name] = out;
        }
      }
      const tok = meta.tok;
      M = {
        ok: true, meta, P,
        off: {
          cards: 256,
          seats: 256 + tok.cards.length,
          faces: 256 + tok.cards.length + tok.seats.length,
          doms: 256 + tok.cards.length + tok.seats.length + tok.faces.length,
        },
      };
      W.ready = true;
      return true;
    })().catch((e) => {
      console.warn('🔮 weave: unavailable —', e && e.message);
      return false;
    });
  }

  /* ---- one transformer block, one position, K/V cached ------------------ */

  function ln(x, g, b, out) {
    const n = x.length;
    let mu = 0, vr = 0;
    for (let i = 0; i < n; i++) mu += x[i];
    mu /= n;
    for (let i = 0; i < n; i++) { const d = x[i] - mu; vr += d * d; }
    const sd = Math.sqrt(vr / n + 1e-5);
    for (let i = 0; i < n; i++) out[i] = ((x[i] - mu) / sd) * g[i] + b[i];
  }

  const gelu = (x) => 0.5 * x * (1 + Math.tanh(0.7978845608028654 * (x + 0.044715 * x * x * x)));

  function matvec(a, w, rows, cols, out) { /* out[j] = Σ_m a[m]·w[m·cols+j] */
    for (let j = 0; j < cols; j++) {
      let s = 0;
      for (let m = 0; m < rows; m++) s += a[m] * w[m * cols + j];
      out[j] = s;
    }
  }

  function newState(cfg) {
    const st = { kc: [], vc: [], pos: 0 };
    for (let i = 0; i < cfg.n_layer; i++) {
      st.kc.push(new Float32Array(cfg.ctx * cfg.d));
      st.vc.push(new Float32Array(cfg.ctx * cfg.d));
    }
    return st;
  }

  /* Feed one token id at position pos, return logits for the next token. */
  function step(id, st, P, cfg, tmp) {
    const { d, n_layer: L, n_head: H } = cfg;
    const dh = d / H, pos = st.pos;
    const { x1, qkv, ao, ff, x } = tmp;
    for (let j = 0; j < d; j++) x[j] = P.wte[id * d + j] + P.wpe[pos * d + j];

    for (let i = 0; i < L; i++) {
      const p = i + '.';
      ln(x, P[p + 'ln1g'], P[p + 'ln1b'], x1);
      matvec(x1, P[p + 'wqkv'], d, 3 * d, qkv);
      for (let j = 0; j < 3 * d; j++) qkv[j] += P[p + 'bqkv'][j];
      const kc = st.kc[i], vc = st.vc[i];
      for (let j = 0; j < d; j++) { kc[pos * d + j] = qkv[d + j]; vc[pos * d + j] = qkv[2 * d + j]; }
      // attention: q attends to cached k/v rows 0..pos, causal by length alone
      const scale = 1 / Math.sqrt(dh);
      const sc = tmp.sc;
      for (let hh = 0; hh < H; hh++) {
        const b0 = hh * dh;
        let mx = -Infinity;
        for (let t = 0; t <= pos; t++) {
          let s = 0;
          for (let j = 0; j < dh; j++) s += qkv[b0 + j] * kc[t * d + b0 + j];
          sc[t] = s * scale;
          if (sc[t] > mx) mx = sc[t];
        }
        let Z = 0;
        for (let t = 0; t <= pos; t++) { sc[t] = Math.exp(sc[t] - mx); Z += sc[t]; }
        const iZ = 1 / Z;
        for (let j = 0; j < dh; j++) {
          let s = 0;
          for (let t = 0; t <= pos; t++) s += sc[t] * vc[t * d + b0 + j];
          ao[b0 + j] = s * iZ;
        }
      }
      matvec(ao, P[p + 'wo'], d, d, ff);
      for (let j = 0; j < d; j++) x[j] += ff[j] + P[p + 'bo'][j];
      ln(x, P[p + 'ln2g'], P[p + 'ln2b'], x1);
      matvec(x1, P[p + 'w1'], d, 4 * d, qkv.subarray(0, 4 * d));
      for (let j = 0; j < 4 * d; j++) ff[j] = gelu(qkv[j] + P[p + 'b1'][j]);
      matvec(ff, P[p + 'w2'], 4 * d, d, qkv.subarray(0, d));
      for (let j = 0; j < d; j++) x[j] += qkv[j] + P[p + 'b2'][j];
    }
    st.pos += 1;
    ln(x, P.lnfg, P.lnfb, x1);
    matvec(x1, P.wte, d, M.meta.tok.vocab_size, tmp.logits); // tied head
    return tmp.logits;
  }

  function headerIds(deal) {
    const tok = M.meta.tok, o = M.off, out = [];
    out.push(o.doms + tok.domains.indexOf(deal.dom || 'none'));
    for (const c of deal.cards) {
      out.push(o.seats + tok.seats.indexOf(c.seat));
      out.push(o.faces + (c.rev ? 1 : 0));
      out.push(o.cards + c.i);
    }
    out.push(tok.deal_end);
    return out;
  }

  function reading(deal) {
    if (!M || !M.ok) return null;
    const cfg = M.meta.config, tok = M.meta.tok, P = M.P;
    const eos = tok.eos, V = tok.vocab_size;
    const tmp = {
      x: new Float32Array(cfg.d), x1: new Float32Array(cfg.d),
      qkv: new Float32Array(4 * cfg.d), ao: new Float32Array(cfg.d),
      sc: new Float32Array(cfg.ctx), ff: new Float32Array(4 * cfg.d),
      logits: new Float32Array(V),
    };
    const st = newState(cfg);
    const ids = headerIds(deal);
    for (const id of ids) step(id, st, P, cfg, tmp);
    const start = ids.length;
    const cap = Math.min(cfg.ctx - 1, start + W.config.maxNew);
    while (st.pos <= cap) {
      const lg = tmp.logits;
      let best = -Infinity, bi = -1;
      for (let j = 32; j < 127; j++) if (lg[j] > best) { best = lg[j]; bi = j; }
      if (lg[eos] > best || bi < 0) break;
      step(bi, st, P, cfg, tmp);
      ids.push(bi);
    }
    const bytes = new Uint8Array(ids.slice(start));
    try { return new TextDecoder('utf-8', { fatal: false }).decode(bytes); }
    catch (e) { return null; }
  }

  function readingAsync(deal) {
    if (!W.ready) return Promise.resolve(null);
    try { return Promise.resolve(reading(deal)); } catch (e) { return Promise.resolve(null); }
  }
})();
