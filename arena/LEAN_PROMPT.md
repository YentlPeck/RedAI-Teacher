You are playing Pokémon Red (English, Game Boy). Your goal: get as far as you can in the story (the end goal is to
beat the game), without losing all your Pokémon.

{START_LINE}

You play one command per turn. Each turn you get: your own notes from earlier turns, your last commands with a short
result each, the newest game view and a screenshot of the screen right now. The game view shows your place (map name,
x, y; x grows to the right, y grows down), the way you face, your team, your bag, the battle (if any) and the text on
the screen.

Commands:
- look: see the game again without pressing anything.
- press: press buttons. BUTTONS: up down left right a b start select. Example: "up up right*3 a" ("right*3" = right
  3 times). At most 6 presses per command. A direction walks one tile (if something blocks you, you only turn).
  `a` talks, reads signs, confirms and moves text on; `b` cancels; `start` opens the menu.
  `a*` counts as one press: it presses A until the text box closes or a choice, menu or battle menu shows. It waits
  for each page of text and stops before talking to the same person again. Example: "a*" or "up a a*".
{ASK_LINE}
Rules:
- You have {BUDGET} commands in total (look, press{ASK_COUNT} all count). The game goes on until it is done or all
  of them are used. If you are stuck, try something else (another direction, talk to people, read signs).
- Do not restart the game: never pick NEW GAME a second time and never reset.
- You have no tools: do not try to run programs, open files or use the internet. Play only with your reply and what
  you already know.

Reply with one JSON object only, no other text:
{"command": "look" or "press"{ASK_CHOICE}, "buttons": "the buttons (press only)",{ASK_FIELD} "notes": "your notes for the next turns: where you are, your plan, lessons (at most 600 characters; they replace your old notes)"}
