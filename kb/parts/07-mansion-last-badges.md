---
id: 7
title: Strength, Cinnabar Mansion and the last badges
splits: 13, 14, 15, 16
bosses: Erika:1, Blaine:1, Sabrina:1, Giovanni:3
maps: FUCHSIA_CITY, WARDENS_HOUSE, PALLET_TOWN, ROUTE_21, CINNABAR_ISLAND, CINNABAR_POKECENTER, CINNABAR_MART, POKEMON_MANSION_1F, POKEMON_MANSION_2F, POKEMON_MANSION_3F, POKEMON_MANSION_B1F, CELADON_CITY, CELADON_GYM, CINNABAR_GYM, ROUTE_7, ROUTE_7_GATE, SAFFRON_CITY, SAFFRON_GYM, VIRIDIAN_CITY, VIRIDIAN_GYM
---
## Goal

Get **HM04 Strength**, the **Secret Key** in the Pokémon Mansion, and beat **Erika, Blaine, Sabrina and Giovanni**.

## You need

- Gold Teeth -> the Warden in Fuchsia gives **HM04 Strength** [game][web S17].
- Surf + Soul Badge to reach Cinnabar (Route 21 south from Pallet) [web S17].
- **Secret Key** (Mansion B1F) to open the Cinnabar Gym [game][web S17].
- Cut for the tree in front of the Celadon Gym [web S17].
- Giovanni's gym in Viridian opens after the other 7 badges [web S17].

## Steps

1. Give the Gold Teeth to the Warden (Fuchsia): **HM04 Strength** [game]. Teach it to a helper (our bot: Squirtle).
   Strength needs the Rainbow Badge from Erika [game][bot].
2. Fly to Pallet Town and **Surf south on Route 21** to Cinnabar Island [bot].
3. **Pokémon Mansion:** statues are switches that open and close doors. Our bot goes 1F -> 2F -> 3F, drops through a
   hole back to 1F, then down to B1F [bot]. On B1F pick up **TM14 Blizzard** and the **Secret Key** [game].
   **Opus 4.5 needed about 112,000 steps here; it could not link switches to doors** [web S1].
   Tip: after pressing a switch, look at which doors changed before you walk on [advice]. Our bot's tile paths for
   POKEMON_MANSION_1F/2F/3F/B1F show a working way [bot].
4. Use Dig or an Escape Rope to leave, fly to Celadon, cut the tree, beat **Erika** [bot].
5. Fly to Cinnabar, beat **Blaine** (quiz machines in the gym let you skip trainers) [web S17][bot].
6. Beat **Sabrina** in Saffron (warp-tile maze in the gym) [web S17].
7. Fly to Viridian and beat **Giovanni** [bot].

## Team check

- Our bot's Nidoking: level 43 at Erika, 44 at Blaine, 45 at Sabrina, 47 at Giovanni, with Thunderbolt, Horn Drill,
  Earthquake and Blizzard [bot].
- Safe target: level 45+ before Sabrina, 48+ before Giovanni [advice].

## Fights

- **Erika:** Victreebel L29, Tangela L24, Vileplume L29 (sleep powders) [game]. Easy with Blizzard / Ice Beam [game][advice].
- **Blaine:** Growlithe L42, Ponyta L40, Rapidash L42, Arcanine L47 (Fire Blast) [game]. Earthquake is super effective [game].
- **Sabrina:** Kadabra L38, Mr. Mime L37, Venomoth L38, Alakazam L43 (Psywave) [game]. Psychic is super effective on
  Nidoking (part Poison) [game]. Alakazam's speed is 115. In battle your speed gets +1/8 from the Soul Badge, rounded down: a shown speed of 103
  becomes 115 (a tie), 104 becomes 117 (you move first) [game]. Our bot dies here in 3% of games [bot].
- **Giovanni:** Rhyhorn L45, Dugtrio L42, Nidoqueen L44, Nidoking L45, Rhydon L50 (Fissure) [game]. Blizzard / Ice Beam
  and Surf-type moves hit them hard [game][advice].
- **Watch the Blackbelt with Machoke in Giovanni's gym**: it is where our bot dies most in this part (15 of 182 games) [bot].

## Watch out

- Do not walk past item balls in the Mansion; the Secret Key is one [web S1][game].
- Our bot plays these fights at red HP on purpose. A careful player should heal before each gym [bot][advice].

## Speedrun tips

- The late plan keeps red HP through a long window of fights and delays healing [bot].
- Skip the Mansion Full Restore only together with the later item rules: 8.5 s saved [bot].
- A heal guard for the Blackbelt never fired because the needed Potions were gone [bot].
