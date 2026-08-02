#!/usr/bin/env python3
"""Package the Audacity Tarot for digital release."""
import json, os, glob, shutil
from PIL import Image

CARDS = os.path.dirname(os.path.abspath(__file__))
REL = os.path.join(os.path.dirname(CARDS), 'release', 'major-arcanai')
FULL, WEB = (800, 1280), (500, 800)

MEANINGS = {
    "zero_of_fucks": "Let go of expectations and pressure. Step into freedom and a fresh start.",
    "burned_bridge": "Not everything is meant to be saved. Some endings are necessary.",
    "two_of_deez": "Stand confidently on your own. You don't need validation.",
    "lovers": "Deep connection — romantic, platonic, or with yourself.",
    "coffee": "Wake up. Face reality. Do what needs to be done.",
    "death": "Transformation through endings. Let the old version of you go.",
    "moon": "Things are unclear. Trust your intuition and wait.",
    "strength": "Inner calm and patience will carry you through.",
    "perseverance": "Keep going. You're closer than you think.",
    "tea": "Truth is being revealed. Stay grounded.",
    "last_straw": "You've reached your limit. Change is inevitable.",
    "audacity": "Be bold. Take the risk.",
    "breast_pump": "You're overgiving. Rest and refill yourself.",
    "bottle": "Unexpressed emotions will surface eventually.",
    "taco": "Find joy in small pleasures.",
    "gold_shoulder": "Beware of ego and image obsession.",
    "child": "Nurture your inner child.",
    "mother": "You also deserve care, not just others.",
    "mom_boss": "You're doing too much. Let go of control.",
    "hermit": "Withdraw and reflect.",
    "gardener": "Growth takes time. Keep nurturing.",
    "cheese_fries": "You deserve enjoyment.",
    "slice": "Release toxic attachments.",
    "empress": "You are creative and abundant.",
    "chicken_nugget": "Comfort and simplicity heal.",
    "sun": "Joy and truth are coming to light.",
    "high_priestess": "Trust your inner wisdom.",
    "zoom_meeting": "Disconnect from the fake, reconnect with real life.",
    "influencer": "Be authentic — image isn't everything.",
    "life_of_the_party": "Outward shine can hide inner loneliness.",
    "last_hurrah": "A final celebration before an ending.",
    "dead_end_job": "Don't stay stuck in something meaningless.",
    "fiddle_leaf_fig": "Balance appearance with reality.",
    "star": "Hope and healing are ahead.",
    "devil": "Break free from unhealthy cycles.",
    "fair_weather_friend": "Reevaluate shallow relationships.",
    "tower": "Breakdown leads to breakthrough.",
    "drama_queen": "Not everything is a crisis. Check the story you're telling yourself.",
    "last_flying_fuck": "Watch it go. Some things no longer deserve your energy.",
    "nap": "Rest is productive. Lie down.",
}



REVERSED = {
    "zero_of_fucks": "You claim you don't care. You absolutely do. Admit it.",
    "burned_bridge": "You lit this one too soon. Some bridges deserve an apology and a rebuild.",
    "two_of_deez": "Fishing for validation again. Deez are not for external approval.",
    "lovers": "Disconnection. You're kissing distance from someone you stopped seeing.",
    "coffee": "Decaf energy. You're running on fumes and calling it fine.",
    "death": "Clinging to the old you. Rigor mortis is not a personality.",
    "moon": "The fog is self-made. Stop mistaking anxiety for intuition.",
    "strength": "Forcing it. The lion calms down when you stop wrestling.",
    "perseverance": "Stubbornness isn't progress. Maybe it's the wrong staircase.",
    "tea": "The gossip turned toxic. Spill less, sip more.",
    "last_straw": "You keep declaring the last straw, then buying more straws.",
    "audacity": "Bold in the wrong direction. Audacity without follow-through is just noise.",
    "breast_pump": "Running on empty and still giving. Refill the well first.",
    "bottle": "It already burst. Clean up honestly instead of re-corking.",
    "taco": "Comfort became avoidance. The taco cannot fix this one.",
    "gold_shoulder": "The mirror is winning. Look outward for once.",
    "child": "Your inner child is running the meeting. Adult supervision required.",
    "mother": "Martyr mode. Care that costs you everything isn't care.",
    "mom_boss": "Delegation refused, burnout accepted. Put three of the six arms down.",
    "hermit": "Solitude curdled into hiding. Crack the door open.",
    "gardener": "Overwatering. Some things only grow when you leave them alone.",
    "cheese_fries": "All reward, no task. Earn the fries.",
    "slice": "You cut the wrong thread — or keep re-tying the one you cut.",
    "empress": "Creative block by comparison. Make ugly things on purpose.",
    "chicken_nugget": "Comfort became the whole menu. Vary the diet.",
    "sun": "Forced positivity. It's okay to sit in the shade sometimes.",
    "high_priestess": "You already know. You've known for months. Stop asking for signs.",
    "zoom_meeting": "This could have been an email. So could your excuses.",
    "influencer": "Performing a life instead of living one. Log off.",
    "life_of_the_party": "The mask slipped. Let someone see the tear.",
    "last_hurrah": "The party's over and you're still holding the glass. Go home.",
    "dead_end_job": "The exit exists. You've just memorized the wallpaper.",
    "fiddle_leaf_fig": "All price tag, no roots. Get real or get repotted.",
    "star": "Hope deferred. Healing isn't linear — pour anyway.",
    "devil": "Back in the cuffs, voluntarily. You know the way out; you've walked it before.",
    "fair_weather_friend": "Plot twist: you might be the one holding the umbrella. Check.",
    "drama_queen": "Suppressed feelings staging a coup. A little drama is honest.",
    "last_flying_fuck": "You let it go too fast. Some things deserved your care.",
    "nap": "Rest became hiding. Get up, hydrate, face one thing.",
    "tower": "Postponing the collapse. Controlled demolition beats waiting for lightning.",
}


