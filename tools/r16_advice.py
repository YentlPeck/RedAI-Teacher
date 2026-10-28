"""R16 (PokéBench rules): advice from power-on to Brock, and every button list fits a 6-press command.

Facts checked in reference/pokered:
- Name menus (engine/movie/oak_speech/oak_speech2.asm DisplayIntroNameTextBox): wMenuWatchedKeys = PAD_A only, so
  B never picks NEW NAME; text pages (home/joypad2.asm WaitForTextScrollButtonPress) go on with A or B.
- Naming screen (engine/menus/naming_screen.asm): START submits; an empty name reopens the screen (oak_speech2.asm
  ChoosePlayerName / ChooseRivalName `cp '@'`), so one letter (A) then START leaves it.
- Preset names (data/player/names.asm): NEW NAME, RED, ASH, JACK / NEW NAME, BLUE, GARY, JOHN.
- Oak's lab balls (data/maps/objects/OaksLab.asm): CHARMANDER (6,3), SQUIRTLE (7,3), BULBASAUR (8,3); a ball asks
  YES/NO with YES first (scripts/OaksLab.asm OaksLabMonChoiceMenu); then AskName asks for a nickname (YES/NO, then
  the NICKNAME? letter screen; an empty name keeps the species name). Seen in the emulator follow run.
- Pallet Town (scripts/PalletTown.asm): Oak appears when wYCoord == 1. Viridian (scripts/ViridianCity.asm): without
  EVENT_GOT_POKEDEX the sleeping old man pushes you back from (19,9).
- Learnsets (data/pokemon/evos_moves.asm): SQUIRTLE BUBBLE L8; BULBASAUR VINE WHIP L13; CHARMANDER EMBER L9.
  Brock (data/trainers/parties.asm): GEODUDE L12, ONIX L14, both Rock/Ground.
The boot sequence (A or START past the logo and title, A on NEW GAME) was seen in one emulator run.
"""
import re

MAX_PRESSES = 6
BUTTON = r"(?:up|down|left|right|a|b|start|select)(?:\*\d+)?"
RUN = re.compile(rf"(?<![\w*]){BUTTON}(?: {BUTTON})*(?![\w*])")
STARTER_Q = re.compile(r"\b(starter|starters|squirtle|charmander|bulbasaur|pok[eé]mon (?:should|do) i (?:pick|choose|take)|"
                       r"which (?:pok[eé]mon|ball|one)|pick|choose|ball)\b", re.I)
SQUIRTLE_SPOT = (7, 4)
WHY_SQUIRTLE = ("Brock's GEODUDE L12 and ONIX L14 are Rock/Ground: Water hits them 4 times as hard, and SQUIRTLE "
                "learns BUBBLE at L8. CHARMANDER's Scratch and Ember do only half damage to them; BULBASAUR's Vine "
                "Whip comes only at L13.")


def result(do, why, details=()):
    return dict(do=do, why=why, details=list(details))


def rows_of(s):
    return [r.strip() for r in s.get("teacher_screen", {}).get("rows", [])]


# ---------- power-on to Red's room ----------

