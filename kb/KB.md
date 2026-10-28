# Pokémon Red teacher: knowledge base (generated)

Built by `teacher/dev-r23/tools/build_kb.py`. Do not edit here: edit `teacher/dev-r23/kb/parts/*.md` and rebuild.

## 0. How to beat Pokémon Red (general rules)

**Tags**

- Every line ends with a tag that says how we know it:
- [game] read from the game's own code (pokered disassembly). Certain.
- [bot] measured in our bot's recorded games (`teacher/kb/bot_stats.json`). Certain for our bot; our bot plays risky.
- [web] from online sources, listed in `docs/teacher/research/AI_AGENTS_WEB_2026-10-19.md` (S1-S18).
- [advice] our advice. Makes sense, but not tested yet.

**The plan in one line**

- Pick Squirtle, catch a male Nidoran on Route 22, make it a Nidoking with the Moon Stone in Mt. Moon, and teach it strong TMs. Our bot's best live run with this plan is 1:46:57 (official time); a typical finish is about 1:51 (median 1:50:42 bot clock, 102 finishes in 900 full games) [bot]. A careful player can use the same plan with more levels and more healing [advice].

**Team**

- **Nidoking does almost all the fighting.** In our bot's finished games it is the only Pokémon above level 10 [bot].
- Nidoking's final moves in our bot: Thunderbolt, Horn Drill, Earthquake, Blizzard [bot]. For a careful player, Ice Beam (Celadon roof, give Fresh Water) is safer than Blizzard: listed accuracy 100% vs 90%. In Red, normal moves with 100% listed accuracy still miss 1 time in 256 (Swift and X Accuracy skip this check) [game].
- Helpers that only use field moves: Squirtle (Surf, Strength), Pidgey (Fly), Paras (Cut, Dig) [bot]. A normal player can level a second fighter as a backup. Recommended, not required [advice].
- Catch the helpers on the way: a flier (Pidgey, Route 2), Paras (Mt. Moon) for Cut, a Water Pokémon for Surf and Strength [game][bot].
- **Teach each HM before you need it.** Owning it is not enough. To use it outside battle you need a badge: Cut = Cascade (Misty), Fly = Thunder (Surge), Surf = Soul (Koga), Strength = Rainbow (Erika), Flash = Boulder (Brock) [game].
- Nidoking is weak to Water, Ground, Ice and Psychic [game]. The big danger fights are Misty (Water) and Sabrina (Psychic) [game]. Our bot dies most at Misty, Brock and the Champion [bot].

**Healing and items**

- Heal at every Pokémon Center you pass if HP is below half [advice].
- Full Heal cures status only (poison, sleep, ...). It does **not** restore HP. Gemini lost ~100 hours at the Elite Four believing it did [web S5].
- Keep 1-2 free bag slots. The bag holds 20 item types. A full bag blocks key items (Gemini failed in the Safari Zone) [game][web S6].
- Never throw away key items, HMs or TMs you still plan to use [advice].
- X Accuracy, X Speed and other X items each cost one turn, and switching Pokémon removes their effect. Use them only when your HP is safe [game][advice].
- Ethers and Elixers cannot be bought. Pick them up and save them for the League: S.S. Anne has an Ether and a Max Ether, Pokémon Tower 4F an Elixer [game]. Check your PP before the Elite Four [advice].
- Before the Elite Four, buy Full Restores / Max Potions and Revives at the Indigo Plateau shop [game][advice].

**Finding the way (where AI agents lose the most time)**

- Battles are rarely the problem. Mazes, items on the floor, boulder puzzles and missed story steps are [web S1, S2, S4].
- Always look for item balls on the floor and pick them up. Key items like the Card Key are just items on the floor [web S1].
- If you are stuck for long, leave the area and come back later. Write down what you tried [web S2].
- Do not trust notes you wrote earlier without checking. One wrong note can stall a run for days [web S2].
- Red is not FireRed. In Red you give a **drink** (not Tea) to the Saffron guards [web S9][game].
- Do not use Dig or an Escape Rope in the middle of a boulder puzzle: it resets the boulders [web S1].
- Boulders can only be pushed, never pulled. Plan the push before you start [game][advice].
- For mazes and puzzles the tool can give our bot's exact tile path (x, y as stored in game memory) [bot].

**Story checklist (what opens the way)**

- | Gate | What you need | Where to get it |
|---|---|---|
| Viridian north road / Mart | Deliver Oak's Parcel | Viridian Mart, bring to Oak in Pallet [web S17] |
| Pewter east exit | Boulder Badge | Brock [web S17] |
| Cerulean robbed house | Help Bill | The ticket removes the house guard; Route 5 south and Misty do not need Bill [game] |
| S.S. Anne | S.S. Ticket | From Bill. Captain gives HM01 Cut [game][web S17] |
| Trees (Vermilion Gym, Route 9, Celadon Gym, Route 16 house) | Cut + Cascade Badge | S.S. Anne captain [web S17][web S18] |
| Saffron gates | Any drink | Celadon Department Store roof vending machine [web S9, S17] |
| Ghost Marowak (Pokémon Tower 6F) | Silph Scope, or a Poké Doll to escape it | Silph Scope: Rocket Hideout B4F. Poké Doll: Celadon Mart 4F [game] |
| Snorlax (Routes 12 and 16) | Poké Flute | Mr. Fuji, after the Tower [web S17] |
| Cycling Road | Bicycle | Bike Voucher (Vermilion Fan Club) -> Cerulean Bike Shop [web S17] |
| Water routes | Surf + Soul Badge | Safari Zone secret house (HM03) [game][web S17] |
| Boulders | Strength + Rainbow Badge | Gold Teeth (Safari Zone) -> Warden in Fuchsia (HM04) [game][web S17] |
| Silph Co. locked doors | Card Key | Silph Co. 5F floor [game] |
| Cinnabar Gym | Secret Key | Pokémon Mansion B1F [game] |
| Route 23 guards | All 8 badges | [web S17] |

**Speedrun tricks (only if you want speed)**

- Our bot uses save-and-reset luck tricks (catch Nidoran and Pidgey, the Surge trash cans) and plays at low HP to skip battle sounds [bot]. A normal player does not need them. See the "Speedrun tips" in each part.

## 1. Start, Nidoran and Brock

**Goal**

- Leave home, get a starter, catch a male Nidoran and beat Brock for the Boulder Badge.

**You need**

- Professor Oak is not in his lab at the start. Walk north out of Pallet Town into the tall grass: Oak stops you and walks you to his lab, where you pick your first Pokémon [game].
- Oak's Parcel delivered before the Viridian Mart sells Poké Balls and the road north opens [web S17].
- Boulder Badge (Brock) before the boy at Pewter's east exit lets you pass [web S17].

**Steps**

- Go downstairs and out. Walk north into the grass: Oak stops you and takes you to his lab [web S17].
- Pick **Squirtle**. The rival then picks Bulbasaur [game]. Win the first fight with Tackle [advice].
- Walk north on Route 1 to Viridian City. The Mart clerk gives you **Oak's Parcel**. Walk back and give it to Oak. AI agents often fail this backtrack: the parcel goes south, not north [web S12].
- Go back to the Viridian Mart and buy Poké Balls (bot: 3) [bot] [game].
- Go west from Viridian to **Route 22** and catch a **male Nidoran** in the grass. It is 40% of encounters there, levels 2-4 [game]. Weaken it a little first if you have balls to spare [advice].
- Optional: catch a Pidgey on Route 2 (45% of encounters) for Fly later. Our bot does this [game][bot].
- Go north through Route 2 and **Viridian Forest** to Pewter City. Fight the bug catchers for EXP [advice]. Weedle poisons: carry an Antidote (Viridian Mart) [game][advice].
- Heal at the Pewter Pokémon Center. Then fight Brock [advice].

**Team check**

- For Brock, use **Squirtle with Bubble** (learned at level 8) [game]. Water hits Onix (Rock/Ground) four times as hard [game].
- Safe target: Squirtle level 12 or more [advice]. Our bot beats Brock with Squirtle 10 and Nidoran 8, but dies there in about 1 in 10 games [bot].
- Nidoran learns Horn Attack at level 8 [game]. Level it to 10-12 on the way [advice].

**Fights**

- **Brock:** Geodude L12, Onix L14 (Tackle, Screech, Bide) [game]. When Onix uses Bide it stores damage and hits back double after 2-3 turns. Finish it fast or keep HP high [game][advice].

**Watch out**

- Getting out of the bedroom: the stairs are in the top right corner of Red's room [game].
- Viridian Forest is a small maze. Follow the path north; the exit gate is at the top left [advice].
- Our bot dies here mostly at Brock (59 of 900 games) and in Viridian Forest (28 of 900) [bot]. It plays with very little healing. A careful player who heals before Brock should rarely lose here [advice].

