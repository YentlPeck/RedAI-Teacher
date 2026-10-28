---
id: 0
title: How to beat Pokémon Red (general rules)
splits:
bosses:
maps:
---
## Tags

Every line ends with a tag that says how we know it:
- [game] read from the game's own code (pokered disassembly). Certain.
- [bot] measured in our bot's recorded games (`teacher/kb/bot_stats.json`). Certain for our bot; our bot plays risky.
- [web] from online sources, listed in `docs/teacher/research/AI_AGENTS_WEB_2026-10-19.md` (S1-S18).
- [advice] our advice. Makes sense, but not tested yet.

## The plan in one line

Pick Squirtle, catch a male Nidoran on Route 22, make it a Nidoking with the Moon Stone in Mt. Moon, and teach it
strong TMs. Our bot's best live run with this plan is 1:46:57 (official time); a typical finish is about 1:51 (median 1:50:42 bot clock, 102 finishes in 900 full games) [bot]. A careful player can use the same plan with more
levels and more healing [advice].

## Team

- **Nidoking does almost all the fighting.** In our bot's finished games it is the only Pokémon above level 10 [bot].
- Nidoking's final moves in our bot: Thunderbolt, Horn Drill, Earthquake, Blizzard [bot].
  For a careful player, Ice Beam (Celadon roof, give Fresh Water) is safer than Blizzard: listed accuracy 100% vs 90%. In Red, normal moves with 100% listed accuracy still miss 1 time in 256 (Swift and X Accuracy skip this check) [game].
- Helpers that only use field moves: Squirtle (Surf, Strength), Pidgey (Fly), Paras (Cut, Dig) [bot].
  A normal player can level a second fighter as a backup. Recommended, not required [advice].
- Catch the helpers on the way: a flier (Pidgey, Route 2), Paras (Mt. Moon) for Cut, a Water Pokémon for Surf and Strength [game][bot].
- **Teach each HM before you need it.** Owning it is not enough. To use it outside battle you need a badge: Cut = Cascade
  (Misty), Fly = Thunder (Surge), Surf = Soul (Koga), Strength = Rainbow (Erika), Flash = Boulder (Brock) [game].
- Nidoking is weak to Water, Ground, Ice and Psychic [game]. The big danger fights are Misty (Water) and
  Sabrina (Psychic) [game]. Our bot dies most at Misty, Brock and the Champion [bot].

## Healing and items

- Heal at every Pokémon Center you pass if HP is below half [advice].
- Full Heal cures status only (poison, sleep, ...). It does **not** restore HP. Gemini lost ~100 hours at the
  Elite Four believing it did [web S5].
- Keep 1-2 free bag slots. The bag holds 20 item types. A full bag blocks key items (Gemini failed in the Safari Zone) [game][web S6].
- Never throw away key items, HMs or TMs you still plan to use [advice].
- X Accuracy, X Speed and other X items each cost one turn, and switching Pokémon removes their effect. Use them only
  when your HP is safe [game][advice].
- Ethers and Elixers cannot be bought. Pick them up and save them for the League: S.S. Anne has an Ether and a Max Ether,
  Pokémon Tower 4F an Elixer [game]. Check your PP before the Elite Four [advice].
- Before the Elite Four, buy Full Restores / Max Potions and Revives at the Indigo Plateau shop [game][advice].

## Finding the way (where AI agents lose the most time)

- Battles are rarely the problem. Mazes, items on the floor, boulder puzzles and missed story steps are [web S1, S2, S4].
- Always look for item balls on the floor and pick them up. Key items like the Card Key are just items on the floor [web S1].
- If you are stuck for long, leave the area and come back later. Write down what you tried [web S2].
- Do not trust notes you wrote earlier without checking. One wrong note can stall a run for days [web S2].
- Red is not FireRed. In Red you give a **drink** (not Tea) to the Saffron guards [web S9][game].
- Do not use Dig or an Escape Rope in the middle of a boulder puzzle: it resets the boulders [web S1].
- Boulders can only be pushed, never pulled. Plan the push before you start [game][advice].
- For mazes and puzzles the tool can give our bot's exact tile path (x, y as stored in game memory) [bot].

## Story checklist (what opens the way)

| Gate | What you need | Where to get it |
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

## Speedrun tricks (only if you want speed)

Our bot uses save-and-reset luck tricks (catch Nidoran and Pidgey, the Surge trash cans) and plays at low HP to
skip battle sounds [bot]. A normal player does not need them. See the "Speedrun tips" in each part.
