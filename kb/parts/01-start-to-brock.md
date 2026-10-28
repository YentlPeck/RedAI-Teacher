---
id: 1
title: Start, Nidoran and Brock
splits: 1, 2, 3
bosses: Rival1:2, Rival1:5, Brock:1
maps: REDS_HOUSE_2F, REDS_HOUSE_1F, PALLET_TOWN, OAKS_LAB, ROUTE_1, VIRIDIAN_CITY, VIRIDIAN_MART, VIRIDIAN_POKECENTER, ROUTE_22, ROUTE_2, VIRIDIAN_FOREST_SOUTH_GATE, VIRIDIAN_FOREST, VIRIDIAN_FOREST_NORTH_GATE, PEWTER_CITY, PEWTER_POKECENTER, PEWTER_MART, PEWTER_GYM
---
## Goal

Leave home, get a starter, catch a male Nidoran and beat Brock for the Boulder Badge.

## You need

- Professor Oak is not in his lab at the start. Walk north out of Pallet Town into the tall grass: Oak stops you
  and walks you to his lab, where you pick your first Pokémon [game].
- Oak's Parcel delivered before the Viridian Mart sells Poké Balls and the road north opens [web S17].
- Boulder Badge (Brock) before the boy at Pewter's east exit lets you pass [web S17].

## Steps

1. Go downstairs and out. Walk north into the grass: Oak stops you and takes you to his lab [web S17].
2. Pick **Squirtle**. The rival then picks Bulbasaur [game]. Win the first fight with Tackle [advice].
3. Walk north on Route 1 to Viridian City. The Mart clerk gives you **Oak's Parcel**. Walk back and give it to Oak.
   AI agents often fail this backtrack: the parcel goes south, not north [web S12].
4. Go back to the Viridian Mart and buy Poké Balls (bot: 3) [bot] [game].
5. Go west from Viridian to **Route 22** and catch a **male Nidoran** in the grass. It is 40% of encounters there,
   levels 2-4 [game]. Weaken it a little first if you have balls to spare [advice].
6. Optional: catch a Pidgey on Route 2 (45% of encounters) for Fly later. Our bot does this [game][bot].
7. Go north through Route 2 and **Viridian Forest** to Pewter City. Fight the bug catchers for EXP [advice].
   Weedle poisons: carry an Antidote (Viridian Mart) [game][advice].
8. Heal at the Pewter Pokémon Center. Then fight Brock [advice].

## Team check

- For Brock, use **Squirtle with Bubble** (learned at level 8) [game]. Water hits Onix (Rock/Ground) four times as hard [game].
- Safe target: Squirtle level 12 or more [advice]. Our bot beats Brock with Squirtle 10 and Nidoran 8, but dies there in about 1 in 10 games [bot].
- Nidoran learns Horn Attack at level 8 [game]. Level it to 10-12 on the way [advice].

## Fights

- **Brock:** Geodude L12, Onix L14 (Tackle, Screech, Bide) [game]. When Onix uses Bide it stores damage and hits back
  double after 2-3 turns. Finish it fast or keep HP high [game][advice].

## Watch out

- Getting out of the bedroom: the stairs are in the top right corner of Red's room [game].
- Viridian Forest is a small maze. Follow the path north; the exit gate is at the top left [advice].
- Our bot dies here mostly at Brock (59 of 900 games) and in Viridian Forest (28 of 900) [bot]. It plays with very
  little healing. A careful player who heals before Brock should rarely lose here [advice].

## Speedrun tips

- The bot saves in Viridian, resets, and presses buttons on exact frames to meet a Nidoran at the first grass tile
  and catch it with one ball; the same chain then catches a Pidgey on Route 2 [bot].
- It skips the Viridian tree Potion and the early Center only where that keeps the chain working [bot].
