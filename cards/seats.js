/* The Major ArcanAI — the seats.
 *
 * One definition of what each position in a spread is, read by two very
 * different consumers:
 *
 *   `prose` is MATCHING text. attune.js embeds it and cosines the question
 *   against it to decide which card belongs in which seat. It is written long
 *   and plain for that reason, and it is never displayed. Editing it changes
 *   attune.js's corpus signature and silently rebuilds every cached vector on
 *   every device — a cost, not a bug, but know that you are paying it.
 *
 *   `lens` is DISPLAY text. It is printed in front of the card's meaning so
 *   that the same card reads differently depending on where it landed, which
 *   is the whole point of dealing cards into positions and was, until now,
 *   information the page threw away. Written short, lowercase, ending in a
 *   colon, so it runs into the deck's declarative copy as one sentence:
 *   "what's in the way: Keep going. You're closer than you think."
 *
 *   `label` is the heading over the card. Defaults to `name`; it only exists
 *   because the matching prose wants "Hopes and Fears" (an ampersand is not a
 *   word and embeds like punctuation) and the page wants "Hopes & Fears".
 *
 * Loaded before the deck script and before attune.js. Both degrade rather than
 * throw if it is missing: the page falls back to bare labels, attune.js turns
 * off seating and leaves selection alone.
 */
(function () {
  'use strict';

  const SEATS = {
    /* One card has no seat — there is nowhere else it could have gone. */
    1: [
      { name: '', lens: '', prose: '' },
    ],
    3: [
      { name: 'Past',
        lens: "what you're still carrying:",
        prose: 'What is behind this. The history you are still carrying, what already happened.' },
      { name: 'Present',
        lens: 'where you actually are:',
        prose: 'Where you stand now. The current state of it, the shape of today.' },
      { name: 'Future',
        lens: 'where this is headed:',
        prose: 'What is coming. The next stretch of road, where this is heading.' },
    ],
    5: [
      { name: 'The Situation',
        lens: 'the plain facts of it:',
        prose: 'The heart of the matter. Where you actually are right now, the plain facts of it.' },
      { name: 'The Obstacle',
        lens: "what's in the way:",
        prose: 'What stands in the way. The friction, the block, the thing working against you.' },
      { name: 'The Advice',
        lens: 'what to do about it:',
        prose: 'What to do about it. The counsel, the move to make, the practical step.' },
      { name: 'The Vibe',
        lens: 'how this feels:',
        prose: 'The mood and atmosphere around this. How it feels, the emotional weather.' },
      { name: 'The Outcome',
        lens: 'where this lands if nothing changes:',
        prose: 'Where this lands if nothing changes. The result, the destination, how it ends.' },
    ],
    10: [
      { name: 'The Situation',
        lens: 'where you actually are, not where you say you are:',
        prose: 'The heart of the matter. Where you actually are, not where you say you are.' },
      { name: 'What Crosses You',
        lens: 'what cuts across it:',
        prose: 'The force working with or against it. The complication cutting across the situation.' },
      { name: 'The Root',
        lens: 'what drives it from underneath:',
        prose: 'What drives this from underneath. The cause, the part you do not say out loud.' },
      { name: 'The Recent Past',
        lens: "what's already on its way out:",
        prose: 'What is on its way out. What just happened and is already fading.' },
      { name: 'The Crown',
        lens: "the best you're reaching for:",
        prose: 'The best available outcome. What you are consciously reaching for, your aim and hope.' },
      { name: 'The Near Future',
        lens: 'the next beat:',
        prose: 'The next beat. Days and weeks, what arrives soon.' },
      { name: 'The Self',
        lens: "how you're showing up:",
        prose: 'How you are showing up in this story. Your own conduct, stance and behaviour.' },
      { name: 'The House',
        lens: "the room you're in:",
        prose: 'Your environment. The people around you, the room, the group chat.' },
      { name: 'Hopes and Fears',
        label: 'Hopes & Fears',
        lens: 'what you want and dread at once:',
        prose: 'What you long for and what you dread, which are usually the same thing.' },
      { name: 'The Outcome',
        lens: 'how it ends if nothing changes:',
        prose: 'Where this lands if nothing changes. The final result, how it ends.' },
    ],
  };

  const modes = Object.keys(SEATS);
  const seat = (mode, i) => (SEATS[mode] || [])[i] || null;

  window.ARCANAI_SEATS = {
    seats: SEATS,

    /* Display headings per mode: {1:[''], 3:['Past',...], ...} — what the
       page's LABELS used to hardcode. */
    labels: modes.reduce((acc, m) => {
      acc[m] = SEATS[m].map((s) => s.label || s.name);
      return acc;
    }, {}),

    /* The matching corpus, in the [name, prose] pairs attune.js embeds.
       Seats with no prose (mode 1) are excluded: an empty document would be a
       vector pointing nowhere, and there is nothing to seat anyway. */
    matching: modes.filter((m) => SEATS[m].every((s) => s.prose)).reduce((acc, m) => {
      acc[m] = SEATS[m].map((s) => [s.name, s.prose]);
      return acc;
    }, {}),

    labelFor: (mode, i) => { const s = seat(mode, i); return s ? (s.label || s.name) : ''; },
    lensFor: (mode, i) => { const s = seat(mode, i); return s ? s.lens : ''; },
  };
})();
