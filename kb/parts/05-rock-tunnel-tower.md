---
id: 5
title: Bicycle, Rock Tunnel, Celadon, Fly and Pokémon Tower
splits: 9, 10
bosses: Rival2:5
maps: VERMILION_CITY, POKEMON_FAN_CLUB, CERULEAN_CITY, BIKE_SHOP, ROUTE_9, ROUTE_10, ROCK_TUNNEL_POKECENTER, ROCK_TUNNEL_1F, ROCK_TUNNEL_B1F, LAVENDER_TOWN, LAVENDER_POKECENTER, ROUTE_8, UNDERGROUND_PATH_ROUTE_8, UNDERGROUND_PATH_WEST_EAST, UNDERGROUND_PATH_ROUTE_7, ROUTE_7, CELADON_CITY, CELADON_POKECENTER, CELADON_MART_1F, CELADON_MART_2F, CELADON_MART_3F, CELADON_MART_4F, CELADON_MART_5F, CELADON_MART_ROOF, CELADON_MART_ELEVATOR, ROUTE_16, ROUTE_16_GATE_1F, ROUTE_16_FLY_HOUSE, POKEMON_TOWER_1F, POKEMON_TOWER_2F, POKEMON_TOWER_3F, POKEMON_TOWER_4F, POKEMON_TOWER_5F, POKEMON_TOWER_6F, POKEMON_TOWER_7F, MR_FUJIS_HOUSE
---
## Goal

Get the Bicycle, cross Rock Tunnel, shop in Celadon, get **HM02 Fly**, and rescue Mr. Fuji in Pokémon Tower for the **Poké Flute**.

## You need

- Bike Voucher from the Fan Club chairman in Vermilion, then the Cerulean Bike Shop gives the **Bicycle** [web S17].
- Cut for the tree on Route 9 (east of Cerulean) and the tree to the Route 16 Fly house [web S17][bot].
- To pass the ghost Marowak on Tower 6F: the **Silph Scope** (Rocket Hideout) or a **Poké Doll** (Celadon Mart 4F) [game].

## Steps

1. In Vermilion, talk to the Fan Club chairman: **Bike Voucher**. Get the Bicycle in Cerulean [web S17].
2. Cut the tree east of Cerulean, cross Route 9 to Route 10 and **Rock Tunnel** [web S17].
   Rock Tunnel is dark. **HM05 Flash** (Oak's aide in the Route 2 gate, needs 10 Pokémon species caught) lights it,
   but it is optional. Our bot crosses without Flash [game][bot].
3. Lavender Town, then west on Route 8 and the Underground Path to Route 7 and **Celadon City** [bot].
4. **Celadon Department Store** [game][bot]:
   - 2F: TM07 Horn Drill, Super Potions, Revives.
   - 4F: **Poké Doll**.
   - Roof vending machine: buy drinks. Give the girl Fresh Water for **TM13 Ice Beam** or Soda Pop for TM48 Rock Slide.
     Keep **one extra drink for the Saffron guards**.
   - 5F: X Accuracy, X Speed (useful with Horn Drill).
5. Go west from Celadon (cut the tree) to Route 16. The **Fly house** is there: HM02 Fly [game][bot]. Teach it to your
   flier (our bot: Pidgey). Fly needs the Thunder Badge [game][bot].
6. Fly to Lavender. Climb **Pokémon Tower**. The rival waits on 2F [game]. On 5F, step into the purified zone: it heals
   your whole team for free [game].
7. On 6F the ghost Marowak blocks the way. Use the **Poké Doll** in battle to escape it, or fight it with the Silph Scope [game][bot].
8. On 7F beat the Rockets, then talk to **Mr. Fuji**. In his house in Lavender he gives the **Poké Flute** [web S17][bot].

## Team check

- Teach **Thunderbolt** (from Surge) and **Horn Drill** (Celadon). Our bot's Nidoking is level 31 at Fly and 34 at the Flute [bot].
- Horn Drill knocks out in one hit but hits only 30% of the time [game]. With X Accuracy it always hits if your speed is
  not lower than the target's. It still fails on Ghost types and on a target in the air (Fly) or underground (Dig) [game].

## Fights

- **Tower rival:** Pidgeotto L25, Gyarados L23, Growlithe L22, Kadabra L20, Ivysaur L25 [game]. Thunderbolt hits Gyarados four times as hard [game].
- Our bot dies in this part in about 10% of the games that reach it (29 of 284: Rock Tunnel, Lavender, Tower) [bot].

## Watch out

- **Skipping the Rocket Hideout:** the Poké Doll trick avoids the Hideout's spinner-tile maze, which cost Claude Opus 4.5
  about 9,000 steps and Gemini days [game][web S2][web S5]. Our bot never enters the Hideout [bot].
- Pokémon Tower: pick up items that block the path. Opus 4.5 did not pick up a Rare Candy blocking it for over an hour [web S2].
- Without the Silph Scope, wild ghosts in the Tower cannot be hit. Run from them [game][advice].
- If you want the Silph Scope anyway: a poster behind a Grunt in the Celadon Game Corner opens the Rocket Hideout. On B4F
  a Grunt drops the Lift Key: talk to him again after the fight. Beat Giovanni; the Silph Scope is on B4F [web S17][game].

## Speedrun tips

- Red HP can carry from Surge through Rock Tunnel to the Tower heal zone; it saved about 27 s in the Fly part and
  13 s before the heal zone in small samples [bot].
- `LAVENDER_FLOOR`: keep enough HP for two Pidgeotto hits at the Tower rival [bot].
