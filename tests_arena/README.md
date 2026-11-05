# Arena regression tests

[`test_arena_r11.py`](test_arena_r11.py) checks the game harness, prompts and
scoring with synthetic states, logs and a fake game object.
[`non_emulator/sitecustomize.py`](non_emulator/sitecustomize.py) supplies the
emulator-blocking setup for this suite.

Run from the repository root:

```powershell
$env:PYTHONPATH = "tests_arena/non_emulator"
python -m unittest discover -s tests_arena
```