**Speedrun tips**

- The bot saves in Viridian, resets, and presses buttons on exact frames to meet a Nidoran at the first grass tile and catch it with one ball; the same chain then catches a Pidgey on Route 2 [bot].
- It skips the Viridian tree Potion and the early Center only where that keeps the chain working [bot].

**Boss teams (from the game)**

| Trainer | Where | Pokémon (level, speed, moves) |
|---|---|---|
| Rival1 | Oak's Lab | BULBASAUR L5 spd 10 (TACKLE, GROWL) |
| Rival1 | Route 22 | PIDGEY L9 spd 16 (GUST, SAND_ATTACK); BULBASAUR L8 spd 13 (TACKLE, GROWL, LEECH_SEED) |
| Brock | Pewter Gym | GEODUDE L12 spd 11 (TACKLE, DEFENSE_CURL); ONIX L14 spd 26 (TACKLE, SCREECH, BIDE) |

**Our bot here (900 full games, v62)**

| Split | Reached | Died | Death rate | Died at |
|---|---|---|---|---|
| 1 Rival | 900 | 47 | 5.2% | Pallet Rival 47 |
| 2 Nidoran | 799 | 0 | 0.0% | - |
| 3 Brock | 799 | 87 | 10.9% | Brock's Gym 59, Viridian Forest 28 |

Bot team after split 3 (Brock): NIDORAN_M L8 (LEER / TACKLE / HORN_ATTACK), SQUIRTLE L10 (TACKLE / TAIL_WHIP / BUBBLE), PIDGEY L5 (GUST / SAND_ATTACK)

## 2. Route 3 and Mt. Moon

**Goal**

- Cross Route 3, take one fossil, and leave Mt. Moon for Cerulean [game][advice].

**You need**

- Buy Potions, Antidotes and an Escape Rope if affordable; heal HP, PP and status at the entrance Center. No particular starter, Nidoran, stone or TM is required [game][advice].
- Sources: reference/pokered/data/maps/objects/{Route3,Route4,MtMoon1F,MtMoonB1F,MtMoonB2F}.asm, matching headers/scripts, data/trainers/parties.asm and data/wild/maps/. Coordinates are walking squares [game].

**Steps**

- Leave Pewter east onto Route 3. Eight trainers stand at (10,6), (14,4), (16,9), (19,5), (23,4), (22,9), (24,6), (33,10), with sight ranges 2,3,2,1,4,3,3,2. Fight one at a time when healthy; keep PP for the cave [game][advice].
- Route 3 joins western Route 4. Center door (11,5); cave entrance (18,5) -> 1F (14,35). The eastern cave exit is Route 4 (24,5), a different door [game].
- Main route: 1F (5,5) -> B1F (5,5); B1F (21,17) -> main B2F (21,17). This skips optional item branches when a safe path exists [game][advice].
- Mega Punch detour: 1F (17,11) -> B1F (25,9); B1F (17,11) -> B2F (25,9). Return B2F (25,9) -> B1F (17,11); B1F (25,9) -> 1F (17,11). Do not confuse the two B1F ladders [game].
- HP Up branch: 1F (25,15) -> B1F (25,15); B1F (13,27) -> B2F (15,27). Return by the same ladders. The item and its Rocket fight are optional [game][advice].
- Stop at main B2F (12,9), below the Super Nerd at (12,8). Talking up starts battle; stepping on (13,8) also triggers it. After winning, take Dome Fossil (12,6) or Helix Fossil (13,6), with a free bag slot [game][advice].
- After the fossil: B2F (5,7) -> B1F (23,3); B1F (27,3) -> Route 4 (24,5). Go east to Cerulean. Do not restart the cave; fossil flags survive Escape Rope/blackout [game][advice].
- All item balls: 1F Potion (2,20), Moon Stone (2,2), Rare Candy (35,31), Escape Rope (36,23), Potion (20,33), TM12 Water Gun (5,32); B2F HP Up (25,21), TM01 Mega Punch (29,5). Stand beside a visible ball, face it, press A. A full bag leaves it there [game].
- Recorded bot detour: 1F -> B1F -> B2F -> B1F -> 1F -> B1F -> B2F -> B1F -> Route 4. Main route skips the Mega Punch detour. New walks are map-checked, unverified in a game [bot][advice].

**Team check**

- Bulbasaur gets Vine Whip L13; Charmander can use Ember on bugs; Squirtle has Water attacks for Geodude. These are type choices, not guaranteed level targets [game][advice].
- Nidoran male evolves L16; Moon Stone evolves Nidorino only if you have both. The bot leaves with Nidoking L17; this is an example, not a requirement [game][bot][advice].
- Red has no wild Mankey on Routes 3, 4 or 22. Route 5 lists Mankey L10/12/14/16; it is reachable south of Cerulean before Bill or Misty. Mankey is not a Water counter [game][advice].
- Paras is available in Mt. Moon: 1F 5%, B1F 10%, B2F 15%. Catching it for later HMs is optional here [game][advice].

**Fights**

- B2F Rockets: (11,16) Rattata/Zubat L13; (15,22) Sandshrew/Rattata/Zubat L11; (29,11) Zubat/Ekans L12; (29,17) Raticate L16. Sight range 4, facing down/down/up/left. Avoid optional battles only with a checked path [game][advice].
- Super Nerd: Grimer, Voltorb, Koffing L12. Disable, Screech and Smog/poison can upset a damage estimate [game][advice].
- Route 4 Lass (63,3), facing right, range 3, has Paras, Paras and Parasect L31. She is in the Surf-access area; do not seek her for pre-Misty training [game][advice].

**Watch out**

- Poison takes 1 HP every four steps and can black out the team. Cure before a long retreat; compare survival distance. Restore low PP at a Center [game][advice].
- Escape Rope in Red returns to the last healing place (wLastBlackoutMap), not the cave entrance or fossil exit. Look where you arrive, then heal. After blackout, wait for recovery, then read the new town and tile [game][advice].
- Stop after each floor change, text box or unexpected moving person. Map checks are not game verification; all new level targets are untested guesses [advice].

**Speedrun tips**

- The bot's Nidoking and TM detours are examples, not requirements for your starter [bot][advice].

**Boss teams (from the game)**

| Trainer | Where | Pokémon (level, speed, moves) |
|---|---|---|
| SuperNerd | Mt. Moon B2F | GRIMER L12 spd 12 (POUND, DISABLE); VOLTORB L12 spd 30 (TACKLE, SCREECH); KOFFING L12 spd 15 (TACKLE, SMOG) |

**Our bot here (900 full games, v62)**

| Split | Reached | Died | Death rate | Died at |
|---|---|---|---|---|
| 4 Route 3 | 701 | 35 | 5.0% | Shorts Kid 27, Route 3 8 |
| 5 Mt. Moon | 620 | 0 | 0.0% | - |

Bot team after split 5 (Mt. Moon): NIDOKING L17 (HORN_ATTACK / WATER_GUN / MEGA_PUNCH / POISON_STING), SQUIRTLE L10 (TACKLE / TAIL_WHIP / BUBBLE), PIDGEY L5 (GUST / SAND_ATTACK), PARAS L10 (SCRATCH)

## 3. Cerulean, optional Nugget Bridge and Bill, Misty

**Goal**

- Heal in Cerulean and earn Misty's Cascade Badge. Nugget Bridge, Route 25 and Bill are optional for this badge [game][advice].

**You need**

- Cerulean Gym has no Bill or S.S. Ticket check. Keep Bill as a later ticket goal even if Misty is beaten first [game][advice].
- Sources: reference/pokered/data/maps/headers/, objects/, scripts/ for Cerulean City/Gym, Route 24/25 and Bill; data/trainers/parties.asm, data/trainers/special_moves.asm, data/wild/maps/Route24.asm, Route25.asm, data/items/marts.asm [game].

**Steps**

- Route 4 cave exit (24,5) -> eastern ground/ledges -> Cerulean Center city door (19,17). Mart door (25,25); Gym (30,19). New walks are map-checked, unverified in a game [game][advice].
- Heal and check the rival before going north. City (20,6)/(21,6) triggers him when unbeaten. Use his actual recorded starter and current HP/PP; do not follow the bot into battle when weak [game][advice].
- Optional Nugget Bridge south to north: Bug Catcher (11,31), Lass (10,28), Youngster (11,25), Lass (10,22), Jr. Trainer (11,19), Rocket (11,15), whose trigger is (10,15). Another Jr. Trainer is off-bridge at (5,20). Recheck between fights [game][advice].
- Optional Red Oddish is L12-14 in Route 24/25 grass, with Absorb. The usual northern trip crosses the rival and bridge first; bring Balls and a healthy team [game][advice].
- Optional Bill: go east across Route 25 to house door (45,3). Help Bill, use his computer, talk again for the S.S. Ticket, needed later. Return west across Route 25, then south over Route 24 and Nugget Bridge to Cerulean; stop for unbeaten trainers [game][advice].
- Go straight to Misty if ready. Gym bypass: stay left of the Swimmer's row-7 sight, cross row 5, then face the Goldeen trainer on row 3. Fight her, recheck HP/PP, and heal outside if needed before Misty [game][advice].

