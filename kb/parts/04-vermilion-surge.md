---
id: 4
title: Vermilion, the S.S. Anne and Lt. Surge
splits: 8
bosses: Rival2:2, LtSurge:1
maps: CERULEAN_CITY, ROUTE_5, UNDERGROUND_PATH_ROUTE_5, UNDERGROUND_PATH_NORTH_SOUTH, UNDERGROUND_PATH_ROUTE_6, ROUTE_6, VERMILION_CITY, VERMILION_POKECENTER, VERMILION_MART, VERMILION_DOCK, SS_ANNE_1F, SS_ANNE_2F, SS_ANNE_CAPTAINS_ROOM, VERMILION_GYM
---
## Goal

Get **HM01 Cut** on the S.S. Anne and beat **Lt. Surge** for the Thunder Badge.

## You need

- The S.S. Ticket (from Bill) to board the ship [web S17].
- Cut and the Cascade Badge to cut the small tree in front of the Vermilion Gym [web S17][web S18].

## Steps

1. Leave Cerulean through the robbed house to Route 5. Take the **Underground Path** south to Route 6 [bot].
   Do not try the Saffron gates: the guards are thirsty and let no one through yet [web S17].
2. In Vermilion, heal and buy **Super Potions** at the Mart [game][advice].
3. Board the **S.S. Anne** at the dock. The rival waits on 2F (Pidgeotto L19, Raticate L16, Kadabra L18, Ivysaur L20) [game].
4. Go to the **captain's room** at the top of the ship and talk to the captain. He gives **HM01 Cut** [game][web S17].
   The ship leaves after you get off [web S17].
5. Teach Cut to a helper Pokémon (our bot: Paras from Mt. Moon) [bot]. Cut needs the Cascade Badge [game]. Cut the tree next to the gym.
6. In the gym, find two switches hidden in trash cans. The second is usually in a can next to the first, but in Red it
   can also be in the top-left can. If you pick a wrong can, both switches reset [game][web S17].
7. Fight Lt. Surge. He gives **TM24 Thunderbolt** [game]. Teach it to Nidoking [bot].

## Team check

- Nidoking is part Ground, so Electric moves do nothing to it [game]. Surge is a safe fight for Nidoking [game].
- Our bot's Nidoking is level 28 at Surge [bot]. A careful player: 28 or more [advice].

## Fights

- **Lt. Surge:** Voltorb L21 (Tackle, Screech, SonicBoom), Pikachu L18, Raichu L24 (Thunderbolt) [game].
  SonicBoom always does 20 damage, even to Ground types [game]. Only normal-type hits (Tackle, Quick Attack) and SonicBoom hurt Nidoking [game].
- Our bot dies in this section in 1.5% of games (5 of 336), all on the S.S. Anne, none at Surge [bot].

## Watch out

- Thrash, Mega Punch and BubbleBeam are enough here [bot].
- Rival fight: Sand-Attack lowers accuracy. Our bot stays in rather than switching (switching costs instant text) [bot].

## Speedrun tips

- The bot visits the ship before the Mart to keep instant text, and teaches BubbleBeam only after the rival [bot].
- The trash-can puzzle is solved with a save, reset and exact button frames [bot].
- `VOLTORB_RED` (19 Oct): let Voltorb's SonicBoom bring Nidoking to red HP. Red HP skips battle sounds later.
  In 38 pairs of runs where the switch fired and both runs reached the Tower, it was 17 s faster (95% range 7-26 s),
  with no clear extra deaths. Not an average over all games [bot].