def normalize(src, canvas, box_frac=0.93):
    """Crop to ink bbox, stretch to one uniform art box, center on canvas.
    Uniformity beats aspect purity here: every frame gets identical size
    (max ~12% stretch on the worst source aspect)."""
    im = Image.open(src).convert('L')
    bb = im.point(lambda v: 255 if v < 240 else 0).getbbox()
    im = im.crop(bb)
    W, H = canvas
    box = (int(W * box_frac), int(H * 0.956))
    im = im.resize(box, Image.LANCZOS)
    out = Image.new('L', canvas, 255)
    out.paste(im, ((W - box[0]) // 2, (H - box[1]) // 2))
    return out


def main():
    for sub in ('cards', 'cards-web'):
        os.makedirs(os.path.join(REL, sub), exist_ok=True)

    manifest = json.load(open(os.path.join(CARDS, 'manifest.json')))
    deck = {
        "name": "The Major ArcanAI",
        "version": "1.3",
        "description": "A 40-card humorous oracle deck of sarcastic skeletons in ornate black-and-white line art. Twelve classic major arcana anchor a deck of cards life actually deals you.",
        "card_size_px": {"full": FULL, "web": WEB},
        "back": {"full": "cards/back.png", "web": "cards-web/back.png"},
        "cards": [],
    }

    for i, c in enumerate(manifest['cards']):
        slug = c['slug']
        src = os.path.join(CARDS, 'lettered', f"{i:02d}_{slug}.png")
        fn = f"{i:02d}_{slug}.png"
        normalize(src, FULL).save(os.path.join(REL, 'cards', fn), optimize=True)
        normalize(src, WEB).save(os.path.join(REL, 'cards-web', fn), optimize=True)
        deck['cards'].append({
            "index": i,
            "numeral": c['num'],
            "name": c['name'],
            "meaning": MEANINGS[slug],
            "reversed": REVERSED[slug],
            "image": {"full": f"cards/{fn}", "web": f"cards-web/{fn}"},
        })
        print('packed', fn)

    normalize(os.path.join(CARDS, 'back.png'), FULL).save(os.path.join(REL, 'cards', 'back.png'), optimize=True)
    normalize(os.path.join(CARDS, 'back.png'), WEB).save(os.path.join(REL, 'cards-web', 'back.png'), optimize=True)

    with open(os.path.join(REL, 'deck.json'), 'w') as f:
        json.dump(deck, f, indent=2)

    gb = ["# The Major ArcanAI\n",
          "*A 40-card oracle deck of sarcastic skeletons — the cards life actually deals you.*\n",
          "## How to read\n",
          "Shuffle. Draw one card for a daily nudge, three for past / present / future,",
          "or five when things have truly gone sideways. The deck does not predict the",
          "future; it tells you what you already know, but louder.\n",
          "## The cards\n"]
    for c in deck['cards']:
        gb.append(f"**{c['numeral']} — {c['name']}**  \n{c['meaning']}  \n*Reversed:* {c['reversed']}\n")
    gb.append("\n---\n")
    gb.append("Art style: ornate black-and-white skeleton line art. Generated with Google Gemini, ")
    gb.append("art-directed and lettered (Cinzel) by hand. v1.0, 2026.\n")
    with open(os.path.join(REL, 'GUIDEBOOK.md'), 'w') as f:
        f.write('\n'.join(gb))

    print('release at', REL)


if __name__ == '__main__':
    main()