**Team check**

- Bulbasaur: Vine Whip L13, Ivysaur L16. Healed Ivysaur L20-24 is an untested guess for both fights; actual HP, PP and stats decide [game][advice].
- Charmander/Charmeleon is weak to Water. Oddish with Absorb is a reachable Grass backup; L18-22 is an untested guess, not a guarantee [game][advice].
- Squirtle/Wartortle resists Water, but its Water attacks are resisted back. Wartortle learns Bite L24 (Normal in Red). Wartortle L24+ alone is an untested guess; consider Oddish, levels and Potions [game][advice].
- Butterfree: Confusion L12, Sleep Powder L17; support, not a guaranteed Starmie answer. Pidgey: Sand-Attack L5, Quick Attack L12; not a Water counter [game][advice].
- Nidoran male can use Horn Attack; Nidorino + Moon Stone makes Nidoking, which is weak to Water. Bot Nidoking L25 is measured; L27 with 3+ Potions is an untested guess [game][bot][advice].
- Restore HP/PP, cure status, check party order, bag and money. Three or more Potions for a neutral-damage plan is untested advice. Cerulean Mart: Potion 300, Repel 350, Antidote 100, no Super Potions (first sold in Vermilion). Pewter sells no Repel [game][advice].

**Fights**

- Rival: Pidgeotto L18 (Gust, Sand-Attack, Quick Attack), Abra L15 (Teleport only), Rattata L15 (including Hyper Fang), starter L17. Your Bulbasaur -> his Charmander (Rival1:9); Charmander -> Squirtle (Rival1:7); Squirtle -> Bulbasaur (Rival1:8). His starter is unevolved here [game].
- Two-fight route: Jr. Trainer Goldeen L19 (Peck, Tail Whip, Supersonic), then Misty. Peck is super effective on Grass; Supersonic can confuse. Optional Swimmer: Horsea/Shellder L16, counted too if no checked bypass exists [game][advice].
- Misty: Staryu L18 (Tackle, Water Gun); Starmie L21 (Tackle, Water Gun, BubbleBeam), Speed 56. Grass is super effective, Water is resisted. Choose lead/move using actual stats and PP; carry HP/PP between enemies and fights [game][advice].

**Watch out**

- BubbleBeam can lower Speed; Starmie may move first. Critical hits and misses can overturn an estimate. Healing uses a turn and can still be followed by a hit; levels alone cannot guarantee victory [game][advice].
- Read text and choices before selecting. After blackout, use the new town/tile instead of repeating old cave directions [game][advice].

**Speedrun tips**

- Bot Bill-before-Misty is its route, not a badge gate. All new walks and proposed level targets still need normal-button game tests [bot][advice].

**Boss teams (from the game)**

| Trainer | Where | Pokémon (level, speed, moves) |
|---|---|---|
| Rival1 | Cerulean City | PIDGEOTTO L18 spd 33 (GUST, SAND_ATTACK, QUICK_ATTACK); ABRA L15 spd 34 (TELEPORT); RATTATA L15 spd 29 (TACKLE, TAIL_WHIP, QUICK_ATTACK, HYPER_FANG); SQUIRTLE L17 spd 22 (TACKLE, TAIL_WHIP, BUBBLE, WATER_GUN) |
| Rival1 | Cerulean City | PIDGEOTTO L18 spd 33 (GUST, SAND_ATTACK, QUICK_ATTACK); ABRA L15 spd 34 (TELEPORT); RATTATA L15 spd 29 (TACKLE, TAIL_WHIP, QUICK_ATTACK, HYPER_FANG); BULBASAUR L17 spd 23 (TACKLE, GROWL, LEECH_SEED, VINE_WHIP) |
| Rival1 | Cerulean City | PIDGEOTTO L18 spd 33 (GUST, SAND_ATTACK, QUICK_ATTACK); ABRA L15 spd 34 (TELEPORT); RATTATA L15 spd 29 (TACKLE, TAIL_WHIP, QUICK_ATTACK, HYPER_FANG); CHARMANDER L17 spd 29 (SCRATCH, GROWL, EMBER, LEER) |
| JrTrainerF | Cerulean Gym | GOLDEEN L19 spd 31 (PECK, TAIL_WHIP, SUPERSONIC) |
| Swimmer | Cerulean Gym | HORSEA L16 spd 26 (BUBBLE); SHELLDER L16 spd 20 (TACKLE, WITHDRAW) |
| Misty | Cerulean Gym | STARYU L18 spd 38 (TACKLE, WATER_GUN); STARMIE L21 spd 56 (TACKLE, WATER_GUN, BUBBLEBEAM) |

**Our bot here (900 full games, v62)**

| Split | Reached | Died | Death rate | Died at |
|---|---|---|---|---|
| 6 Bridge | 530 | 22 | 4.2% | Nugget Bridge 21, Cerulean Rival 1 |
| 7 Misty | 452 | 52 | 11.5% | Misty's Gym 47, Nugget Bridge 3, Cerulean Rocket 2 |

Bot team after split 7 (Misty): NIDOKING L25 (HORN_ATTACK / THRASH / MEGA_PUNCH / POISON_STING), SQUIRTLE L10 (TACKLE / TAIL_WHIP / BUBBLE), PIDGEY L5 (GUST / SAND_ATTACK), PARAS L10 (SCRATCH)

## 4. Vermilion, the S.S. Anne and Lt. Surge

**Goal**

- Get **HM01 Cut** on the S.S. Anne and beat **Lt. Surge** for the Thunder Badge.

**You need**

- The S.S. Ticket (from Bill) to board the ship [web S17].
- Cut and the Cascade Badge to cut the small tree in front of the Vermilion Gym [web S17][web S18].

**Steps**

- Leave Cerulean through the robbed house to Route 5. Take the **Underground Path** south to Route 6 [bot]. Do not try the Saffron gates: the guards are thirsty and let no one through yet [web S17].
- In Vermilion, heal and buy **Super Potions** at the Mart [game][advice].
- Board the **S.S. Anne** at the dock. The rival waits on 2F (Pidgeotto L19, Raticate L16, Kadabra L18, Ivysaur L20) [game].
- Go to the **captain's room** at the top of the ship and talk to the captain. He gives **HM01 Cut** [game][web S17]. The ship leaves after you get off [web S17].
- Teach Cut to a helper Pokémon (our bot: Paras from Mt. Moon) [bot]. Cut needs the Cascade Badge [game]. Cut the tree next to the gym.
- In the gym, find two switches hidden in trash cans. The second is usually in a can next to the first, but in Red it can also be in the top-left can. If you pick a wrong can, both switches reset [game][web S17].
- Fight Lt. Surge. He gives **TM24 Thunderbolt** [game]. Teach it to Nidoking [bot].

**Team check**

- Nidoking is part Ground, so Electric moves do nothing to it [game]. Surge is a safe fight for Nidoking [game].
- Our bot's Nidoking is level 28 at Surge [bot]. A careful player: 28 or more [advice].

**Fights**

- **Lt. Surge:** Voltorb L21 (Tackle, Screech, SonicBoom), Pikachu L18, Raichu L24 (Thunderbolt) [game]. SonicBoom always does 20 damage, even to Ground types [game]. Only normal-type hits (Tackle, Quick Attack) and SonicBoom hurt Nidoking [game].
- Our bot dies in this section in 1.5% of games (5 of 336), all on the S.S. Anne, none at Surge [bot].

**Watch out**

- Thrash, Mega Punch and BubbleBeam are enough here [bot].
- Rival fight: Sand-Attack lowers accuracy. Our bot stays in rather than switching (switching costs instant text) [bot].

**Speedrun tips**

- The bot visits the ship before the Mart to keep instant text, and teaches BubbleBeam only after the rival [bot].
- The trash-can puzzle is solved with a save, reset and exact button frames [bot].
- `VOLTORB_RED` (19 Oct): let Voltorb's SonicBoom bring Nidoking to red HP. Red HP skips battle sounds later. In 38 pairs of runs where the switch fired and both runs reached the Tower, it was 17 s faster (95% range 7-26 s), with no clear extra deaths. Not an average over all games [bot].

**Boss teams (from the game)**

