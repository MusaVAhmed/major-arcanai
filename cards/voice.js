/* ── voice.js · ask out loud ──────────────────────────────────────────
   Reading tarot is a spoken thing, so the deck grew ears. Tap the dot,
   say the question, tap again. Whisper-tiny (~40 MB, transformers.js,
   browser-cached) turns it into text in the field and then gets out of
   the way: the transcript is an ordinary question from that point on,
   seeding the shuffle and feeding attunement exactly as typing would.

   Nothing loads until the dot is tapped. A page whose seeker never
   speaks pays nothing for this, which is the same bargain attune.js
   makes about the embedding model.

   Nothing recorded ever leaves the page. There is nowhere to send it:
   the model runs here, the audio is discarded the moment it is decoded,
   and the microphone track is stopped before transcription starts.

   Classic script, no build step. Injects its own button, so a browser
   that cannot record simply never grows one — and marks the body with
   `canvoice` so the Back Room can hide the toggle to match.
   ──────────────────────────────────────────────────────────────────── */
(() => {
  const MODEL = 'Xenova/whisper-tiny.en';
  const CDN = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.3.3/dist/transformers.min.js';
  const MAXMS = 20000;   // a question that runs longer than this is a monologue
  const MAXLEN = 140;    // #q's own maxlength; setting .value bypasses it

  /* Knowing when the seeker has finished. Every level here is measured
     against the room rather than set absolutely, because a quiet bedroom and
     a kitchen with a fridge in it are two orders of magnitude apart and a
     fixed threshold would either never trigger in one or trigger constantly
     in the other. The first `calibMs` of the recording is the room; speech is
     anything that beats it by `startMul`.

     `startMul` sits above `stopMul` deliberately — with one threshold the
     level flaps across it on every syllable boundary and the timer resets
     forever. Guesses, all of them, pending a real room and a real thumb; they
     are gathered here to be tuned the way TELL_CFG is meant to be. */
  const VAD = {
    calibMs: 350,       // the room, measured before anything counts as speech
    startMul: 2.2,      // speech must beat the room by this to have begun
    stopMul: 1.5,       // ...and drop under this to have stopped. Hysteresis.
    floorMin: 0.006,    // absolute floor, so a silent room does not make breathing speech
    silenceMs: 1400,    // quiet this long after speech, and the question is over
    minMs: 700,         // never stop before this: a cough cannot end a reading
    noSpeechMs: 6000,   // said nothing at all? give the tap back rather than wait out MAXMS
  };

  const qEl = document.getElementById('q');
  const ask = qEl && qEl.closest('.ask');
  const AC = window.AudioContext || window.webkitAudioContext;
  const able = qEl && ask && AC && window.MediaRecorder &&
    navigator.mediaDevices && navigator.mediaDevices.getUserMedia;
  if (!able) return;

  document.body.classList.add('canvoice');

  /* Drawn rather than typed: there is no microphone in any font that is not
     an emoji, and an emoji would arrive in colour on a page that has exactly
     two. Stroked with currentColor so the states below only set a colour. */
  const ICON = {
    mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"' +
      ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
      '<rect x="9" y="2" width="6" height="11" rx="3"/>' +
      '<path d="M5 10.5a7 7 0 0 0 14 0"/>' +
      '<path d="M12 17.5V21M8.5 21h7"/></svg>',
    stop: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">' +
      '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/></svg>',
  };

  /* The endpointing knobs, reachable from a console on the phone the way
     ARCANAI_ATTUNE.config is — these want tuning against a real room and a
     real thumb, and making that need a rebuild is how they stay guesses.
     `silenceMs` is the one that will be wrong first. */
  window.ARCANAI_VOICE = { config: VAD, model: MODEL };

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.id = 'mic';
  btn.setAttribute('aria-label', 'Ask out loud');
  btn.title = 'Ask out loud';
  btn.innerHTML = ICON.mic;
  ask.appendChild(btn);

  const say = document.createElement('div');
  say.id = 'vsay';
  say.setAttribute('aria-live', 'polite');
  ask.appendChild(say);

  /* idle → warm (fetching the model) → live (recording) → think → idle.
     `live` and `think` are the only states that lock the button. */
  let state = 'idle';
  let rec = null, chunks = [], stopTimer = 0, asr = null, asrPromise = null;
  let unwatch = () => {};   // tears down the level watcher's audio graph
  /* Tri-state, and the third state is the point: `false` means the watcher ran
     and heard nobody, `null` means there was no watcher to ask. Only `false`
     is grounds for refusing to transcribe — treating `null` as silence would
     disable the whole feature on any engine where the analyser cannot build. */
  let heard = null;

  /* Whisper does not return nothing when it is given nothing. Handed silence
     it emits a confident little pleasantry — "you", "Thank you." — because
     those are what fills the quiet in its training data. Measured here: six
     seconds of a silent stream produced "you", which sailed past the
     empty-string guard and into the question field. The VAD flag above is the
     real defence; this is the second line, for audio that cleared the level
     gate on a door slam and still had no words in it. */
  const NOISE = /^(you|thank you|thanks for watching|bye|okay|ok|oh|hm+|uh|um)[.!?]*$/i;

  const setState = (s, msg) => {
    state = s;
    btn.className = s === 'idle' ? '' : 'v-' + s;
    btn.innerHTML = s === 'live' ? ICON.stop : ICON.mic;
    btn.setAttribute('aria-label', s === 'live' ? 'Stop and ask' : 'Ask out loud');
    btn.title = btn.getAttribute('aria-label');
    say.textContent = msg || '';
    say.classList.toggle('show', !!msg);
  };

  /* The model download is started the moment recording begins, not when it
     ends: the seeker is talking for a few seconds either way, and that is
     the only free time this feature gets. */
  function loadASR() {
    if (asrPromise) return asrPromise;
    asrPromise = (async () => {
      const { pipeline, env } = await import(CDN);
      env.allowLocalModels = false;
      asr = await pipeline('automatic-speech-recognition', MODEL, {
        dtype: 'q8',
        /* Shown while recording AND while transcribing: on a cold first use
           the download usually outlasts the sentence, and a silent minute
           after the seeker stops talking reads as a hang. */
        progress_callback: (p) => {
          if (state !== 'live' && state !== 'think') return;
          if (!p || p.status !== 'progress' || !p.total) return;
          say.textContent = 'waking its ears… ' + Math.round(p.progress) + '%';
          say.classList.add('show');
        },
      });
      return asr;
    })().catch((e) => {
      asrPromise = null;      // a failed download should be retryable
      throw e;
    });
    return asrPromise;
  }

  /* Whisper wants 16 kHz mono float. OfflineAudioContext resamples for free
     on anything current; the manual path is for engines that still refuse to
     be constructed at a rate the hardware does not run at. */
  function linear16k(buf) {
    const src = buf.getChannelData(0);
    const ratio = buf.sampleRate / 16000;
    const n = Math.floor(src.length / ratio);
    const out = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = i * ratio, i0 = x | 0, f = x - i0;
      out[i] = src[i0] * (1 - f) + (src[i0 + 1] || 0) * f;
    }
    return out;
  }

  async function to16k(blob) {
    const ctx = new AC();
    let buf;
    try {
      buf = await ctx.decodeAudioData(await blob.arrayBuffer());
    } finally {
      ctx.close();
    }
    const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    try {
      const off = new OAC(1, Math.max(1, Math.ceil(buf.duration * 16000)), 16000);
      const src = off.createBufferSource();
      src.buffer = buf;
      src.connect(off.destination);
      src.start();
      return (await off.startRendering()).getChannelData(0);
    } catch (_) {
      return linear16k(buf);
    }
  }

  /* Watches the level on the live stream and stops the recorder when the
     seeker has finished. Returns its own disposer; any failure to build the
     graph returns a no-op, leaving the tap and MAXMS as the only ways out —
     which is exactly what shipped before this existed. */
  function watchLevel(stream) {
    let ctx, timer = 0;
    const dispose = () => {
      clearInterval(timer);
      if (ctx) { try { ctx.close(); } catch (_) {} ctx = null; }
    };
    try {
      ctx = new AC();
      const an = ctx.createAnalyser();
      an.fftSize = 1024;
      ctx.createMediaStreamSource(stream).connect(an);
      const buf = new Float32Array(an.fftSize);
      const t0 = performance.now();
      let sum = 0, n = 0, spoke = false, quietAt = 0;
      heard = false;    // from here on, silence is a fact rather than an absence of evidence
      timer = setInterval(() => {
        if (state !== 'live') return dispose();
        an.getFloatTimeDomainData(buf);
        let s = 0;
        for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
        const rms = Math.sqrt(s / buf.length);
        const t = performance.now() - t0;
        if (t < VAD.calibMs) { sum += rms; n++; return; }
        const room = Math.max(VAD.floorMin, n ? sum / n : VAD.floorMin);
        if (!spoke) {
          if (rms > room * VAD.startMul) { spoke = heard = true; quietAt = 0; }
          else if (t >= VAD.noSpeechMs) stop();
          return;
        }
        if (rms > room * VAD.stopMul) { quietAt = 0; return; }
        if (!quietAt) { quietAt = performance.now(); return; }
        if (performance.now() - quietAt >= VAD.silenceMs && t >= VAD.minMs) stop();
      }, 50);
    } catch (_) {
      dispose();
    }
    return dispose;
  }

  async function start() {
    // claimed before the first await: the permission prompt can sit there for
    // seconds, and until the state moves off idle a second tap starts a second
    // stream and leaks the first one's microphone
    setState('warm', '');
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      setState('idle', e && e.name === 'NotAllowedError'
        ? 'the deck was not given permission to listen'
        : 'no microphone it can reach');
      return;
    }
    chunks = [];
    heard = null;
    rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    rec.onstop = () => {
      unwatch();
      unwatch = () => {};
      stream.getTracks().forEach((t) => t.stop());   // the light goes off here
      finish();
    };
    rec.start();
    // state before the watcher: its first tick reads `state` and would dispose
    // itself on the spot if the recording were not live yet
    setState('live', 'listening…');
    unwatch = watchLevel(stream);
    loadASR().catch(() => {});
    stopTimer = setTimeout(stop, MAXMS);
  }

  function stop() {
    clearTimeout(stopTimer);
    if (rec && rec.state !== 'inactive') rec.stop();
    else { unwatch(); unwatch = () => {}; }   // nothing to stop; still let go of the graph
  }

  async function finish() {
    setState('think', 'hearing you…');
    try {
      const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
      chunks = [];
      rec = null;
      // the watcher listened and nobody spoke: do not wake the model to invent
      // something, and do not spend the download on a mis-tap
      if (heard === false) { setState('idle', 'it did not catch that'); return; }
      if (blob.size < 1200) { setState('idle', 'it did not catch that'); return; }
      const [audio, model] = await Promise.all([to16k(blob), loadASR()]);
      const out = await model(audio);
      const text = ((out && out.text) || '').trim().slice(0, MAXLEN);
      if (!text || /^[\s.,!?\-]*$/.test(text) || NOISE.test(text)) {
        setState('idle', 'it did not catch that');
        return;
      }
      qEl.value = text;
      /* `input` so the shuffle's entropy pool, the typing sampler and
         attune's warm-up all see the question arrive by their usual door;
         `arcanai:spoken` immediately after so the page can tell the deck
         that this one was said rather than written. Order matters: the
         page resets the typing sampler on the second event. */
      qEl.dispatchEvent(new Event('input', { bubbles: true }));
      qEl.dispatchEvent(new CustomEvent('arcanai:spoken', { bubbles: true }));
      setState('idle', '');
    } catch (e) {
      console.warn('\u{1F52E} voice: unavailable —', e && e.message);
      setState('idle', 'it could not hear you this time');
    }
  }

  btn.addEventListener('click', () => {
    if (state === 'live') stop();
    else if (state === 'idle') start();
  });

  // leaving the reading should not leave the microphone open
  addEventListener('pagehide', stop);
})();
