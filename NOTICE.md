# Credits and third-party notices

## PokéBench

`arena/bench.py` uses the same ten milestones (keys, labels and order) and the same "start counting in Red's house"
rule as PokéBench's `milestones.py`. Our checks are our own code: they read Red's memory. `arena/lean_player.py`
follows PokéBench's turn format (one fresh prompt per turn, at most 6 presses, a JSON reply; its reply cleanup works
like PokéBench's `_extract_json`). The `a*` press works like PokéBench's `a_until_dialog_end`.
Source: https://github.com/VibeCodyH/pokebench (license checked 28 Oct 2026). Its notice:

```
MIT License

Copyright (c) 2026 Cody Harris
Copyright (c) 2026 Nous Research

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## PokeBot

`kb/bot_route.json`, `kb/bot_stats.json` and `kb/walks.json` come from our speedrun bot,
https://github.com/YentlPeck/Pokebot-RedAI, which builds on PokeBot by Kyle Coburn and Michael Jondahl
(MIT, Copyright (c) 2014 Kyle Coburn and Michael Jondahl; full notice in that repository).

## pret/pokered

`kb/game_facts.json`, `kb/map_facts.json` and the move, species and type tables in `kb/kb.json` were extracted
from the pret disassembly, https://github.com/pret/pokered. We found no license file there (checked 28 Oct 2026).
The disassembly itself is not included; the teacher reads it from your own download (see README).

Pokémon and Pokémon Red are trademarks of Nintendo, Creatures Inc. and GAME FREAK inc. This project is not
affiliated with them, and the MIT license of this repository does not cover their game data.
