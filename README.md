# RedAI Teacher

A guide that tells an AI player where to go in Pokémon Red, like a speedrun guide in World of Warcraft.

Each turn the AI player sees the game screen and one GUIDE line: the step it is on and the buttons for its next
move. The guide is plain code, not a language model: it reads the game's memory and the game's own rules, so the
same moment always gets the same advice. The player can also ask the teacher a question.

## Result

Fresh game to the first badge (Brock), at most 1000 commands, rules as in
[PokéBench](https://github.com/VibeCodyH/pokebench). One game each, thinking level high.

| Model | Alone (PokéBench) | With the guide |
|---|---|---|
| Claude Haiku 5.5 | no badge in 1000 commands, $2.36 | Brock in **317** commands, $0.14 |
| GPT-6-Luna | no badge in 1000 commands, $1.85 | Brock in **296** commands, $0.08 |
| GPT-6.1 Terra | Brock in 514 commands, $5.47 | Brock in **369** commands, $1.01 |

With the guide every model beat Brock in every scored game. More thinking did not help. All numbers:
[RESULTS.md](RESULTS.md).

## Setup

You need Python 3.12, `git`, and your own legal copy of Pokémon Red (English, Game Boy). Expected SHA-1 of the ROM:
`ea9bcae617fdf159b045185467ae58b2e4a48b9a`. The ROM is not included.

```sh
python -m pip install -r requirements.txt

# The teacher reads names and memory addresses from the pret disassembly (not included, see below).
git clone https://github.com/pret/pokered reference/pokered
git -C reference/pokered checkout af519899719f0754965776faac0e836a3b906e6d
curl -L -o reference/pokered.sym https://raw.githubusercontent.com/pret/pokered/095c7d7227ea958c1afa76765c044793b9e8dc5a/pokered.sym
```

Put your ROM at `red.gb` in this folder, or set `REDAI_ROM=/path/to/red.gb`. Other paths can be changed with
environment variables too (list at the top of [tools/settings.py](tools/settings.py)).

The AI player runs through a command-line tool on your own subscription: the `claude` CLI (Claude models) or the
`codex` CLI (GPT models). They must be on your `PATH`, or set `REDAI_CLAUDE` / `REDAI_CODEX`.

## Run a game

```sh
python arena/lean_player.py game1 --model haiku --group teacher       # with the guide
python arena/lean_player.py game2 --model haiku --group plain         # without the guide
python arena/score_bench.py game1 game2                               # milestones and commands
```

Models: `haiku`, `luna`, `sonnet`, `terra`. Add `--effort low|medium|high|xhigh|max` for the thinking level.
Each game gets a folder in `~/redai-runs/` (or `REDAI_RUNS`). The emulator runs headless, one command at a time.

Other tools:

- `python arena/guide_follow.py follow1` plays by copying the GUIDE keys only, with no model.
- `python tools/advise.py FILE "am I ready for Brock?"` asks the teacher about a saved PyBoy `.state` file.

## Tests

```sh
PYTHONPATH=non_emulator python -m unittest discover -s tests
PYTHONPATH=tests_arena/non_emulator python -m unittest discover -s tests_arena
```

On Windows PowerShell, set the variable first: `$env:PYTHONPATH = "non_emulator"`.

The tests never start the emulator unless you set `ARENA_EMULATOR_TESTS=1` (then they need the ROM). Most teacher
tests use memory dumps from our own game runs. Those dumps are made from the ROM, so they are not in this repo, and
the tests that need them are skipped with a clear reason. With the dumps (`REDAI_FIXTURES`), all 532 + 34 tests
pass, apart from 13 skipped emulator and history checks.

## Not included, and why

- **The ROM and anything made from it**: save states, memory dumps, screenshots, game recordings. Bring your own ROM.
- **pret/pokered** (the disassembly): third-party, and we found no license that allows copying it. Download it as
  shown above.
- **PokéBench**: third-party. We only follow its rules and compare with its published runs.
- **Game logs and run folders** of our test games.
- **Scripts that rebuild the knowledge base** from our speedrun bot's runs. They need that bot's private run data.
  The finished knowledge base is in `kb/`.
- **Internal notes and reviews.** Code comments such as "Sol R17 B1" name a finding from our AI code reviewer.

## Credits

The route data in `kb/` comes from our speedrun bot,
[Pokebot-RedAI](https://github.com/YentlPeck/Pokebot-RedAI), which builds on PokeBot by Kyle Coburn and Michael
Jondahl (MIT). Game facts come from the [pret/pokered](https://github.com/pret/pokered) disassembly.
Pokémon is a trademark of Nintendo, Creatures Inc. and GAME FREAK inc. This project is not affiliated with them.

Made by Yentl Peck in 2026, with AI help. MIT license: [LICENSE](LICENSE).
