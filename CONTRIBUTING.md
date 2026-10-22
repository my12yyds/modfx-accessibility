# Contributing

This format is an early draft. Please open an issue with the problem, the proposed change, and a small before/after manifest example. Category and control changes affect every consumer, so discuss them before sending a large implementation.

## Local checks

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m modfx_accessibility lint examples/demo.modfx.json
```

Keep the validator dependency-free, preserve stable issue codes where possible, and add a focused test when changing validation behavior. Do not describe a manifest as proof that in-game controls work; that requires integration testing in the mod.
