---
id: 2
title: Route 3 and Mt. Moon
splits: 4, 5
bosses: SuperNerd:2
maps: PEWTER_CITY, PEWTER_MART, ROUTE_3, MT_MOON_POKECENTER, MT_MOON_1F, MT_MOON_B1F, MT_MOON_B2F, ROUTE_4
---
## Goal

Cross Route 3, take one fossil, and leave Mt. Moon for Cerulean [game][advice].

## You need

- Buy Potions, Antidotes and an Escape Rope if affordable; heal HP, PP and status at the entrance Center. No particular starter, Nidoran, stone or TM is required [game][advice].
- Sources: reference/pokered/data/maps/objects/{Route3,Route4,MtMoon1F,MtMoonB1F,MtMoonB2F}.asm, matching headers/scripts, data/trainers/parties.asm and data/wild/maps/. Coordinates are walking squares [game].

## Steps

1. Leave Pewter east onto Route 3. Eight trainers stand at (10,6), (14,4), (16,9), (19,5), (23,4), (22,9), (24,6), (33,10), with sight ranges 2,3,2,1,4,3,3,2. Fight one at a time when healthy; keep PP for the cave [game][advice].
2. Route 3 joins western Route 4. Center door (11,5); cave entrance (18,5) -> 1F (14,35). The eastern cave exit is Route 4 (24,5), a different door [game].
3. Main route: 1F (5,5) -> B1F (5,5); B1F (21,17) -> main B2F (21,17). This skips optional item branches when a safe path exists [game][advice].
4. Mega Punch detour: 1F (17,11) -> B1F (25,9); B1F (17,11) -> B2F (25,9). Return B2F (25,9) -> B1F (17,11); B1F (25,9) -> 1F (17,11). Do not confuse the two B1F ladders [game].
5. HP Up branch: 1F (25,15) -> B1F (25,15); B1F (13,27) -> B2F (15,27). Return by the same ladders. The item and its Rocket fight are optional [game][advice].
6. Stop at main B2F (12,9), below the Super Nerd at (12,8). Talking up starts battle; stepping on (13,8) also triggers it. After winning, take Dome Fossil (12,6) or Helix Fossil (13,6), with a free bag slot [game][advice].
7. After the fossil: B2F (5,7) -> B1F (23,3); B1F (27,3) -> Route 4 (24,5). Go east to Cerulean. Do not restart the cave; fossil flags survive Escape Rope/blackout [game][advice].
8. All item balls: 1F Potion (2,20), Moon Stone (2,2), Rare Candy (35,31), Escape Rope (36,23), Potion (20,33), TM12 Water Gun (5,32); B2F HP Up (25,21), TM01 Mega Punch (29,5). Stand beside a visible ball, face it, press A. A full bag leaves it there [game].
9. Recorded bot detour: 1F -> B1F -> B2F -> B1F -> 1F -> B1F -> B2F -> B1F -> Route 4. Main route skips the Mega Punch detour. New walks are map-checked, unverified in a game [bot][advice].

## Team check

- Bulbasaur gets Vine Whip L13; Charmander can use Ember on bugs; Squirtle has Water attacks for Geodude. These are type choices, not guaranteed level targets [game][advice].
- Nidoran male evolves L16; Moon Stone evolves Nidorino only if you have both. The bot leaves with Nidoking L17; this is an example, not a requirement [game][bot][advice].
- Red has no wild Mankey on Routes 3, 4 or 22. Route 5 lists Mankey L10/12/14/16; it is reachable south of Cerulean before Bill or Misty. Mankey is not a Water counter [game][advice].
- Paras is available in Mt. Moon: 1F 5%, B1F 10%, B2F 15%. Catching it for later HMs is optional here [game][advice].

## Fights

- B2F Rockets: (11,16) Rattata/Zubat L13; (15,22) Sandshrew/Rattata/Zubat L11; (29,11) Zubat/Ekans L12; (29,17) Raticate L16. Sight range 4, facing down/down/up/left. Avoid optional battles only with a checked path [game][advice].
- Super Nerd: Grimer, Voltorb, Koffing L12. Disable, Screech and Smog/poison can upset a damage estimate [game][advice].
- Route 4 Lass (63,3), facing right, range 3, has Paras, Paras and Parasect L31. She is in the Surf-access area; do not seek her for pre-Misty training [game][advice].

## Watch out

- Poison takes 1 HP every four steps and can black out the team. Cure before a long retreat; compare survival distance. Restore low PP at a Center [game][advice].
- Escape Rope in Red returns to the last healing place (wLastBlackoutMap), not the cave entrance or fossil exit. Look where you arrive, then heal. After blackout, wait for recovery, then read the new town and tile [game][advice].
- Stop after each floor change, text box or unexpected moving person. Map checks are not game verification; all new level targets are untested guesses [advice].

## Speedrun tips

- The bot's Nidoking and TM detours are examples, not requirements for your starter [bot][advice].
