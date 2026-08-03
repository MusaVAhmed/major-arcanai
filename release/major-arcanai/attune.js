/* ── attune.js · the semantic heresy ─────────────────────────────────
   In-browser sentence embeddings (transformers.js + all-MiniLM-L6-v2,
   ~23 MB quantized, cached by the browser after first load) so the
   question tilts the deck by MEANING instead of keyword lists.

   Three things come out of one question embedding:
     which cards   cosine against each card's two faces, softmaxed
     which face    whichever of upright / reversed matches better
     which seat    cosine against each spread position's description

   A fourth, free: what KIND of question it is, by cosine against a handful
   of anchor descriptions. That one changes nothing about the deal.

   Classic script, no build step. Loads after the inline DECK exists.
   Exposes window.ARCANAI_ATTUNE:
     .ready        → true once card vectors are computed
     .readFor(q, mode, timeoutMs) → Promise<{w, rev, pos, su, sr, v, dom, stats} | null>
     .weightsFor(q, timeoutMs)    → Promise<Float64Array(40) | null>
     .vecFor(q, timeoutMs)        → Promise<Float32Array(384) | null>
     .domainOf(vec)               → {k, top, gap, all} | null   (synchronous)
     .domainFor(q, timeoutMs)     → Promise<same | null>
     .resonanceOf(idxs, revs, qv) → how the dealt cards relate (synchronous)
     .bg           → the background cosine distribution they are scored against
     .config       → { temp, strength } tuning knobs

   Failure of any kind (offline, old browser, CDN down) resolves to
   null and the page falls back to the keyword THEME_HINTS shuffle.
   ──────────────────────────────────────────────────────────────────── */
