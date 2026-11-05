# AI players and game scoring

Runs AI players through Pokemon Red and scores their progress:

- [`lean_player.py`](lean_player.py): calls a model once per command, with or without the teacher.
- [`play.py`](play.py): game controls, observations and teacher questions.
- [`guide_follow.py`](guide_follow.py): follows the guide's buttons without a model.
- [`bench.py`](bench.py) and [`score_bench.py`](score_bench.py): benchmark milestones and scoring.
- [`guard.py`](guard.py): enforces one command at a time.

See the [main README](../README.md) for setup and game commands.
