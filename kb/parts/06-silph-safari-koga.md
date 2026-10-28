---
id: 6
title: Silph Co., Snorlax, Safari Zone and Koga
splits: 11, 12
bosses: Rival2:8, Giovanni:2, Koga:1
maps: LAVENDER_TOWN, CELADON_CITY, CELADON_POKECENTER, ROUTE_7, ROUTE_7_GATE, SAFFRON_CITY, SAFFRON_POKECENTER, SILPH_CO_1F, SILPH_CO_2F, SILPH_CO_3F, SILPH_CO_4F, SILPH_CO_5F, SILPH_CO_6F, SILPH_CO_7F, SILPH_CO_8F, SILPH_CO_9F, SILPH_CO_10F, SILPH_CO_11F, SILPH_CO_ELEVATOR, ROUTE_16, ROUTE_16_GATE_1F, ROUTE_17, ROUTE_18, ROUTE_18_GATE_1F, FUCHSIA_CITY, FUCHSIA_POKECENTER, FUCHSIA_MART, SAFARI_ZONE_GATE, SAFARI_ZONE_CENTER, SAFARI_ZONE_EAST, SAFARI_ZONE_NORTH, SAFARI_ZONE_WEST, SAFARI_ZONE_SECRET_HOUSE, FUCHSIA_GYM
---
## Goal

Free Silph Co. (beat Giovanni), wake Snorlax, ride Cycling Road to Fuchsia, get **Surf** and the **Gold Teeth** in the
Safari Zone, and beat **Koga** for the Soul Badge.

## You need

- **A drink** for the Saffron gate guard (Celadon roof). Not Tea: that is FireRed [web S9][web S17].
- **Card Key** (Silph Co. 5F) for the locked doors in Silph Co. [game].
- **Poké Flute** to wake Snorlax on Route 16; the Bicycle for Cycling Road [web S17].

## Steps

1. Give a drink to the guard in the Route 7 gate (west side of Saffron) [bot][web S17].
2. Enter **Silph Co.** (the big building in the middle of Saffron) [web S17].
3. Get the **Card Key**: it is an item ball on the floor of **5F** [game]. Our bot reaches it through 9F and back [bot].
   **Opus 4.5 spent weeks and 50,000+ steps here because it did not see the Card Key** [web S1].
4. Use the Card Key on the locked doors and take the warp tiles to reach the rival on 7F and **Giovanni on 11F**.
   Our bot's exact path (floors 5F, 9F, 5F, 3F, 7F, 11F) is in `bot_route.json` [bot].
5. On 10F pick up **TM26 Earthquake** and a Rare Candy [game]. Teach Earthquake to Nidoking [bot].
6. Back in Celadon, go west to Route 16. Play the **Poké Flute** next to Snorlax and beat or run from it [bot][web S17].
7. Ride **Cycling Road** (Routes 17-18) south to Fuchsia City [bot].
8. **Safari Zone** (costs 500 money): find the **secret house** in the far west area for **HM03 Surf**, and pick up the
   **Gold Teeth** in the west area (an item ball) [game][web S17]. Free **two** bag slots first: Surf and the Gold Teeth
   are two new items [game]. You get about 500 steps, so go straight there; our bot's tile path shows the way [game][bot].
   Teach Surf to a Water Pokémon (our bot: Squirtle). Surf needs the Soul Badge from Koga [game][bot].
   **Opus 4.5 skipped the Gold Teeth and had no Strength until much later** [web S1].
9. Fight Koga in the Fuchsia Gym. It has invisible walls: use our bot's tile path for FUCHSIA_GYM [bot].

## Team check

- Our bot's Nidoking is level 38 at Silph Giovanni and 40 at Koga [bot].
- Carry X Accuracy for Horn Drill, and Ethers/Elixers [bot].

## Fights

- **Silph rival (7F):** Pidgeot L37, Gyarados L38, Growlithe L35, Alakazam L35, Venusaur L40 [game].
- **Giovanni (11F):** Nidorino L37, Kangaskhan L35, Rhyhorn L37, Nidoqueen L41 [game].
- **Koga:** Koffing L37, Muk L39, Koffing L37, Weezing L43 (Toxic, Selfdestruct) [game].
  Weezing can Selfdestruct; our bot's Nidoking often faints that way and still wins [bot].
- Our bot never dies in this part (0 of 197 games that reached it) [bot].

## Watch out

- Silph Co. has 11 floors and many warp tiles. Write down which warp goes where [advice].
- Opus 4.7 called a door a "conveyor belt" and could not use the Card Key until a later visit [web S1].
- Bag full in the Safari Zone blocked Gemini [web S6].

## Speedrun tips

- This is also the human world record's route [bot].
- Teach Earthquake at the Cycling Road gate. Cycling Road gives PP Up [bot].
- `SILPH_RED` (keep red HP in Silph) saved only 2.5 s and died 15 of 38 times: off [bot].