| Trainer | Where | Pokémon (level, speed, moves) |
|---|---|---|
| Rival2 | SS Anne 2F | PIDGEOTTO L19 spd 35 (GUST, SAND_ATTACK, QUICK_ATTACK); RATICATE L16 spd 38 (TACKLE, TAIL_WHIP, QUICK_ATTACK, HYPER_FANG); KADABRA L18 spd 45 (TELEPORT, CONFUSION, DISABLE); IVYSAUR L20 spd 32 (TACKLE, GROWL, LEECH_SEED, VINE_WHIP) |
| LtSurge | Vermilion Gym | VOLTORB L21 spd 50 (TACKLE, SCREECH, SONICBOOM); PIKACHU L18 spd 40 (THUNDERSHOCK, GROWL, THUNDER_WAVE, QUICK_ATTACK); RAICHU L24 spd 56 (THUNDERSHOCK, GROWL, THUNDERBOLT) |

**Our bot here (900 full games, v62)**

| Split | Reached | Died | Death rate | Died at |
|---|---|---|---|---|
| 8 Surge | 336 | 5 | 1.5% | S.S. Anne 5 |

Bot team after split 8 (Surge): NIDOKING L28 (HORN_ATTACK / THRASH / MEGA_PUNCH / BUBBLEBEAM), SQUIRTLE L10 (TACKLE / TAIL_WHIP / BUBBLE), PIDGEY L5 (GUST / SAND_ATTACK), PARAS L10 (SCRATCH / CUT / DIG)

## 5. Bicycle, Rock Tunnel, Celadon, Fly and Pokémon Tower

**Goal**

- Get the Bicycle, cross Rock Tunnel, shop in Celadon, get **HM02 Fly**, and rescue Mr. Fuji in Pokémon Tower for the **Poké Flute**.

**You need**

- Bike Voucher from the Fan Club chairman in Vermilion, then the Cerulean Bike Shop gives the **Bicycle** [web S17].
- Cut for the tree on Route 9 (east of Cerulean) and the tree to the Route 16 Fly house [web S17][bot].
- To pass the ghost Marowak on Tower 6F: the **Silph Scope** (Rocket Hideout) or a **Poké Doll** (Celadon Mart 4F) [game].

**Steps**

