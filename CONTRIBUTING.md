# Contributing

This format is an early draft. Please open an issue with the problem, the proposed change, and a small before/after manifest example. Category and control changes affect every consumer, so discuss them before sending a large implementation.

## Local checks

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m modfx_accessibility lint examples/demo.modfx.json
PYTHONPATH=src python -m modfx_accessibility fmt examples/ --check
PYTHONPATH=src python -m modfx_accessibility doctor
```

Keep the validator dependency-free, preserve stable issue codes where possible, and add a focused test when changing validation behavior. Do not describe a manifest as proof that in-game controls work; that requires integration testing in the mod.

## Adding a diagnostic

1. Add the code to `src/modfx_accessibility/rules.py` with a severity, title, description, group and
   whether `--fix` can repair it. Every emitted code must be registered; the test suite checks that
   the registry and the validator agree.
2. Emit it from `validator.py` (or `pack.py` / `config.py`) using the same code string.
3. Add the code to `docs/DIAGNOSTICS.md` and, if it is normative, to `SPEC.md`.
4. Add a test that fails before the change and passes after it. If the code can fire on the fixtures
   in `examples/`, update `examples/README.md` and the expected counts in
   `tests/test_public_api.py`.

Prefer a warning over an error for anything that is a style or quality judgment. Errors must mean
"this manifest does not satisfy the contract".

## Adding a command or format

Commands live in `cli.py` as a parser plus a `_cmd_*` handler; the logic belongs in a module under
`src/modfx_accessibility/`. Formats live in `reporters/` and must be pure functions that take
`[(path, report), ...]` and return text. Register the name in `reporters.FORMATS`, add it to the
`--format` choices, update `docs/CLI.md` and `docs/DIAGNOSTICS.md`, and add a test that asserts the
output parses in its own format.

Anything that reads or writes files belongs in the command handler, not in a renderer.

## Style

- Python 3.10+, standard library only.
- Type hints on public functions; docstrings with `Args` and `Returns` for new functions.
- Frozen dataclasses for value types; return new objects instead of mutating arguments.
- Deterministic output: sorted keys and stable ordering, so reports diff cleanly.