def intro(A, s, question):
    """Logo, title, main menu, Oak's talk, name menus and the letter screen (play.py marks them intro)."""
    if not s.get("intro"):
        return None
    rows = rows_of(s)
    words = " ".join(rows)
    upper = words.upper()
    if "A B C D E F G H I" in upper:     # the letter screen (YOUR NAME? / RIVAL's NAME?); the NAME list has no alphabet
        return result("This is the letter screen. Press: a start (one command). A adds the letter under the arrow, "
                      "START finishes the name.",
                      "START with no letters only opens this screen again; one letter is enough. The story goes on "
                      "after the name.",
                      ["If you see this screen again, press: a start again."])
    if "NEW NAME" in upper and any(n in upper.split() for n in ("RED", "ASH", "JACK", "BLUE", "GARY", "JOHN")):
        rival = any(n in upper.split() for n in ("BLUE", "GARY", "JOHN"))
        name = "BLUE" if rival else "RED"
        return result(f"Pick a ready-made name. Press: down a (one command). The arrow moves from NEW NAME to {name}, "
                      "A picks it.",
                      "NEW NAME opens a slow letter screen. Any ready-made name works the same; B does nothing here.",
                      ["After that, press b*6 to read Professor Oak's next pages."])
    if "NEW GAME" in upper:
        if "CONTINUE" in upper:
            return result("Press down once, then A, to pick NEW GAME. Do not pick CONTINUE.",
                          "This game must start new from power-on.", [])
        return result("Press A: the arrow is on NEW GAME.", "This starts a new game; Professor Oak talks first.",
                      ["Then press b*6 (B also moves his pages on) and look; repeat until a NAME list shows."])
    if re.search(r"TEXT SPEED|BATTLE ANIMATION|BATTLE STYLE", upper):
        return result("Press B to leave OPTION, then press A on NEW GAME.", "OPTION only changes settings.", [])
    started = s["place"]["map_id"] != 0        # NEW GAME sets Red's room (map 38) before Oak talks (seen in RAM)
    if not started and not rows:
        return result("Press: a a a a a a (one command), then look. A skips the intro and the title screen, and A on the "
                      "menu picks NEW GAME.",
                      "The game starts at the Game Freak logo; nothing can go wrong with A before Professor Oak talks.",
                      ["When Professor Oak talks, switch to b*6: B moves his pages on but never picks NEW NAME "
                       "in the name list."])
    return result("Professor Oak is talking. Press: b*6 (one command), then look; repeat until a NAME list shows.",
                  "B moves his pages on like A. In the name list B does nothing, so it never picks NEW NAME "
                  "(A there opens a slow letter screen).",
                  ["In the NAME list press: down a. After the last page you stand in your room."])


# ---------- Oak's lab: the starter ----------

def starter(A, s, question):
    here = s["place"]["map"]
    if here != "OAKS_LAB" or s.get("battle") or s["team"] or "oak" not in s["story"]["done"]:   # Oak must have called you
        return None
    rows = rows_of(s)
    words = " ".join(rows).upper()
    if s.get("text_box"):
        offer = re.search(r"YOU WANT|POK.MON,", words) and re.search(r"\bYES\b", words)
        if offer and "SQUIRTLE" in words:
            return result("Press A for YES: SQUIRTLE is the best pick here.", WHY_SQUIRTLE,
                          ["Then press A through the text. The rival takes his ball and fights you before you leave."])
        if offer and "CHARMANDER" in words:
            return result("Press B for NO. Then take SQUIRTLE, the middle ball: stand at (7,4), press up (you only "
                          "turn), then A.", WHY_SQUIRTLE, [])
        if offer and "BULBASAUR" in words:
            return result("Press A for YES is fine: BULBASAUR also beats Brock, but SQUIRTLE is easier.", WHY_SQUIRTLE, [])
        return None
    if question and not STARTER_Q.search(question) and not re.search(r"what (?:now|next)|what should i do", question, re.I):
        return None
    p = s["place"]
    if (p["x"], p["y"]) == SQUIRTLE_SPOT:
        walk = "You stand below SQUIRTLE's ball."
        keys = "up a a a a a"
    else:
        route = A.walk_to(s, lambda m, q: m == "OAKS_LAB" and q == SQUIRTLE_SPOT, max_maps=1)
        walk = ("Walk to (7,4): " + ", ".join(A.walk_words(s, route)) + ".") if route else "Walk to (7,4), below the middle ball."
        keys = "up a a a a a"
    return result(f"Pick SQUIRTLE, the middle of the three balls on the table at (7,3). {walk} Then press: {keys} "
                  "(one command) and look: up only turns you to the ball, A opens it and reads on. At \"So! You want "
                  "the water POKéMON, SQUIRTLE?\" press A for YES.",
                  WHY_SQUIRTLE,
                  ["Then the game asks \"Do you want to give a nickname to SQUIRTLE?\": press B for NO (A opens a slow "
                   "letter screen).",
                   "CHARMANDER is the left ball (6,3), BULBASAUR the right one (8,3).",
                   "If you cannot move yet, Oak and the rival are still talking or walking: press A through their "
                   "text first.",
                   "After you pick, the rival takes his ball and fights you before you can leave: use TACKLE."])


