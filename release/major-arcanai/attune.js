/* ── attune.js · the semantic heresy ─────────────────────────────────
   In-browser sentence embeddings (transformers.js + all-MiniLM-L6-v2,
   ~23 MB quantized, cached by the browser after first load) so the
   question tilts the deck by MEANING instead of keyword lists.

   Classic script, no build step. Loads after the inline DECK exists.
   Exposes window.ARCANAI_ATTUNE:
     .ready        → true once card vectors are computed
     .weightsFor(q, timeoutMs) → Promise<Float64Array(40) | null>
     .config       → { temp, strength } tuning knobs

   Failure of any kind (offline, old browser, CDN down) resolves to
   null and the page falls back to the keyword THEME_HINTS shuffle.
   ──────────────────────────────────────────────────────────────────── */
(() => {
  const MODEL = 'Xenova/all-MiniLM-L6-v2';
  const CDN = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.3.3/dist/transformers.min.js';
  const LS_KEY = 'arcanai-cardvecs-v1';

  const A = (window.ARCANAI_ATTUNE = {
    ready: false,
    config: {
      /* softmax temperature over cosine sims; lower = peakier tilt.
         Measured on-device (400 five-card draws per question): at 0.06 a
         bullseye question put one card in 92% of draws, which reads as
         stacked rather than attentive. 0.15 lands topical questions at
         roughly 2-3x their baseline rate, matching the keyword shuffle. */
      temp: 0.15,
      strength: 2.5,  // matches the keyword shuffle's 2.5x flavor of "leaning in"
    },
    lastStats: null,  // {max, mean, lift} of the last question's sims, for tuning
    weightsFor,
  });

  if (typeof DECK === 'undefined') {
    console.warn('🔮 attune: DECK not found; load attune.js after the deck script.');
    return;
  }

  // What each card "is", for the embedding space: name + upright + reversed.
  const corpus = DECK.map(
    (c) => `${c.name}. ${c.meaning} Reversed: ${c.r || ''}`
  );
  const corpusSig = (() => {
    // cheap stable hash so cached vectors invalidate when the deck changes
    let h = 0;
    const s = MODEL + '\u0000' + corpus.join('\u0000');
    for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
    return (h >>> 0).toString(36);
  })();

  let embedFn = null;        // (texts) => Promise<vectors>
  let cardVecs = null;       // Array<Float32Array> once ready
  const qCache = new Map();  // normalized question -> Float32Array
  let bootPromise = null;

  const norm = (q) => q.trim().toLowerCase().replace(/\s+/g, ' ');

  async function boot() {
    if (bootPromise) return bootPromise;
    bootPromise = (async () => {
      const { pipeline, env } = await import(CDN);
      env.allowLocalModels = false;
      const extractor = await pipeline('feature-extraction', MODEL, { dtype: 'q8' });
      embedFn = async (texts) => {
        const out = await extractor(texts, { pooling: 'mean', normalize: true });
        // out.dims = [n, 384]; slice into per-text vectors
        const [n, d] = out.dims;
        const data = out.data;
        const vecs = [];
        for (let i = 0; i < n; i++) vecs.push(data.slice(i * d, (i + 1) * d));
        return vecs;
      };

      // Card vectors: localStorage cache first, else compute (~40 embeds, <1s)
      try {
        const cached = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
        if (cached && cached.sig === corpusSig) {
          cardVecs = cached.v.map((a) => Float32Array.from(a));
        }
      } catch (_) {}
      if (!cardVecs) {
        cardVecs = await embedFn(corpus);
        try {
          localStorage.setItem(LS_KEY, JSON.stringify({
            sig: corpusSig,
            v: cardVecs.map((v) => Array.from(v, (x) => Math.round(x * 1e5) / 1e5)),
          }));
        } catch (_) {}
      }
      A.ready = true;
      console.log('🔮 attune: semantic shuffle armed (' + MODEL + ')');
    })().catch((e) => {
      console.warn('🔮 attune: unavailable, keyword shuffle remains —', e && e.message);
      bootPromise = null;   // allow a retry on next call
      throw e;
    });
    return bootPromise;
  }

  async function embedQuestion(q) {
    const key = norm(q);
    if (qCache.has(key)) return qCache.get(key);
    await boot();
    const [v] = await embedFn([key]);
    qCache.set(key, v);
    if (qCache.size > 40) qCache.delete(qCache.keys().next().value);
    return v;
  }

  /* cosine of normalized vectors = dot product */
  const dot = (a, b) => {
    let s = 0;
    for (let i = 0; i < a.length; i++) s += a[i] * b[i];
    return s;
  };

  function simsToWeights(sims) {
    const { temp, strength } = A.config;
    const mx = Math.max(...sims);
    const exps = sims.map((s) => Math.exp((s - mx) / temp));
    const Z = exps.reduce((a, b) => a + b, 0);
    // p sums to 1; scale so a flat distribution would add ~0 tilt and a
    // peaked one boosts its favorites by up to `strength`, echoing the
    // keyword shuffle's weighting scale.
    return Float64Array.from(exps, (e) => 1 + strength * ((e / Z) * sims.length - 1) * 0.5)
      .map((w) => Math.min(8, Math.max(0.25, w)));
  }

  /* Resolve to per-card weights, or null if not ready within timeoutMs. */
  async function weightsFor(q, timeoutMs = 400) {
    if (!q || !q.trim()) return null;
    try {
      const v = await Promise.race([
        embedQuestion(q),
        new Promise((res) => setTimeout(() => res(null), timeoutMs)),
      ]);
      if (!v || !cardVecs) return null;
      const sims = cardVecs.map((cv) => dot(v, cv));
      const mx = Math.max(...sims);
      const mean = sims.reduce((a, b) => a + b, 0) / sims.length;
      A.lastStats = { max: +mx.toFixed(3), mean: +mean.toFixed(3), lift: +(mx - mean).toFixed(3) };
      return simsToWeights(sims);
    } catch (_) {
      return null;
    }
  }

  /* Warm-up: start the model download quietly, and pre-embed the question
     as the seeker types so the vector is ready before they hit draw. */
  const qEl = document.getElementById('q');
  let debounce = 0;
  const warm = () => boot().catch(() => {});
  if (qEl) {
    qEl.addEventListener('focus', warm, { once: true });
    qEl.addEventListener('input', () => {
      clearTimeout(debounce);
      const q = qEl.value;
      if (!q.trim()) return;
      debounce = setTimeout(() => embedQuestion(q).catch(() => {}), 300);
    });
  }
  // Also warm on idle so first draw of the night isn't the cold one.
  (window.requestIdleCallback || ((f) => setTimeout(f, 2500)))(warm);
})();
