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
    "algorithm": "Some wheels turn without you. Play your hand and let the rest spin.",
    "receipts": "The record speaks for itself. What was done gets weighed.",
    "landlord": "There are terms, and they apply to you too.",
    "waiting_room": "Nothing moves yet. That isn't failure — it's the pause before.",
    "slow_cooker": "Low heat, long time. It cannot be hurried into being.",
    "apology": "Say it plainly, without conditions. Repair starts there.",
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
    "algorithm": "Taking the weather personally. The wheel was never aimed at you.",
    "receipts": "Keeping score for a war you claim not to be fighting. Screenshots aren't intimacy.",
    "landlord": "Control dressed up as order. You're the one who won't bend.",
    "waiting_room": "You could have left the queue an hour ago. Stalling isn't waiting.",
    "slow_cooker": "You cranked the heat to finish sooner. It's raw in the middle.",
    "apology": "“Sorry you feel that way.” That's not an apology, that's an exit.",
}

# Situational expansions. NEVER shown to a seeker: these exist only so the
# semantic shuffle can match a card against the everyday circumstances people
# actually type. Card meanings are written as aphorisms ("Break free from
# unhealthy cycles"), which sit nowhere near a concrete question in embedding
# space. Keep each to roughly twenty words: padding a short well-placed vector
# drags it off target (a long draft knocked Strength from rank 4 to 17).
SITUATIONS = {
    "zero_of_fucks": "Walking away without drama, starting over somewhere new, no longer auditioning for anyone's approval.",
    "burned_bridge": "Cutting someone off for good, leaving a job badly, blocking a number, a friendship past repair.",
    "two_of_deez": "Making a decision nobody approves of, backing yourself, ignoring the group chat's opinion of your life.",
    "lovers": "Dating someone seriously, choosing a partner, whether to commit, a friendship that genuinely matters.",
    "coffee": "Getting through the morning, facing the thing you have avoided, deadlines, the errand you keep rescheduling.",
    "death": "A chapter closing, leaving a city or a marriage or a career, becoming someone your old friends would not recognise.",
    "moon": "Mixed signals, not knowing where you stand, waiting on news, a gut feeling you cannot prove.",
    "strength": "Keeping your temper with a difficult person, enduring a long hard stretch, restraint instead of force.",
    "perseverance": "Late in a long project, months of job hunting, studying, wanting to quit near the finish.",
    "tea": "Gossip reaching you, finding something out, a secret surfacing, what people say once you leave the room.",
    "last_straw": "The final incident, handing in your notice, ending it after one thing too many.",
    "audacity": "Asking for the raise, making the first move, applying anyway, saying the bold thing out loud.",
    "breast_pump": "Caring for everyone else, new parenthood, being the one who always helps, running empty for others.",
    "bottle": "Swallowing what you feel, not saying it, holding it down until it comes out sideways.",
    "taco": "A good meal, a small treat, cheap ordinary happiness, what to eat, plans with people you like.",
    "gold_shoulder": "Status, showing off, being seen with the right people, caring how it looks over how it is.",
    "child": "Play, doing something purely for fun, what you loved at eight, taking yourself less seriously.",
    "mother": "Looking after family, being the reliable one, nobody thinking to ask how you are.",
    "mom_boss": "Too many responsibilities, running everything, work and home both landing on you, delegating badly.",
    "hermit": "Cancelling plans, needing time alone, stepping back from people, wanting quiet instead of the noise.",
    "gardener": "Slow progress, a new job or skill or relationship still growing, patience with something planted recently.",
    "cheese_fries": "Indulgence, a night off, eating what you actually want, permission to enjoy something.",
    "slice": "Cutting someone loose, ending a draining friendship, removing yourself from a group that costs you.",
    "empress": "Making something, a project blooming, money coming in, fertility, having enough to be generous.",
    "chicken_nugget": "Wanting something easy, comfort food, keeping it simple, low effort care on a bad day.",
    "sun": "Good news, things finally going well, feeling healthy again, a clear happy stretch.",
    "high_priestess": "Already knowing the answer underneath, a private instinct, something unsaid, trusting yourself over advice.",
    "zoom_meeting": "Pointless meetings, remote work, screens all day, digital life crowding out the actual one.",
    "influencer": "Curating how you appear, social media, comparing your life to posts, the personal brand.",
    "life_of_the_party": "Being the fun one, big social nights, everyone's favourite and nobody's confidant.",
    "last_hurrah": "One last night, a leaving do, the final round before things change, a goodbye that is also a party.",
    "dead_end_job": "A job going nowhere, quitting, stuck in a role or a town or a relationship with no future.",
    "fiddle_leaf_fig": "Looking fine and not being fine, a life that photographs better than it lives.",
    "star": "Recovery after a bad run, faith returning, the first good news in a while, reasons to keep going.",
    "devil": "The habit you keep going back to, addiction, the person who is bad for you, the cage with its door open.",
    "fair_weather_friend": "Friends who vanish when it gets hard, one sided effort, who actually shows up for you.",
    "tower": "Sudden collapse, redundancy, a breakup out of nowhere, the business failing, everything changing at once.",
    "drama_queen": "Overreacting, catastrophising, making it bigger than it is, a story you have told yourself too often.",
    "last_flying_fuck": "Letting go of what does not deserve you, boundaries, refusing to care about it any more.",
    "nap": "Exhaustion, needing sleep, overwork, a day off, your body asking you to stop.",
    "algorithm": "Luck turning, being passed over, a system deciding without you, timing you do not control.",
    "receipts": "Being proved right, a formal complaint, evidence, a fair outcome, consequences finally landing on someone.",
    "landlord": "Rent, a boss or parent setting the terms, rules you did not write, an authority you answer to.",
    "waiting_room": "Waiting on results, a visa, a court date, an offer, weeks where nothing can be done.",
    "slow_cooker": "Physiotherapy, saving slowly, a long treatment, learning something properly, pacing yourself through months of it.",
    "apology": "Owing an apology, being owed one, making amends, whether to forgive someone.",
}