# ---------- nickname question and letter screen (after the starter or a catch) ----------

def nickname(A, s, question):
    """AskName (engine/menus/naming_screen.asm): YES/NO, then the NICKNAME? letter screen; an empty name keeps the
    species name (`cp '@'` -> .declinedNickname)."""
    if s.get("intro") or not (s.get("text_box") or s.get("battle")):
        return None
    rows = rows_of(s) or [r.strip() for r in (s.get("teacher_ui") or {}).get("rows") or []]
    words = " ".join(rows).upper()
    if "NICKNAME?" in words and "A B C D E F G H I" in words:
        return result("Press START: it ends the letter screen. With no letters the Pokémon keeps its own name.",
                      "A nickname is not needed; every A here only adds letters.", [])
    if "NICKNAME" in words and re.search(r"\bYES\b", words):
        return result("Press B for NO: a nickname is not needed.",
                      "A (YES) opens a slow letter screen; B answers NO and the game goes on.", [])
    return None


# ---------- Pallet Town: the Oak trigger ----------

WAY_Q = re.compile(r"\b(where|way|go|what (?:now|next)|what should i do|what do i do|oak|north|grass|route 1|lab|stuck)\b", re.I)


def pallet_oak(A, s, question):
    """PalletTown.asm PalletTownDefaultScript: Oak appears when wYCoord == 1 (the top row), not one row earlier.
    The recorded walk stops at (10,2) because the story changed during the next step (R16 follow check)."""
    if s["place"]["map"] != "PALLET_TOWN" or s.get("battle") or s.get("text_box") or "oak" in s["story"]["done"]:
        return None
    if question and not WAY_Q.search(question):
        return None
    if s["place"]["y"] == 1:
        walk = "You are on the top row: Oak's call starts now; press A through the text."
    else:
        route = A.walk_to(s, lambda m, p: m == "PALLET_TOWN" and p[1] == 1 and p[0] in (10, 11), max_maps=1)
        walk = ("The walk: " + ", ".join(A.walk_words(s, route)) + ".") if route else "Walk to (10,1) at the top of the town."
    return result("Walk north to the top row of Pallet Town, at (10,1) or (11,1), at the edge of the tall grass of "
                  f"Route 1. Professor Oak stops you there and walks you to his lab; press A through his text. {walk}",
                  "Oak must stop you first: he is not in his lab at the start and only appears when you reach the "
                  "town's top row (the way into the tall grass).",
                  [walk, "In the lab, pick SQUIRTLE, the middle ball."])


# ---------- Parcel to Oak, the sleeping old man ----------

def parcel_to_oak(A, s, question):
    """Inside the lab with the Parcel: talk to Oak from the tile below him (OaksLab.asm OAK1 at (5,2))."""
    if s["place"]["map"] != "OAKS_LAB" or s.get("battle") or s.get("text_box") or "parcel" in s["story"]["done"]:
        return None
    if not A._bag(s).get("OAKS_PARCEL") or (question and not re.search(
            r"\b(parcel|oak|what (?:now|next)|what should i do|what do i do|where)\b", question, re.I)):
        return None
    p = s["place"]
    if (p["x"], p["y"]) == (5, 3):
        walk = "You stand right below him."
    else:
        route = A.walk_to(s, lambda m, q: m == "OAKS_LAB" and q == (5, 3), max_maps=1)
        walk = ("Walk to (5,3): " + ", ".join(A.walk_words(s, route)) + ".") if route else "Walk to (5,3), right below him."
    return result(f"Give the Parcel to Professor Oak at (5,2). {walk} Then press: up a a a a a (one command): up turns "
                  "you to him, A talks and reads on.",
                  "Oak takes the Parcel and gives you the Pokédex; then the old man in Viridian lets you go north.",
                  ["After the Pokédex: go back north through Route 1 and Viridian City to Route 2."])


