---
id: 8
title: Victory Road and the Pokémon League
splits: 17, 18, 19, 20, 21
bosses: Rival2:11, Lorelei:1, Bruno:1, Agatha:1, Lance:1, Rival3:2
maps: VIRIDIAN_CITY, ROUTE_22, ROUTE_22_GATE, ROUTE_23, VICTORY_ROAD_1F, VICTORY_ROAD_2F, VICTORY_ROAD_3F, INDIGO_PLATEAU, INDIGO_PLATEAU_LOBBY, LORELEIS_ROOM, BRUNOS_ROOM, AGATHAS_ROOM, LANCES_ROOM, CHAMPIONS_ROOM, HALL_OF_FAME
---
## Goal

Beat the rival on Route 22, cross **Victory Road**, and beat the Elite Four and the Champion.

## You need

- All 8 badges for the Route 23 guards [web S17].
- **Strength** (and the Rainbow Badge) for the boulders; **Surf** for Route 23 [web S17].

## Steps

1. West of Viridian, the rival waits on Route 22 (Pidgeot L47, Rhyhorn L45, Gyarados L45, Growlithe L47, Alakazam L50, Venusaur L53) [game][bot].
2. Route 23: show your badges to each guard [web S17].
3. **Victory Road:** push boulders onto the round switches to open the way. Use Strength first (from the menu), then
   walk into a boulder to push it [web S17][bot]. Our bot's exact pushes are in `bot_route.json` (VICTORY_ROAD_1F/2F/3F) [bot].
4. **Do not use Dig or an Escape Rope halfway**: it resets the boulders [web S1].
5. At the Indigo Plateau, heal and buy **Full Restores / Max Potions, Revives and Full Heals** [game][advice].
6. Fight Lorelei, Bruno, Agatha, Lance, then the Champion. There is no Center between fights; use items [web S17].
   If you lose, you go back to the last Center and must start the Elite Four again [web S17].

## Team check

- Our bot's Nidoking: level 50 at Lorelei, 55 at the Champion [bot]. It leads with Pidgey so that Nidoking avoids
  Lorelei's opening move [bot].
- Safe target: Nidoking level 55+, plus at least one backup fighter at 45+ [advice].

## Fights

- **Lorelei:** Dewgong L54, Cloyster L53, Slowbro L54, Jynx L56, Lapras L56 (Blizzard) [game]. Water and Ice are both
  strong against Nidoking; Thunderbolt is your best move against the Water Pokémon. Use Earthquake on Jynx (Ice/Psychic): Thunderbolt is not
  super effective there, and Earthquake is stronger for Nidoking (same-type bonus) [game][advice].
- **Bruno:** Onix L53, Hitmonchan L55, Hitmonlee L55, Onix L56, Machamp L58 (Fissure) [game]. Blizzard / Ice Beam for
  Onix; Earthquake for Machamp is neutral [game].
- **Agatha:** Gengar L56, Golbat L56, Haunter L55, Arbok L58, Gengar L60 (Toxic) [game]. Earthquake hits Gengar and
  Arbok hard; Golbat is immune to it [game]. Normal moves cannot hit ghosts [game].
- **Lance:** Gyarados L58, Dragonair L56 (x2), Aerodactyl L60, Dragonite L62 [game]. Blizzard / Ice Beam for the dragons;
  Thunderbolt for Gyarados [game].
- **Champion:** Pidgeot L61 (Sky Attack), Alakazam L59, Rhydon L61, plus three that depend on your starter. With
  Squirtle the rival has Gyarados L61, Arcanine L63 and Venusaur L65 (Mega Drain) [game].
- **Our bot dies most at the Champion: 19 of the 130 games that reach him (15%)**. It saves healing items on purpose to
  set records [bot]. A careful player should heal here [advice].

## Watch out

- Victory Road boulder switches stopped Claude models for months; one called the switch tile "decoration" [web S1].
- Full Heal does not restore HP [web S5]. Bring Full Restores or Max Potions.
- Opus 4.7 lost a close fight to the Champion, bought healing items and Revives, and won the next try [web S1].

## Speedrun tips

- Deposit extra Pokémon in the Indigo PC: skipping it looked faster but cost about 7 s at the Hall of Fame [bot].
- Keep X Speed for the Champion. Keep red HP through Bruno only above the set HP limit [bot].
- `YOLO_LANCE` saved only 2.7 s with 13 of 19 deaths: off [bot].