SITUATIONS_REV = {
    "zero_of_fucks": "Performing indifference, pretending to be over it while checking on them nightly.",
    "burned_bridge": "Regretting how you ended it, wanting to apologise, wondering whether to reach out again.",
    "two_of_deez": "Fishing for compliments, posting for reassurance, asking six people until one of them agrees.",
    "lovers": "Drifting apart in the same bed, a relationship gone quiet, roommates who used to be in love.",
    "coffee": "Burnout, sleeping badly, too much caffeine and no rest, calling exhaustion a personality.",
    "death": "Clinging to who you used to be, keeping an old identity alive well past its expiry.",
    "moon": "Anxiety dressed up as instinct, inventing motives, spiralling at night over something unconfirmed.",
    "strength": "Snapping at last, patience running out, forcing something that needed waiting.",
    "perseverance": "Grinding away at something already dead, stubbornness mistaken for commitment.",
    "tea": "Spreading it further, drama you are feeding, talking about people instead of to them.",
    "last_straw": "Threatening to leave and staying, raising your limit again, a last straw that keeps not being last.",
    "audacity": "Recklessness, nerve without a plan, or somebody else's gall aimed squarely at you.",
    "breast_pump": "Resenting the people you keep giving to, martyrdom, keeping score of your own sacrifice.",
    "bottle": "The blow up, crying at the wrong moment, drinking to keep it down, saying it all badly at once.",
    "taco": "Treating yourself instead of dealing with it, small pleasures used as avoidance.",
    "gold_shoulder": "The ego cracking, humiliation, being found out as less impressive than the photographs.",
    "child": "Sulking, tantrums, acting your shoe size, waiting for somebody to parent you.",
    "mother": "Guilt for resting, smothering the people you love, care that has curdled into control.",
    "mom_boss": "Micromanaging, refusing help, collapsing from insisting on doing all of it yourself.",
    "hermit": "Isolation, not answering anyone for weeks, loneliness dressed up as solitude.",
    "gardener": "Neglect, giving up before it grew, expecting a harvest a week after planting.",
    "cheese_fries": "Overdoing it, comfort as anaesthetic, the regret that arrives after the binge.",
    "slice": "Still attached, unable to make the cut, going back to the thing you keep ending.",
    "empress": "Creative block, scarcity thinking, hoarding, nothing you make ever feeling good enough.",
    "chicken_nugget": "Only ever comfort, avoiding anything difficult, the same safe thing every single night.",
    "sun": "Forced positivity, performing happiness you do not feel, good news that keeps not arriving.",
    "high_priestess": "Ignoring what you already know, outsourcing the decision, a secret kept too long.",
    "zoom_meeting": "Hiding behind the screen, camera off in every sense, avoiding contact with actual people.",
    "influencer": "Believing your own image, envying strangers online, the gap between the profile and the life.",
    "life_of_the_party": "The comedown, lonely in a crowded room, going home alone after being on all night.",
    "last_hurrah": "Dragging it out, one more that is never the last, refusing to let the ending happen.",
    "dead_end_job": "Staying for the money, comfortable and wasted, waiting to be pushed instead of jumping.",
    "fiddle_leaf_fig": "Neglect behind the presentation, the thing quietly dying while it still looks green.",
    "star": "Losing hope, cynicism, believing honestly that it is never going to improve.",
    "devil": "Deeper in, choosing it again, telling yourself you could stop any time you wanted.",
    "fair_weather_friend": "Being that friend yourself, going quiet on someone who is in trouble.",
    "tower": "The slow collapse you can see coming, propping up what should be allowed to fall.",
    "drama_queen": "A real crisis waved off as drama, nobody believing you on the one occasion it counts.",
    "last_flying_fuck": "Caring loudly about not caring, spite, energy spent proving you have moved on.",
    "nap": "Sleeping to avoid it, oversleeping, tired no matter how long you stay lying down.",
    "algorithm": "Blaming yourself for bad luck, refreshing for a verdict, superstition, reading meaning into randomness.",
    "receipts": "Keeping score, screenshotting arguments, litigating a friendship, needing to be proved right more than reconciled.",
    "landlord": "Petty rules for their own sake, an authority abusing it, refusing to compromise on anything at all.",
    "waiting_room": "Procrastinating and calling it patience, martyring yourself, waiting for permission that will never come.",
    "slow_cooker": "Rushing it, quitting the course early, expecting results in a week, forcing what needs time.",
    "apology": "A non apology, being pressured to forgive too fast, apologising to end the conversation.",
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
        "version": "1.4",
        "description": "A 46-card humorous oracle deck of sarcastic skeletons in ornate black-and-white line art. Eleven classic major arcana anchor a deck of cards life actually deals you.",
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
            "situations": SITUATIONS[slug],
            "situations_reversed": SITUATIONS_REV[slug],
            "image": {"full": f"cards/{fn}", "web": f"cards-web/{fn}"},
        })
        print('packed', fn)

    normalize(os.path.join(CARDS, 'back.png'), FULL).save(os.path.join(REL, 'cards', 'back.png'), optimize=True)
    normalize(os.path.join(CARDS, 'back.png'), WEB).save(os.path.join(REL, 'cards-web', 'back.png'), optimize=True)

    with open(os.path.join(REL, 'deck.json'), 'w') as f:
        json.dump(deck, f, indent=2)

    gb = ["# The Major ArcanAI\n",
          "*A 46-card oracle deck of sarcastic skeletons — the cards life actually deals you.*\n",
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