def old_man(A, s, question):
    """ViridianCity.asm: without EVENT_GOT_POKEDEX, stepping on (19,9) by the sleeping old man (18,9) pushes you back."""
    if s["place"]["map"] != "VIRIDIAN_CITY" or s.get("battle") or s.get("text_box") or "pokedex" in s["story"]["done"]:
        return None
    if not question or not re.search(r"old man|grandpa|asleep|sleep|block|coffee|north|way up|can.?t pass|pushed",
                                     question, re.I):
        return None
    way = A._answer_core(s, None, 0, None)
    need = ("Bring the Parcel in your bag to Professor Oak in Pallet Town first (south through Route 1)."
            if A._bag(s).get("OAKS_PARCEL") else
            "First get Oak's Parcel from the clerk in the Viridian Mart (blue roof), then bring it to Oak in Pallet Town.")
    return result("The old man lets you pass only after you have the Pokédex. " + need,
                  "The game pushes you back at the old man until Oak has given you the Pokédex; there is no other way "
                  "north.", [way["do"]] + way["details"][:3])


def early(A, s, question, context):
    if s.get("battle") and not nickname(A, s, question):
        return None
    a = (intro(A, s, question) or nickname(A, s, question) or pallet_oak(A, s, question) or starter(A, s, question)
         or parcel_to_oak(A, s, question) or old_man(A, s, question))
    if not a:
        return None
    import read_state as R
    return dict(a, related=[], kind="text" if s.get("text_box") else "way", state=R.summary(s))


# ---------- every button list fits one 6-press command ----------

def count(run):
    return sum(int(t.split("*")[1]) if "*" in t else 1 for t in run.split())


def chunks(run, limit=MAX_PRESSES):
    """Split a button run into commands of at most `limit` presses (a*9 -> a*6 | a*3)."""
    out, cur, n = [], [], 0
    for tok in run.split():
        b, k = (tok.split("*")[0], int(tok.split("*")[1])) if "*" in tok else (tok, 1)
        while k:
            take = min(k, limit - n)
            cur.append(b if take == 1 else f"{b}*{take}")
            n += take
            k -= take
            if n == limit:
                out.append(" ".join(cur))
                cur, n = [], 0
    if cur:
        out.append(" ".join(cur))
    return out


LEG = re.compile(r"\b(up|down|left|right) (\d+) to \((-?\d+),(-?\d+)\)")
LEGS_NOTE = "Long walks as commands (at most 6 presses each): "


def leg_commands(texts):
    """Sol R16: walking legs longer than 6 steps, as explicit commands ("up 29 = up*6 | up*6 | up*6 | up*6 | up*5").
    A separate line, so the walk text (and everything that reads its legs) stays as it is."""
    seen, out = set(), []
    for text in texts:
        if not isinstance(text, str) or text.startswith(LEGS_NOTE):
            continue
        for mt in LEG.finditer(text):
            d, n = mt.group(1), int(mt.group(2))
            if n > MAX_PRESSES and mt.group(0) not in seen:   # "toward", not "to": leg readers skip this line
                seen.add(mt.group(0))
                out.append(f"{d} {n} toward ({mt.group(3)},{mt.group(4)}): " + " | ".join(chunks(f"{d}*{n}")))
    return (LEGS_NOTE + "; ".join(out) + ".") if out else None


def fit_text(text):
    """Rewrite any button run longer than 6 presses as separate commands."""
    def fix(mt):
        run = mt.group(0)
        if count(run) <= MAX_PRESSES:
            return run
        parts = chunks(run)
        return parts[0] + "".join(f" (one command), then {p}" for p in parts[1:]) + " (one command each)"
    if not isinstance(text, str):
        return text
    out = RUN.sub(fix, text)
    return out.replace(" (one command each) (one command)", " (one command each)").replace(
        " (one command each) in one command", " (one command each)").replace(
        "in ONE command: ", "in this order: ") if out != text else out


def finish(A, s, question, a):
    out = dict(a)
    for k in ("do", "why", "watch_out"):
        if k in out:
            out[k] = fit_text(out[k])
    out["details"] = [fit_text(d) for d in out.get("details", []) if not str(d).startswith(LEGS_NOTE)]
    note = leg_commands([out.get("do")] + out["details"])
    if note:
        out["details"].append(note)
    return out
