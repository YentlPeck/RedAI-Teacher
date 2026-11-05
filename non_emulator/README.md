# Test setup without the emulator

[`sitecustomize.py`](sitecustomize.py) blocks PyBoy imports, disables bytecode
output and loads the test fixture-preservation helper. Add this folder to
`PYTHONPATH` when running the main test suite without an emulator:

```powershell
$env:PYTHONPATH = "non_emulator"
python -m unittest discover -s tests
```

Some tests require external fixtures; see the [main README](../README.md).