- In Vermilion, talk to the Fan Club chairman: **Bike Voucher**. Get the Bicycle in Cerulean [web S17].
- Cut the tree east of Cerulean, cross Route 9 to Route 10 and **Rock Tunnel** [web S17]. Rock Tunnel is dark. **HM05 Flash** (Oak's aide in the Route 2 gate, needs 10 Pokémon species caught) lights it, but it is optional. Our bot crosses without Flash [game][bot].
- Lavender Town, then west on Route 8 and the Underground Path to Route 7 and **Celadon City** [bot].
- **Celadon Department Store** [game][bot]: - 2F: TM07 Horn Drill, Super Potions, Revives. - 4F: **Poké Doll**. - Roof vending machine: buy drinks. Give the girl Fresh Water for **TM13 Ice Beam** or Soda Pop for TM48 Rock Slide. Keep **one extra drink for the Saffron guards**. - 5F: X Accuracy, X Speed (useful with Horn Drill).
- Go west from Celadon (cut the tree) to Route 16. The **Fly house** is there: HM02 Fly [game][bot]. Teach it to your flier (our bot: Pidgey). Fly needs the Thunder Badge [game][bot].
- Fly to Lavender. Climb **Pokémon Tower**. The rival waits on 2F [game]. On 5F, step into the purified zone: it heals your whole team for free [game].
- On 6F the ghost Marowak blocks the way. Use the **Poké Doll** in battle to escape it, or fight it with the Silph Scope [game][bot].
- On 7F beat the Rockets, then talk to **Mr. Fuji**. In his house in Lavender he gives the **Poké Flute** [web S17][bot].

**Team check**

- Teach **Thunderbolt** (from Surge) and **Horn Drill** (Celadon). Our bot's Nidoking is level 31 at Fly and 34 at the Flute [bot].
- Horn Drill knocks out in one hit but hits only 30% of the time [game]. With X Accuracy it always hits if your speed is not lower than the target's. It still fails on Ghost types and on a target in the air (Fly) or underground (Dig) [game].

**Fights**

- **Tower rival:** Pidgeotto L25, Gyarados L23, Growlithe L22, Kadabra L20, Ivysaur L25 [game]. Thunderbolt hits Gyarados four times as hard [game].
- Our bot dies in this part in about 10% of the games that reach it (29 of 284: Rock Tunnel, Lavender, Tower) [bot].

**Watch out**

- **Skipping the Rocket Hideout:** the Poké Doll trick avoids the Hideout's spinner-tile maze, which cost Claude Opus 4.5 about 9,000 steps and Gemini days [game][web S2][web S5]. Our bot never enters the Hideout [bot].
- Pokémon Tower: pick up items that block the path. Opus 4.5 did not pick up a Rare Candy blocking it for over an hour [web S2].
- Without the Silph Scope, wild ghosts in the Tower cannot be hit. Run from them [game][advice].
- If you want the Silph Scope anyway: a poster behind a Grunt in the Celadon Game Corner opens the Rocket Hideout. On B4F a Grunt drops the Lift Key: talk to him again after the fight. Beat Giovanni; the Silph Scope is on B4F [web S17][game].

**Speedrun tips**

- Red HP can carry from Surge through Rock Tunnel to the Tower heal zone; it saved about 27 s in the Fly part and 13 s before the heal zone in small samples [bot].
- `LAVENDER_FLOOR`: keep enough HP for two Pidgeotto hits at the Tower rival [bot].

**Boss teams (from the game)**

| Trainer | Where | Pokémon (level, speed, moves) |
|---|---|---|
| Rival2 | Pokémon Tower 2F | PIDGEOTTO L25 spd 44 (GUST, SAND_ATTACK, QUICK_ATTACK, WHIRLWIND); GYARADOS L23 spd 45 (BITE, DRAGON_RAGE, LEER, HYDRO_PUMP); GROWLITHE L22 spd 34 (BITE, ROAR, EMBER); KADABRA L20 spd 50 (TELEPORT, CONFUSION, DISABLE); IVYSAUR L25 spd 39 (GROWL, LEECH_SEED, VINE_WHIP, POISONPOWDER) |

**Our bot here (900 full games, v62)**

| Split | Reached | Died | Death rate | Died at |
|---|---|---|---|---|
| 9 Fly | 284 | 18 | 6.3% | Lavender Town 9, Rock Tunnel 8, Route 9 1 |
| 10 Flute | 221 | 11 | 5.0% | Pokemon Tower 11 |

Bot team after split 10 (Flute): NIDOKING L34 (THUNDERBOLT / HORN_DRILL / ROCK_SLIDE / BUBBLEBEAM), SQUIRTLE L10 (TACKLE / TAIL_WHIP / BUBBLE), PIDGEY L5 (GUST / SAND_ATTACK / FLY), PARAS L10 (SCRATCH / CUT / DIG)

## 6. Silph Co., Snorlax, Safari Zone and Koga

**Goal**

- Free Silph Co. (beat Giovanni), wake Snorlax, ride Cycling Road to Fuchsia, get **Surf** and the **Gold Teeth** in the Safari Zone, and beat **Koga** for the Soul Badge.

**You need**

- **A drink** for the Saffron gate guard (Celadon roof). Not Tea: that is FireRed [web S9][web S17].
- **Card Key** (Silph Co. 5F) for the locked doors in Silph Co. [game].
- **Poké Flute** to wake Snorlax on Route 16; the Bicycle for Cycling Road [web S17].

**Steps**

- Give a drink to the guard in the Route 7 gate (west side of Saffron) [bot][web S17].
- Enter **Silph Co.** (the big building in the middle of Saffron) [web S17].
- Get the **Card Key**: it is an item ball on the floor of **5F** [game]. Our bot reaches it through 9F and back [bot]. **Opus 4.5 spent weeks and 50,000+ steps here because it did not see the Card Key** [web S1].
- Use the Card Key on the locked doors and take the warp tiles to reach the rival on 7F and **Giovanni on 11F**. Our bot's exact path (floors 5F, 9F, 5F, 3F, 7F, 11F) is in `bot_route.json` [bot].
- On 10F pick up **TM26 Earthquake** and a Rare Candy [game]. Teach Earthquake to Nidoking [bot].
- Back in Celadon, go west to Route 16. Play the **Poké Flute** next to Snorlax and beat or run from it [bot][web S17].
- Ride **Cycling Road** (Routes 17-18) south to Fuchsia City [bot].
- **Safari Zone** (costs 500 money): find the **secret house** in the far west area for **HM03 Surf**, and pick up the **Gold Teeth** in the west area (an item ball) [game][web S17]. Free **two** bag slots first: Surf and the Gold Teeth are two new items [game]. You get about 500 steps, so go straight there; our bot's tile path shows the way [game][bot]. Teach Surf to a Water Pokémon (our bot: Squirtle). Surf needs the Soul Badge from Koga [game][bot]. **Opus 4.5 skipped the Gold Teeth and had no Strength until much later** [web S1].
- Fight Koga in the Fuchsia Gym. It has invisible walls: use our bot's tile path for FUCHSIA_GYM [bot].

**Team check**

- Our bot's Nidoking is level 38 at Silph Giovanni and 40 at Koga [bot].
- Carry X Accuracy for Horn Drill, and Ethers/Elixers [bot].

**Fights**

- **Silph rival (7F):** Pidgeot L37, Gyarados L38, Growlithe L35, Alakazam L35, Venusaur L40 [game].
- **Giovanni (11F):** Nidorino L37, Kangaskhan L35, Rhyhorn L37, Nidoqueen L41 [game].
- **Koga:** Koffing L37, Muk L39, Koffing L37, Weezing L43 (Toxic, Selfdestruct) [game]. Weezing can Selfdestruct; our bot's Nidoking often faints that way and still wins [bot].
- Our bot never dies in this part (0 of 197 games that reached it) [bot].

**Watch out**

- Silph Co. has 11 floors and many warp tiles. Write down which warp goes where [advice].
- Opus 4.7 called a door a "conveyor belt" and could not use the Card Key until a later visit [web S1].
- Bag full in the Safari Zone blocked Gemini [web S6].

**Speedrun tips**

- This is also the human world record's route [bot].
- Teach Earthquake at the Cycling Road gate. Cycling Road gives PP Up [bot].
- `SILPH_RED` (keep red HP in Silph) saved only 2.5 s and died 15 of 38 times: off [bot].

**Boss teams (from the game)**

| Trainer | Where | Pokémon (level, speed, moves) |
|---|---|---|
| Rival2 | Silph Co. 7F | PIDGEOT L37 spd 78 (SAND_ATTACK, QUICK_ATTACK, WHIRLWIND, WING_ATTACK); GYARADOS L38 spd 72 (BITE, DRAGON_RAGE, LEER, HYDRO_PUMP); GROWLITHE L35 spd 52 (ROAR, EMBER, LEER, TAKE_DOWN); ALAKAZAM L35 spd 94 (CONFUSION, DISABLE, PSYBEAM, RECOVER); VENUSAUR L40 spd 75 (LEECH_SEED, VINE_WHIP, POISONPOWDER, RAZOR_LEAF) |
| Giovanni | Silph Co. 11F | NIDORINO L37 spd 59 (HORN_ATTACK, POISON_STING, FOCUS_ENERGY, FURY_ATTACK); KANGASKHAN L35 spd 73 (COMET_PUNCH, RAGE, BITE, TAIL_WHIP); RHYHORN L37 spd 29 (HORN_ATTACK, STOMP, TAIL_WHIP); NIDOQUEEN L41 spd 73 (SCRATCH, TAIL_WHIP, BODY_SLAM, POISON_STING) |
| Koga | Fuchsia Gym | KOFFING L37 spd 36 (TACKLE, SMOG, SLUDGE, SMOKESCREEN); MUK L39 spd 50 (DISABLE, POISON_GAS, MINIMIZE, SLUDGE); KOFFING L37 spd 36 (TACKLE, SMOG, SLUDGE, SMOKESCREEN); WEEZING L43 spd 63 (SMOG, SLUDGE, TOXIC, SELFDESTRUCT) |

**Our bot here (900 full games, v62)**

| Split | Reached | Died | Death rate | Died at |
|---|---|---|---|---|
| 11 Silph Giovanni | 197 | 0 | 0.0% | - |
| 12 Koga | 197 | 0 | 0.0% | - |

Bot team after split 12 (Koga): NIDOKING L40 (THUNDERBOLT / HORN_DRILL / EARTHQUAKE / BUBBLEBEAM), SQUIRTLE L10 (TACKLE / TAIL_WHIP / BUBBLE), PIDGEY L5 (GUST / SAND_ATTACK / FLY), PARAS L10 (SCRATCH / CUT / DIG)

## 7. Strength, Cinnabar Mansion and the last badges

**Goal**

- Get **HM04 Strength**, the **Secret Key** in the Pokémon Mansion, and beat **Erika, Blaine, Sabrina and Giovanni**.

**You need**

- Gold Teeth -> the Warden in Fuchsia gives **HM04 Strength** [game][web S17].
- Surf + Soul Badge to reach Cinnabar (Route 21 south from Pallet) [web S17].
- **Secret Key** (Mansion B1F) to open the Cinnabar Gym [game][web S17].
- Cut for the tree in front of the Celadon Gym [web S17].
- Giovanni's gym in Viridian opens after the other 7 badges [web S17].

**Steps**

- Give the Gold Teeth to the Warden (Fuchsia): **HM04 Strength** [game]. Teach it to a helper (our bot: Squirtle). Strength needs the Rainbow Badge from Erika [game][bot].
- Fly to Pallet Town and **Surf south on Route 21** to Cinnabar Island [bot].
- **Pokémon Mansion:** statues are switches that open and close doors. Our bot goes 1F -> 2F -> 3F, drops through a hole back to 1F, then down to B1F [bot]. On B1F pick up **TM14 Blizzard** and the **Secret Key** [game]. **Opus 4.5 needed about 112,000 steps here; it could not link switches to doors** [web S1]. Tip: after pressing a switch, look at which doors changed before you walk on [advice]. Our bot's tile paths for POKEMON_MANSION_1F/2F/3F/B1F show a working way [bot].
- Use Dig or an Escape Rope to leave, fly to Celadon, cut the tree, beat **Erika** [bot].
- Fly to Cinnabar, beat **Blaine** (quiz machines in the gym let you skip trainers) [web S17][bot].
- Beat **Sabrina** in Saffron (warp-tile maze in the gym) [web S17].
- Fly to Viridian and beat **Giovanni** [bot].

**Team check**

- Our bot's Nidoking: level 43 at Erika, 44 at Blaine, 45 at Sabrina, 47 at Giovanni, with Thunderbolt, Horn Drill, Earthquake and Blizzard [bot].
- Safe target: level 45+ before Sabrina, 48+ before Giovanni [advice].

**Fights**

- **Erika:** Victreebel L29, Tangela L24, Vileplume L29 (sleep powders) [game]. Easy with Blizzard / Ice Beam [game][advice].
- **Blaine:** Growlithe L42, Ponyta L40, Rapidash L42, Arcanine L47 (Fire Blast) [game]. Earthquake is super effective [game].
- **Sabrina:** Kadabra L38, Mr. Mime L37, Venomoth L38, Alakazam L43 (Psywave) [game]. Psychic is super effective on Nidoking (part Poison) [game]. Alakazam's speed is 115. In battle your speed gets +1/8 from the Soul Badge, rounded down: a shown speed of 103 becomes 115 (a tie), 104 becomes 117 (you move first) [game]. Our bot dies here in 3% of games [bot].
- **Giovanni:** Rhyhorn L45, Dugtrio L42, Nidoqueen L44, Nidoking L45, Rhydon L50 (Fissure) [game]. Blizzard / Ice Beam and Surf-type moves hit them hard [game][advice].
- **Watch the Blackbelt with Machoke in Giovanni's gym**: it is where our bot dies most in this part (15 of 182 games) [bot].

**Watch out**

- Do not walk past item balls in the Mansion; the Secret Key is one [web S1][game].
- Our bot plays these fights at red HP on purpose. A careful player should heal before each gym [bot][advice].

**Speedrun tips**

- The late plan keeps red HP through a long window of fights and delays healing [bot].
- Skip the Mansion Full Restore only together with the later item rules: 8.5 s saved [bot].
- A heal guard for the Blackbelt never fired because the needed Potions were gone [bot].

**Boss teams (from the game)**

| Trainer | Where | Pokémon (level, speed, moves) |
|---|---|---|
| Erika | Celadon Gym | VICTREEBEL L29 spd 50 (RAZOR_LEAF, WRAP, POISONPOWDER, SLEEP_POWDER); TANGELA L24 spd 37 (CONSTRICT, BIND); VILEPLUME L29 spd 38 (PETAL_DANCE, POISONPOWDER, MEGA_DRAIN, SLEEP_POWDER) |
| Blaine | Cinnabar Gym | GROWLITHE L42 spd 62 (EMBER, LEER, TAKE_DOWN, AGILITY); PONYTA L40 spd 83 (TAIL_WHIP, STOMP, GROWL, FIRE_SPIN); RAPIDASH L42 spd 99 (TAIL_WHIP, STOMP, GROWL, FIRE_SPIN); ARCANINE L47 spd 101 (ROAR, EMBER, FIRE_BLAST, TAKE_DOWN) |
| Sabrina | Saffron Gym | KADABRA L38 spd 90 (DISABLE, PSYBEAM, RECOVER, PSYCHIC_M); MR_MIME L37 spd 77 (CONFUSION, BARRIER, LIGHT_SCREEN, DOUBLESLAP); VENOMOTH L38 spd 79 (POISONPOWDER, LEECH_LIFE, STUN_SPORE, PSYBEAM); ALAKAZAM L43 spd 115 (PSYBEAM, RECOVER, PSYWAVE, REFLECT) |
| Giovanni | Viridian Gym | RHYHORN L45 spd 34 (STOMP, TAIL_WHIP, FURY_ATTACK, HORN_DRILL); DUGTRIO L42 spd 112 (GROWL, DIG, SAND_ATTACK, SLASH); NIDOQUEEN L44 spd 78 (SCRATCH, TAIL_WHIP, BODY_SLAM, POISON_STING); NIDOKING L45 spd 88 (TACKLE, HORN_ATTACK, POISON_STING, THRASH); RHYDON L50 spd 53 (STOMP, TAIL_WHIP, FISSURE, HORN_DRILL) |

**Our bot here (900 full games, v62)**

| Split | Reached | Died | Death rate | Died at |
|---|---|---|---|---|
| 13 Erika | 190 | 1 | 0.5% | Erika's Gym 1 |
| 14 Blaine | 189 | 0 | 0.0% | - |
| 15 Sabrina | 189 | 6 | 3.2% | Sabrina's Gym 6 |
| 16 Giovanni | 182 | 15 | 8.2% | Machoke 15 |

Bot team after split 16 (Giovanni): NIDOKING L47 (THUNDERBOLT / HORN_DRILL / EARTHQUAKE / BLIZZARD), SQUIRTLE L10 (STRENGTH / TAIL_WHIP / BUBBLE / SURF), PIDGEY L5 (GUST / SAND_ATTACK / FLY), PARAS L10 (SCRATCH / CUT / DIG)

## 8. Victory Road and the Pokémon League

**Goal**

- Beat the rival on Route 22, cross **Victory Road**, and beat the Elite Four and the Champion.

**You need**

- All 8 badges for the Route 23 guards [web S17].
- **Strength** (and the Rainbow Badge) for the boulders; **Surf** for Route 23 [web S17].

**Steps**

- West of Viridian, the rival waits on Route 22 (Pidgeot L47, Rhyhorn L45, Gyarados L45, Growlithe L47, Alakazam L50, Venusaur L53) [game][bot].
- Route 23: show your badges to each guard [web S17].
- **Victory Road:** push boulders onto the round switches to open the way. Use Strength first (from the menu), then walk into a boulder to push it [web S17][bot]. Our bot's exact pushes are in `bot_route.json` (VICTORY_ROAD_1F/2F/3F) [bot].
- **Do not use Dig or an Escape Rope halfway**: it resets the boulders [web S1].
- At the Indigo Plateau, heal and buy **Full Restores / Max Potions, Revives and Full Heals** [game][advice].
- Fight Lorelei, Bruno, Agatha, Lance, then the Champion. There is no Center between fights; use items [web S17]. If you lose, you go back to the last Center and must start the Elite Four again [web S17].

**Team check**

- Our bot's Nidoking: level 50 at Lorelei, 55 at the Champion [bot]. It leads with Pidgey so that Nidoking avoids Lorelei's opening move [bot].
- Safe target: Nidoking level 55+, plus at least one backup fighter at 45+ [advice].

**Fights**

- **Lorelei:** Dewgong L54, Cloyster L53, Slowbro L54, Jynx L56, Lapras L56 (Blizzard) [game]. Water and Ice are both strong against Nidoking; Thunderbolt is your best move against the Water Pokémon. Use Earthquake on Jynx (Ice/Psychic): Thunderbolt is not super effective there, and Earthquake is stronger for Nidoking (same-type bonus) [game][advice].
- **Bruno:** Onix L53, Hitmonchan L55, Hitmonlee L55, Onix L56, Machamp L58 (Fissure) [game]. Blizzard / Ice Beam for Onix; Earthquake for Machamp is neutral [game].
- **Agatha:** Gengar L56, Golbat L56, Haunter L55, Arbok L58, Gengar L60 (Toxic) [game]. Earthquake hits Gengar and Arbok hard; Golbat is immune to it [game]. Normal moves cannot hit ghosts [game].
- **Lance:** Gyarados L58, Dragonair L56 (x2), Aerodactyl L60, Dragonite L62 [game]. Blizzard / Ice Beam for the dragons; Thunderbolt for Gyarados [game].
- **Champion:** Pidgeot L61 (Sky Attack), Alakazam L59, Rhydon L61, plus three that depend on your starter. With Squirtle the rival has Gyarados L61, Arcanine L63 and Venusaur L65 (Mega Drain) [game].
- **Our bot dies most at the Champion: 19 of the 130 games that reach him (15%)**. It saves healing items on purpose to set records [bot]. A careful player should heal here [advice].

**Watch out**

- Victory Road boulder switches stopped Claude models for months; one called the switch tile "decoration" [web S1].
- Full Heal does not restore HP [web S5]. Bring Full Restores or Max Potions.
- Opus 4.7 lost a close fight to the Champion, bought healing items and Revives, and won the next try [web S1].

**Speedrun tips**

- Deposit extra Pokémon in the Indigo PC: skipping it looked faster but cost about 7 s at the Hall of Fame [bot].
- Keep X Speed for the Champion. Keep red HP through Bruno only above the set HP limit [bot].
- `YOLO_LANCE` saved only 2.7 s with 13 of 19 deaths: off [bot].

**Boss teams (from the game)**

| Trainer | Where | Pokémon (level, speed, moves) |
|---|---|---|
| Rival2 | Route 22 | PIDGEOT L47 spd 98 (QUICK_ATTACK, WHIRLWIND, WING_ATTACK, AGILITY); RHYHORN L45 spd 34 (STOMP, TAIL_WHIP, FURY_ATTACK, HORN_DRILL); GYARADOS L45 spd 85 (BITE, DRAGON_RAGE, LEER, HYDRO_PUMP); GROWLITHE L47 spd 68 (EMBER, LEER, TAKE_DOWN, AGILITY); ALAKAZAM L50 spd 133 (PSYBEAM, RECOVER, PSYCHIC_M, REFLECT); VENUSAUR L53 spd 98 (VINE_WHIP, POISONPOWDER, RAZOR_LEAF, GROWTH) |
| Lorelei | Indigo Plateau (Elite Four) | DEWGONG L54 spd 89 (GROWL, AURORA_BEAM, REST, TAKE_DOWN); CLOYSTER L53 spd 87 (SUPERSONIC, CLAMP, AURORA_BEAM, SPIKE_CANNON); SLOWBRO L54 spd 46 (GROWL, WATER_GUN, WITHDRAW, AMNESIA); JYNX L56 spd 120 (DOUBLESLAP, ICE_PUNCH, BODY_SLAM, THRASH); LAPRAS L56 spd 81 (BODY_SLAM, CONFUSE_RAY, BLIZZARD, HYDRO_PUMP) |
| Bruno | Indigo Plateau (Elite Four) | ONIX L53 spd 87 (ROCK_THROW, RAGE, SLAM, HARDEN); HITMONCHAN L55 spd 97 (ICE_PUNCH, THUNDERPUNCH, MEGA_PUNCH, COUNTER); HITMONLEE L55 spd 109 (JUMP_KICK, FOCUS_ENERGY, HI_JUMP_KICK, MEGA_KICK); ONIX L56 spd 92 (ROCK_THROW, RAGE, SLAM, HARDEN); MACHAMP L58 spd 78 (LEER, FOCUS_ENERGY, FISSURE, SUBMISSION) |
| Agatha | Indigo Plateau (Elite Four) | GENGAR L56 spd 137 (CONFUSE_RAY, NIGHT_SHADE, HYPNOSIS, DREAM_EATER); GOLBAT L56 spd 114 (SUPERSONIC, CONFUSE_RAY, WING_ATTACK, HAZE); HAUNTER L55 spd 118 (CONFUSE_RAY, NIGHT_SHADE, HYPNOSIS, DREAM_EATER); ARBOK L58 spd 107 (BITE, GLARE, SCREECH, ACID); GENGAR L60 spd 146 (CONFUSE_RAY, NIGHT_SHADE, TOXIC, DREAM_EATER) |
| Lance | Indigo Plateau (Elite Four) | GYARADOS L58 spd 108 (DRAGON_RAGE, LEER, HYDRO_PUMP, HYPER_BEAM); DRAGONAIR L56 spd 92 (AGILITY, SLAM, DRAGON_RAGE, HYPER_BEAM); DRAGONAIR L56 spd 92 (AGILITY, SLAM, DRAGON_RAGE, HYPER_BEAM); AERODACTYL L60 spd 170 (SUPERSONIC, BITE, TAKE_DOWN, HYPER_BEAM); DRAGONITE L62 spd 114 (AGILITY, SLAM, BARRIER, HYPER_BEAM) |
| Rival3 | Indigo Plateau (Champion) | PIDGEOT L61 spd 125 (WHIRLWIND, WING_ATTACK, SKY_ATTACK, MIRROR_MOVE); ALAKAZAM L59 spd 156 (PSYBEAM, RECOVER, PSYCHIC_M, REFLECT); RHYDON L61 spd 63 (TAIL_WHIP, FURY_ATTACK, HORN_DRILL, LEER); GYARADOS L61 spd 113 (DRAGON_RAGE, LEER, HYDRO_PUMP, HYPER_BEAM); ARCANINE L63 spd 134 (ROAR, EMBER, LEER, TAKE_DOWN); VENUSAUR L65 spd 119 (RAZOR_LEAF, GROWTH, MEGA_DRAIN, SOLARBEAM) |

**Our bot here (900 full games, v62)**

| Split | Reached | Died | Death rate | Died at |
|---|---|---|---|---|
| 17 Lorelei | 154 | 0 | 0.0% | - |
| 18 Bruno | 154 | 3 | 1.9% | Bruno 3 |
| 19 Agatha | 151 | 0 | 0.0% | - |
| 20 Lance | 150 | 7 | 4.7% | Lance 7 |
| 21 Champion | 130 | 19 | 14.6% | Blue 19 |

Bot team after split 20 (Lance): PIDGEY L5 (GUST / SAND_ATTACK / FLY), NIDOKING L53 (THUNDERBOLT / HORN_DRILL / EARTHQUAKE / BLIZZARD)

## Puzzle paths (our bot, x/y tiles as stored in game memory)

Each line: map, then the tiles the bot walks and its actions in brackets. Warps show as jumps.

- **VIRIDIAN_FOREST** (part 1, route table): (2,19) [fightWeedle] (1,19) [refForestPotionIf] (1,16) [equipForBrock] (1,5) [equipForBrock] (1,-1)
- **VIRIDIAN_FOREST_NORTH_GATE** (part 1, route table): (4,7) [exitForest] (4,1) (5,1) (5,0)
- **VIRIDIAN_FOREST_SOUTH_GATE** (part 1, replay of the record game): (4,7) (4,2) (5,2) (5,1)
- **MT_MOON_B2F** (part 2, route table): (10,17) [potion] [refMoonPotionMark] (12,17) (12,16) [refMoonMenuCheck] [refCandyEvolve] [refTeach water_gun] [refMoonStone] [refTeach mega_punch] (12,9) [talk Up] [fightGrimer] [refCandyEvolve] [refTeach water_gun] [refMoonStone] [refTeach mega_punch] (13,9) (13,7) [dialogue Up] (13,5) (12,5) (12,4) (3,4) (3,7) (5,7)
- **MT_MOON_B1F** (part 2, route table): (23,3) (27,3)
- **MT_MOON_1F** (part 2, replay of the record game): (14,35) (14,29) (5,29) (5,31) (9,31) (9,29) (14,29) (14,22) (21,22) (21,15) (24,15) (24,16) (25,16) (25,32) (30,32) (30,31) (34,31) (34,23) (35,23) (35,22) (34,22) (34,11) (31,11) (31,3) (25,3) (25,5) (17,5) (17,10)
- **MT_MOON_1F** (part 2, replay of the record game): (17,11) (17,13) (16,13) (16,17) (9,17) (9,16) (8,16) (8,11) (7,11) (7,3) (4,3) (4,2) (3,2) (3,5) (4,5)
- **SS_ANNE_1F** (part 4, route table): (27,0) (27,1) (26,1) (26,7) (2,7) (2,6)
- **SS_ANNE_2F** (part 4, route table): (2,4) (2,11) (3,11) (3,12) (37,12) (37,9) [potion] [refInstantTextLog] (37,8) [rivalSandAttack] (36,8) (36,4)
- **SS_ANNE_CAPTAINS_ROOM** (part 4, route table): (0,7) (0,4) (4,4) (4,3) [talk Up] (4,5) (0,5) (0,7)
- **SS_ANNE_2F** (part 4, route table): (36,4) [guess] (36,12) (3,12) (3,11) (2,11) (2,4)
- **SS_ANNE_1F** (part 4, route table): (2,6) (2,7) (26,7) (26,-1)
- **VERMILION_GYM** (part 4, route table): (3,12) [refSurgeVerify] (4,6) (4,3) (5,3) (5,2) [talk Up] [fightSurge] [split] [tweetSurge] (4,2) (4,13) (5,13) (5,18)
- **ROCK_TUNNEL_1F** (part 5, route table): (15,3) (15,6) (23,6) (23,7) [talk Down] [redbarCubone] (22,7) (22,10) (37,10) (37,3)
- **ROCK_TUNNEL_B1F** (part 5, route table): (33,25) (33,30) (27,30) [talk Left] (27,31) (14,31) (14,29) [potion] [talk Up] [announceOddish] (17,29) (17,24) (25,24) (25,16) (37,16) (37,11) [item repel] [healParalysis] (37,3) (27,3)
- **ROCK_TUNNEL_1F** (part 5, route table): (5,3) (5,9) (11,9) (11,14) (17,14) (17,11)
- **ROCK_TUNNEL_B1F** (part 5, route table): (23,11) (14,11) (14,17) (8,17) (8,10) (7,10) [talk Left] (7,11) (5,11) [item repel] (5,3) (3,3)
- **ROCK_TUNNEL_1F** (part 5, route table): (37,17) (32,17) (32,23) (37,23) (37,28) (28,28) (26,24) (23,24) [talk Left] (23,27) (15,27) (15,33)
- **POKEMON_TOWER_1F** (part 5, route table): (10,17) (10,10) (18,10) (18,9)
- **POKEMON_TOWER_2F** (part 5, route table): (18,9) (18,7) (16,7) (16,5) (15,5) [lavenderRival] (5,5) (5,8) (3,8) (3,9)
- **POKEMON_TOWER_3F** (part 5, route table): (3,9) (3,10) (6,10) (6,13) (8,13) (8,6) (17,6) (17,9) (18,9)
- **POKEMON_TOWER_4F** (part 5, route table): (18,9) (18,7) (16,7) [talk Left] [digFight] (16,9) (14,9) (14,10) (13,10) [take Left] (14,10) (14,8) (11,8) (11,9) (10,9) (10,12) (7,12) (7,11) (4,11) (4,10) (3,10) (3,9)
- **POKEMON_TOWER_5F** (part 5, route table): (3,9) (4,9) (4,11) [take Down] (4,6) (13,6) (13,9) (9,9) (9,12) (14,12) (14,10) (18,10) (18,9)
- **POKEMON_TOWER_6F** (part 5, route table): (18,9) (18,7) (15,7) (15,3) (11,3) (11,5) (10,5) [interact Left] (10,6) (6,6) (6,7) [interact Down] (6,14) (10,14) (10,16) [pokeDoll] (9,16)
- **POKEMON_TOWER_7F** (part 5, route table): (9,16) (10,16) (10,9) [fightX] (10,7) [thunderboltFirst] (10,4) [interact Up]
- **SILPH_CO_1F** (part 6, route table): (10,17) (10,13) (26,13) (26,0)
- **SILPH_CO_2F** (part 6, route table): (24,1) (26,1) (26,0)
- **SILPH_CO_3F** (part 6, route table): (26,1) (24,1) (24,0)
- **SILPH_CO_4F** (part 6, route table): (24,1) (26,1) (26,0)
- **SILPH_CO_5F** (part 6, route table): (26,1) (26,3) (13,3) [refFreeSlot] [refHidden elixer Left] (13,4) (8,4) (8,15) [talk Down] [refFightX horn_drill] (9,15)
- **SILPH_CO_9F** (part 6, route table): (17,15) (17,14) (17,15)
- **SILPH_CO_5F** (part 6, route table): (9,15) (9,16) (20,16) [take Right] (9,16) (9,15)
- **SILPH_CO_9F** (part 6, route table): (17,15) (17,14) (17,15)
- **SILPH_CO_5F** (part 6, route table): (9,15) (9,13) (8,13) [interact Left] (6,13) (6,16) (3,16) (3,15)
- **SILPH_CO_3F** (part 6, route table): (3,15) (4,15) (18,15) (18,9) [interact Left] (16,9) (16,11) (11,11)
- **SILPH_CO_7F** (part 6, route table): (5,3) (5,2) (4,2) (3,2) [silphRival] (3,7) (5,7)
- **SILPH_CO_11F** (part 6, route table): (3,2) [refRestorePP] (2,2) (2,16) [talk Right] [refFightX horn_drill] (2,15) (6,15) [refRecoveryPotion] (6,14) [interact Up] (6,13) [fightX] [fightSilphGiovanni] [split] (6,14) (3,14) (3,2)
- **SILPH_CO_7F** (part 6, route table): (5,7) (4,7) (3,7) (3,3) (4,3) (5,3)
- **SILPH_CO_3F** (part 6, route table): (11,11) (12,11) (16,11) (16,9) (18,9) (18,7) (20,7) (20,0)
- **SILPH_CO_ELEVATOR** (part 6, route table): (1,3) (1,2) (3,2) (3,1) [refSilphElevator] (2,1) (2,4)
- **SILPH_CO_9F** (part 6, route table): (18,1) (14,1) (14,0)
- **SILPH_CO_10F** (part 6, route table): (8,1) (3,1) (3,9) (1,9) (1,12) [take Right] (1,13) (1,15) (3,15) (3,14) [take Right] [skill dig]
- **SAFARI_ZONE_GATE** (part 6, route table): (3,5) (3,2) (4,2) [dialogue Right]
- **SAFARI_ZONE_CENTER** (part 6, route table): (15,25) [bicycle] (15,16) (28,16) (28,11) (30,11)
- **SAFARI_ZONE_EAST** (part 6, route table): (0,23) (4,23) (4,24) (20,24) (20,20) (12,20) (12,22) (11,22) (10,22) [item super_repel] [tossInSafari] [item carbos] (9,22) (9,8) (12,8) (12,6) (17,6) (17,8) (20,8) (20,3) (7,3) (7,5) (-1,5)
- **SAFARI_ZONE_NORTH** (part 6, route table): (39,31) (22,31) (22,22) (16,22) (16,28) (13,28) (13,9) (28,9) (28,3) (3,3) (3,36)
- **SAFARI_ZONE_WEST** (part 6, route table): (21,0) (21,5) (19,5) (19,6) [interact Down] (19,5) (7,5) (7,6) (3,6) (3,3)
- **SAFARI_ZONE_SECRET_HOUSE** (part 6, route table): (2,7) (2,6) (3,6) (3,4) [talk Up] (3,8)
- **SAFARI_ZONE_WEST** (part 6, route table): (3,4) [skill dig]
- **FUCHSIA_GYM** (part 6, route table): (4,17) (4,16) (9,16) (9,9) (7,9) [talk Up] (9,9) (9,1) (1,1) (1,2) [elixer earthquake] [potionBeforeHypno] (1,3) (2,3) (2,5) (1,5) (1,7) [fightHypno] (1,9) (2,9) [elixer earthquake] (4,9) [talk Down] [fightKoga] [split] (1,9) (1,5) (2,5) (2,3) (1,3) (1,1) (9,1) (9,16) (5,16) (5,18)
- **POKEMON_MANSION_1F** (part 7, route table): (5,27) (5,10)
- **POKEMON_MANSION_2F** (part 7, route table): (5,11) (10,11) (10,5) (6,5) (6,1)
- **POKEMON_MANSION_3F** (part 7, route table): (6,2) (11,2) (11,6) (10,6) [dialogue Up] (14,6) (14,11) (16,11) (16,14)
- **POKEMON_MANSION_1F** (part 7, route table): (16,14) (16,16) (13,16) (13,20) (21,20) (21,23)
- **POKEMON_MANSION_B1F** (part 7, route table): (23,22) (23,15) (21,15) [item super_repel] [item carbos] (17,15) (17,19) (18,19) (18,23) (17,23) (17,26) (18,26) [dialogue Up] (19,26) [take Up] [refTeach blizzard] (14,26) (14,22) (12,22) (12,15) (24,15) (24,18) (26,18) (26,6) (24,6) (24,4) (20,4) [dialogue Up] (24,4) (24,6) (12,6) (12,7) (4,7) (4,9) (5,9) (5,10) [teach strength] [refTeach blizzard] [refMakeSpace] [item rare_candy] (5,12) [take Down] (5,12) [skill dig]
- **CELADON_GYM** (part 7, route table): (4,17) (4,16) (1,16) (1,9) (0,9) (0,4) (1,4) [skill cut] (4,4) [talk Up] [fightErika] [split] (5,4) (5,6) [skill cut Down] (5,18)
- **CINNABAR_GYM** (part 7, route table): (16,17) (16,14) (18,14) (18,10) (15,10) (15,8) [dialogue Up] (16,8) (16,7) (18,7) (18,1) (12,1) (12,2) (10,2) [dialogue Up] (12,2) (12,7) (10,7) (10,8) (9,8) [dialogue Up] (9,11) (12,11) (12,13) (10,13) (10,14) (9,14) [dialogue Up] (9,16) (1,16) (1,14) [dialogue Up] (2,14) (2,13) (4,13) (4,9) (1,9) (1,8) [dialogue Up] (2,8) (2,7) (4,7) (4,5) (3,5) (3,4) [talk Up] [refFightX horn_drill] [split] [skill dig]
- **SAFFRON_GYM** (part 7, route table): (8,17) (8,16) (11,16) (11,15) (16,17) (16,15) (15,15) (18,3) (18,5) (15,5) (1,5) (11,11) (11,8) (10,8) [waitToFight Left] [split] (11,8) (11,11) [refSabrinaNoElixer] [skill dig]
- **VIRIDIAN_GYM** (part 7, route table): (16,17) (16,16) (14,16) (14,9) (13,9) (13,7) (15,7) (15,4) (12,4) (12,5) (10,5) (10,4) [fightGiovanniMachoke] (10,5) (13,5) (13,4) (15,4) (15,7) (13,7) (13,11) (14,11) (14,16) (16,16) (16,18)
- **VIRIDIAN_GYM** (part 7, route table): (16,17) (16,16) (14,16) (14,9) (13,9) (13,7) (15,7) (15,4) (12,4) (12,5) (10,5) (10,2) (7,2) (7,4) (2,4) [checkGiovanni] (2,2) [talk Up] [fightGiovanni] [split] (2,4) (7,4) (7,2) (10,2) (10,5) (12,5) (12,4) (15,4) (15,7) (13,7) (13,11) (14,11) (14,16) (16,16) (16,18)
- **VICTORY_ROAD_1F** (part 8, route table): (8,17) [tweetVictoryRoad] (8,16) (4,16) (4,14) (5,14) [skill strength] (5,15) (4,15) (4,16) (7,16) [push Right] (7,17) (9,17) (9,15) (8,15) (8,14) (15,14) (15,15) (16,15) (16,14) [push Up] (14,14) (14,12) (16,12) (16,11) (17,11) (17,12) (14,12) (14,14) (8,14) (8,16) (5,16) (5,12) (11,12) (11,6) (7,6) (7,8) (3,8) (3,5) (2,5) (2,1) (1,1)
- **VICTORY_ROAD_2F** (part 8, route table): (0,8) (0,9) (3,9) (3,13) (5,13) (5,14) [item super_repel] [skill strength] (4,14) (4,13) (3,13) (3,15) (4,15) (4,16) (3,16) [push Left] (3,11) (5,11) (5,8) (14,8) (14,14) (21,14) (21,16) (28,16) (28,11) (23,11) (23,7)
- **VICTORY_ROAD_3F** (part 8, route table): (23,7) (23,6) (22,6) (22,4) [skill strength] (22,2) (23,2) (23,1) (7,1) (7,0) (6,0) (6,1) (7,1) (7,2) (3,2) (3,1) (2,1) (2,4) (1,4) (1,5) (2,5) (2,4) (4,4) (4,2) (7,2) (7,1) (20,1) (20,6) (17,6) (17,4) (9,4) (9,10) (5,10) (5,8) (1,8) (1,15) (11,15) (11,16) (20,16) (20,15) (23,15)
- **VICTORY_ROAD_2F** (part 8, route table): (22,16) [item super_repel] [potionBeforeLorelei] [skill strength] [bicycle] (22,17) (24,17) (24,16) (11,16) [push Left] (21,16) (21,14) (25,14)
- **VICTORY_ROAD_3F** (part 8, route table): (27,15) (27,8) (26,8)
- **VICTORY_ROAD_2F** (part 8, route table): (27,7) (30,7)
