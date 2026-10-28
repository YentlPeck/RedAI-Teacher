You are playing Pokémon Red (English, Game Boy) through a command tool. Your goal: get as far as you can in the
story (the end goal is to beat the game), without losing all your Pokémon.

{START_LINE}

Work in this folder: {ROOT}
Use only these commands (each one is one shell command; run them one at a time):

    {PY} arena/play.py look {RUN}
    {PY} arena/play.py press {RUN} BUTTONS
{ASK_LINE}

BUTTONS: up down left right a b start select. Example: `press {RUN} up up right*3 a`. At most 6 presses per
command. A direction walks one tile (if something blocks you, you only turn). `a` talks, reads signs, confirms and
moves text on; `b` cancels; `start` opens the menu.

After every command you get: your place (map name, x, y; x grows to the right, y grows down), the way you face,
your team, your bag, the battle (if any), the text on the screen, and the path of a screenshot of the screen. Look
at the screenshot whenever it helps (open the image file).

Rules:
- You have {BUDGET} commands in total (look, press{ASK_COUNT} all count). Keep playing until the tool says the game
  is done or all of them are used: do not stop early. If you are stuck, try something else (another direction, talk to people, read signs).
- Do not open, read or search any other file in this folder or on this computer, except the screenshot. Do not use
  the internet. Play only with the commands above and what you already know.
- Do not restart the game: never pick NEW GAME a second time and never reset. Do not edit any file.

Stop only when the tool says the game is done or all {BUDGET} commands are used. Then write a short report: how far you got, what was hard, and how many commands you used.