(() => {
  const MODEL = 'Xenova/all-MiniLM-L6-v2';
  const CDN = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.3.3/dist/transformers.min.js';
  /* v3 adds the background cosine distribution to the cached blob. */
  const LS_KEY = 'arcanai-cardvecs-v3';

  /* What each seat in a spread is asking of the card that lands there.
     Matching prose, not labels: "The Outcome" alone is too thin a string
     to sit anywhere useful in the embedding space.

     This used to live here. It now lives in seats.js, because the renderer
     needs the same seats to print a lens in front of the card copy and two
     copies of the truth is one copy too many. The pairs handed back are
     byte-identical to what was here, so corpusSig is unchanged and no cached
     vector rebuilds on account of the move. */
  const POSITIONS = (window.ARCANAI_SEATS || {}).matching || null;

  /* What kind of question this is. A SEPARATE corpus from the cards — never
     folded into upText/revText — so adding, cutting or rewording an anchor
     cannot dilute a card's vector or move it in the rankings. The dilution
     rule that governs the situational expansions does not apply here, and
     these deliberately run longer than 20 words for that reason: an anchor
     wants breadth, a card wants a well-aimed point. Measured, not assumed:
     a deliberately terse set scored 67% against this one's 89%.

     Only the prose is embedded; the key is a label for our side of it. A
     bare word like "loss" sits somewhere unhelpfully literal in the space
     and would drag the anchor toward questions that use the word rather
     than questions that are about the thing.

     Every anchor must name a SUBJECT, never a disposition. The first draft
     had `nerve` — "whether to do the frightening thing" — and it quietly
     robbed all five of the others, because wanting to tell someone how you
     feel is a love question asked by a frightened person, and telling your
     mother no is a family question asked by the same. It took the argmax on
     both. Replacing it with `change`, which is a thing a question can be
     about rather than a mood a question can be in, moved the set from 59%
     to 89%. If a seventh anchor is ever added, it has to pass that test. */
  const ANCHORS = [
    ['work',   'My job, my boss, my career. Pay, overwork, whether to quit or stay put.'],
    ['love',   'Someone I love or want. My partner, dating, whether they want me back, whether to leave them.'],
    ['kin',    'My family and my friends. My mother, my father, my sister, my brother. Saying no to them, what I owe them.'],
    ['loss',   'Someone is gone or something ended. Grief, mourning, missing them, the thing I cannot undo.'],
    ['change', 'A change I am weighing. Moving, starting over, going back, beginning something I have not begun.'],
    ['self',   'Who I am and how I am doing. Feeling stuck, feeling lost, tired of myself, my own patterns.'],
  ];

  const A = (window.ARCANAI_ATTUNE = {
    ready: false,
    config: {
      /* softmax temperature over cosine sims; lower = peakier tilt.
         Measured on-device (400 five-card draws per question): at 0.06 a
         bullseye question put one card in 92% of draws, which reads as
         stacked rather than attentive. The page drives this from the Back
         Room's lean control and is authoritative over this default. */
      temp: 0.15,
      strength: 2.5,  // matches the keyword shuffle's 2.5x flavor of "leaning in"
      /* Seats need a colder temperature than selection: affinities between the
         few cards actually drawn sit close together, and at the selection temp
         the seating measured a 9% affinity lift, i.e. it did nothing. */
      seatRatio: 0.34,
      /* Dead zone on the orientation decision. At 0 the better matching face
         wins outright, which is the shipped behaviour and pulls the attuned
         reversal rate to roughly a third. Raise it to hand near-ties back to
         the seeded coin: about 0.04 restores a 50/50 deck. */
      faceMargin: 0,
      /* How much daylight the leading anchor needs over the runner-up before
         the deck will claim to know what it is being asked about. With six
         anchors something always wins, and winning by a hair is not knowing.

         Measured over 27 questions: 0.02 claims 81% of them at 95% precision,
         0.04 claims 74% at 95%, 0.06 claims 67% at 94%, 0.09 claims 63% at
         100%. The knee is soft, so this sits where coverage is still most of
         the deck and a wrong claim is rare. Those 27 were written here rather
         than typed by a seeker, so treat this as a sanity check and not a
         calibration — `dom`, `lead` and `domGap` are logged on every draw for
         the same reason the tell thresholds are. */
      domMin: 0.06,
    },
    lastStats: null,  // {max, mean, lift, revShare} of the last question, for tuning
    lastDom: null,    // the last domain call, same
    readFor,
    weightsFor,
    vecFor,
    domainOf,
    domainFor,
    resonanceOf,
    get bg() { return bg; },
  });

  if (typeof DECK === 'undefined') {
    console.warn('🔮 attune: DECK not found; load attune.js after the deck script.');
    return;
  }
  /* Seats are optional. Without them the deck still chooses the cards and
     their faces; it just deals them left to right like an ordinary shuffle,
     which is what it did before seating existed. */
  if (!POSITIONS) {
    console.warn('🔮 attune: seats.js not found; seating disabled, selection unaffected.');
  }

  /* Each face of each card is its own document. `sit` and `sitr` are optional
     situational expansions: the everyday circumstances a card answers to,
     which pull terse abstract copy ("Break free from unhealthy cycles") into
     the same neighbourhood as the concrete things people actually ask. */
  const upText = DECK.map((c) => `${c.name}. ${c.meaning}${c.sit ? ' ' + c.sit : ''}`);
  const revText = DECK.map((c) => `${c.name}, reversed. ${c.r || ''}${c.sitr ? ' ' + c.sitr : ''}`);
  const posModes = POSITIONS ? Object.keys(POSITIONS) : [];
  const posText = posModes.map((m) => POSITIONS[m].map((p) => `${p[0]}. ${p[1]}`));
  const ancText = ANCHORS.map((a) => a[1]);

  const corpusSig = (() => {
    // cheap stable hash so cached vectors invalidate when the deck changes
    let h = 0;
    const s = MODEL + ' ' + upText.join(' ') + ' ' + revText.join(' ') +
      '\u0000' + posText.join('\u0000') + '\u0000' + ancText.join('\u0000');
    for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
    return (h >>> 0).toString(36);
  })();

  let embedFn = null;        // (texts) => Promise<vectors>
  let vUp = null, vRev = null, vAnc = null, bg = null;
  const vPos = {};           // mode -> Array<Float32Array>
  const qCache = new Map();  // normalized question -> Float32Array
  let bootPromise = null;

  const norm = (q) => q.trim().toLowerCase().replace(/\s+/g, ' ');
  const pack = (vs) => vs.map((v) => Array.from(v, (x) => Math.round(x * 1e5) / 1e5));
  const unpack = (a) => a.map((v) => Float32Array.from(v));

  async function boot() {
    if (bootPromise) return bootPromise;
    bootPromise = (async () => {
      const { pipeline, env } = await import(CDN);
      env.allowLocalModels = false;
      const extractor = await pipeline('feature-extraction', MODEL, { dtype: 'q8' });
      embedFn = async (texts) => {
        const out = await extractor(texts, { pooling: 'mean', normalize: true });
        const [n, d] = out.dims;
        const data = out.data;
        const vecs = [];
        for (let i = 0; i < n; i++) vecs.push(data.slice(i * d, (i + 1) * d));
        return vecs;
      };

      let cached = null;
      try {
        cached = JSON.parse(localStorage.getItem(LS_KEY) || 'null');
      } catch (_) {}
      /* Bumping LS_KEY orphans the previous blob: ~320 KB of dead weight in a
         5 MB origin budget, on every device that ever loaded the old version,
         forever. Sweep our own leavings — nobody else's. */
      try {
        for (let i = localStorage.length - 1; i >= 0; i--) {
          const k = localStorage.key(i);
          if (k && k.indexOf('arcanai-cardvecs-') === 0 && k !== LS_KEY) localStorage.removeItem(k);
        }
      } catch (_) {}
      if (cached && cached.sig === corpusSig) {
        vUp = unpack(cached.up);
        vRev = unpack(cached.rev);
        vAnc = unpack(cached.anc);
        posModes.forEach((m) => { vPos[m] = unpack(cached.pos[m]); });
        bg = cached.bg || null;
      } else {
        vUp = await embedFn(upText);
        vRev = await embedFn(revText);
        vAnc = await embedFn(ancText);
        for (let i = 0; i < posModes.length; i++) vPos[posModes[i]] = await embedFn(posText[i]);
        bg = backgroundStats();
        try {
          const pos = {};
          posModes.forEach((m) => { pos[m] = pack(vPos[m]); });
          localStorage.setItem(LS_KEY, JSON.stringify(
            { sig: corpusSig, up: pack(vUp), rev: pack(vRev), anc: pack(vAnc), pos, bg }));
        } catch (_) {}
      }
      if (!bg) bg = backgroundStats();   // a v3 blob written before this line existed
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

  /* The null distribution for "how alike are two card faces you might be
     dealt together". Raw cosines between these documents sit in a narrow band
     high up the scale — every card is short second-person life advice, so
     nothing here is ever really far from anything — which makes an absolute
     threshold meaningless and a z-score against this the only honest way to
     say two cards agree. Computed once when the vectors are built, cached
     beside them, ~3k dot products.

     The population is deliberately the one a spread samples from: every pair
     of faces belonging to DIFFERENT cards. A card's upright and reversed
     sides are each other's nearest neighbours by a mile and can never be
     dealt together, so including them would inflate the mean and flatten
     every z-score the deck ever reports. */
  function backgroundStats() {
    if (!vUp || !vRev) return null;
    const faces = [];
    for (let i = 0; i < vUp.length; i++) { faces.push([i, vUp[i]]); faces.push([i, vRev[i]]); }
    let sum = 0, sum2 = 0, k = 0, min = 1, max = -1;
    for (let a = 0; a < faces.length; a++) {
      for (let b = a + 1; b < faces.length; b++) {
        if (faces[a][0] === faces[b][0]) continue;
        const c = dot(faces[a][1], faces[b][1]);
        sum += c; sum2 += c * c; k++;
        if (c < min) min = c;
        if (c > max) max = c;
      }
    }
    if (!k) return null;
    const mean = sum / k;
    return {
      mean: +mean.toFixed(5),
      sd: +Math.sqrt(Math.max(1e-12, sum2 / k - mean * mean)).toFixed(5),
      n: k, min: +min.toFixed(4), max: +max.toFixed(4),
    };
  }

  /* How the cards actually dealt relate to EACH OTHER, which the deck has
     never before had an opinion about: the old verdict counted theme tags and
     needed three of one tag to say anything, so a three-card draw almost never
     spoke and when it did it said the same sentence forever.

     `idxs` are DECK indices in seat order, `revs` their showing faces, `qv`
     the question vector if there is one. Every index in the RESULT — i, j,
     loudest, quietest — is a position in that drawn array, not a deck index,
     because callers want the seat and the label, not the card number.

     Returns null rather than guessing when the vectors are not up. */
  function resonanceOf(idxs, revs, qv) {
    if (!A.ready || !vUp || !bg || !idxs || !idxs.length) return null;
    const n = idxs.length;
    const face = idxs.map((ci, k) => (revs[k] ? vRev[ci] : vUp[ci]));
    if (face.some((f) => !f)) return null;
    const z = (c) => (c - bg.mean) / bg.sd;

    const pairs = [];
    let strongest = null, tensest = null, zsum = 0;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const p = { i, j, cos: +dot(face[i], face[j]).toFixed(4) };
        p.z = +z(p.cos).toFixed(2);
        zsum += p.z;
        pairs.push(p);
        if (!strongest || p.z > strongest.z) strongest = p;
        if (!tensest || p.z < tensest.z) tensest = p;
      }
    }

    /* Loudest is the card that answers the question best, quietest the one
       that does not fit — the odd card out is usually the interesting one. */
    let loudest = null, quietest = null, qsims = null;
    if (qv) {
      qsims = face.map((fv) => dot(qv, fv));
      qsims.forEach((s, k) => {
        if (loudest === null || s > qsims[loudest]) loudest = k;
        if (quietest === null || s < qsims[quietest]) quietest = k;
      });
    }

    return {
      pairs, strongest, tensest, loudest, quietest,
      qsims: qsims ? qsims.map((s) => +s.toFixed(4)) : null,
      /* mean pair z: how much this spread agrees with itself overall */
      cohesion: pairs.length ? +(zsum / pairs.length).toFixed(2) : null,
      revShare: +(revs.filter(Boolean).length / n).toFixed(2),
      bg,
    };
  }

  /* What the question is ABOUT, which is a different question from what the
     deck should say about it. Synchronous and free once a vector exists: six
     dot products against vectors already in memory. Nothing here touches the
     deal — it exists so the rest of the page can know what it is looking at.

     Returns k=null rather than a shrug when no anchor leads by enough. With
     six anchors something always wins, and a deck that always has an opinion
     about your category is a horoscope. `lead` keeps the winner anyway, so
     the log can show what would have been claimed at a lower threshold. */
  function domainOf(v) {
    if (!v || !vAnc) return null;
    const s = vAnc.map((av) => dot(v, av));
    const rank = s.map((x, i) => [x, i]).sort((a, b) => b[0] - a[0]);
    const gap = rank[0][0] - rank[1][0];
    const all = {};
    ANCHORS.forEach((a, i) => { all[a[0]] = +s[i].toFixed(3); });
    return (A.lastDom = {
      k: gap >= (A.config.domMin || 0) ? ANCHORS[rank[0][1]][0] : null,
      lead: ANCHORS[rank[0][1]][0],
      top: +rank[0][0].toFixed(3),
      gap: +gap.toFixed(3),
      all,
    });
  }

  /* Like vecFor, this refuses to boot the model on its own: a page with
     attunement switched off never pays 23 MB to categorise a sentence. */
  async function domainFor(q, timeoutMs = 400) {
    const v = await vecFor(q, timeoutMs);
    return v ? domainOf(v) : null;
  }

  /* The whole reading in one pass: weights, orientations, seat affinities.
     Resolves to null if the model is not ready within timeoutMs. */
  async function readFor(q, mode, timeoutMs = 400) {
    if (!q || !q.trim()) return null;
    try {
      const v = await Promise.race([
        embedQuestion(q),
        new Promise((res) => setTimeout(() => res(null), timeoutMs)),
      ]);
      if (!v || !vUp) return null;

      const su = vUp.map((cv) => dot(v, cv));
      const sr = vRev.map((cv) => dot(v, cv));
      // a card is relevant if EITHER of its faces speaks to the question
      const sims = su.map((s, i) => Math.max(s, sr[i]));
      // 1 reversed, 0 upright, -1 too close to call (the page flips its coin)
      const m = A.config.faceMargin || 0;
      const rev = su.map((s, i) =>
        (sr[i] - s > m ? 1 : s - sr[i] > m ? 0 : -1));

      const mx = Math.max(...sims);
      const mean = sims.reduce((a, b) => a + b, 0) / sims.length;
      A.lastStats = {
        max: +mx.toFixed(3), mean: +mean.toFixed(3), lift: +(mx - mean).toFixed(3),
        revShare: +(rev.filter((r) => r === 1).length / rev.length).toFixed(2),
      };

      // seat affinity uses the face that will actually be showing
      const faces = vUp.map((cv, i) => (rev[i] === 1 ? vRev[i] : cv));
      const pos = (vPos[mode] || []).map((pv) => faces.map((cv) => dot(pv, cv)));

      /* su/sr ride along: the face decision is only legible with both sides
         visible. `v` rides along so the caller can score the cards it ends up
         dealing against the same question without a second await — the vector
         is already in hand and resonanceOf is synchronous. */
      return { w: simsToWeights(sims), rev, pos, su, sr, v, dom: domainOf(v), stats: A.lastStats };
    } catch (_) {
      return null;
    }
  }

  /* The question's own vector, for callers comparing questions to each other
     rather than to cards. Free once readFor has run: qCache already holds it.
     Deliberately refuses to boot the model on its own, so a page with
     attunement switched off never pays 23 MB for a side feature. */
  async function vecFor(q, timeoutMs = 400) {
    if (!q || !q.trim() || !A.ready) return null;
    try {
      const v = await Promise.race([
        embedQuestion(q),
        new Promise((res) => setTimeout(() => res(null), timeoutMs)),
      ]);
      return v || null;
    } catch (_) {
      return null;
    }
  }

  /* Weights only. Kept for callers that do not need a whole reading. */
  async function weightsFor(q, timeoutMs = 400) {
    const r = await readFor(q, 0, timeoutMs);
    return r ? r.w : null;
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
