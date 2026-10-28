# Results (28 October 2026)

**With the guide, every model beat Brock in every scored game, in about 300 commands for about $1 or less.
More thinking did not help.**

Rules (as in [PokéBench](https://github.com/VibeCodyH/pokebench)): fresh power-on, at most 6 button presses per
command, 1000 commands, the game ends at the Boulder Badge (Brock). Same teacher in every game. Price = API list
price for the tokens used (we played on subscriptions). One game per cell.

## Commands to beat Brock (fewer is better)

| Thinking level | Haiku 5.5 | GPT-6-Luna | GPT-6.1 Terra |
|---|---:|---:|---:|
| low | 310 · $0.11 · 16 min | **282** · $0.10 · 34 min | **298** · $0.81 · 34 min |
| medium | 326 · $0.13 · 19 min | 354 · $0.10 · 33 min | 367 · $1.00 · 42 min |
| high | 317 · $0.14 · 19 min | 296 · $0.08 · 27 min | 369 · $1.01 · 41 min |
| xhigh | 389 · $0.22 · 32 min | 293 · $0.09 · 27 min | 475 · $1.35 · 52 min |
| max | not scored (too slow) | 290 · $0.08 · 27 min | 311 · $1.16 · 50 min |
| ultra | - | - | 320 · $0.89 · 38 min |

No game lost a fight against Brock.

Earlier round with the same teacher (round b4, thinking high): Haiku 268 commands ($0.10, 14 min),
Luna 326 commands ($0.09, 32 min). Both beat Brock.

## Without the guide (PokéBench, thinking high)

| Model | PokéBench alone | With our guide (best / at high) |
|---|---|---|
| Haiku 5.5 | no badge (reached the gym at command 453), $2.36 | 310 / 317 |
| GPT-6-Luna | no badge (reached Pewter at command 945), $1.85 | 282 / 296 |
| GPT-6.1 Terra | beat Brock at command 514, $5.47 | 298 / 369 |

## What we learned

- The guide does the hard thinking, so the model mostly copies its keys. Terra used about 6 thinking tokens per
  command, even at ultra.
- Higher thinking did not lower the count. The worst games were xhigh (Haiku 389, Terra 475). Luck (wild
  encounters) moves one game by about 40 commands either way.
- Cheapest good setup: Luna or Haiku at low or high, about $0.10 per game.

## Not scored

- Haiku 5.5 at max: about 40 s per command. We stopped it after 3 hours at command 275 (Viridian Forest, no loss).
- Claude Sonnet 5.5: its calls often hung after thinking (7 of 25 calls in the last try). Two tries stopped early,
  so Sonnet is not in the results.

## Limits

One game per model and level, so single numbers are noisy. Game logs and recordings are not published (they hold
screenshots of the game). The game runs only to Brock, the first gym.
