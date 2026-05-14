# miniF2F benchmark adapter

Drives Asterism against the [miniF2F](https://github.com/openai/miniF2F)
high-school-math theorem benchmark. Not part of Asterism framework
itself — this directory is benchmark tooling, not callable from
`Tooling/`.

## Files

- `adapter.py` — parse miniF2F Lean 4 files → Asterism `Problems/<slug>/`
- `test_adapter.py` — fixture-based tests for the adapter (no clone needed)

## Workflow

`init-batch` + `run --scope` (commit `a6b24cb`) make benchmark runs
single-workspace-friendly: imported miniF2F problems coexist with
hand-authored research problems in `Problems/`, the daemon scopes
dispatch to the benchmark subset via the `minif2f_` slug prefix, and
no separate workspace clone is required.

```bash
# 1. Clone miniF2F source on demand (kept outside the repo via .gitignore)
git clone --depth 1 https://github.com/yangky11/miniF2F-lean4 _ext/minif2f

# 2. Import a batch — adapter writes Problems/minif2f_<name>/{Manifest,Defs}.lean
python Benchmarks/minif2f/adapter.py \
    --source _ext/minif2f/MiniF2F/Valid \
    --output ./Problems \
    --filter mathd_algebra_ \
    --limit 10

# 3. Bulk-init every problem dir that has a Manifest.md
python -m Tooling.core.cli init-batch Problems
#   (idempotent: hand-authored problems already in the DB stay put;
#    only the newly imported minif2f_* dirs get registered)

# 4. Run scoped — daemon only dispatches problems matching the pattern
python -m Tooling.core.cli run --scope 'minif2f_%'
#   (SG, PN, etc remain in their current state but are not dispatched)
```

To remove a batch after a pilot:

```bash
for d in Problems/minif2f_*; do
    python -m Tooling.core.cli reset "$(basename $d)"
done
rm -rf Problems/minif2f_*
rm -f Library/Misc/minif2f_*.lean
# Manually trim the minif2f_ entries from Library/Misc/INDEX.md
```

## Adapter CLI

```
python Benchmarks/minif2f/adapter.py \
    --source <DIR>        # miniF2F .lean files (e.g. <clone>/MiniF2F/Valid)
    --output <PROBLEMS>   # Asterism Problems root (e.g. ./Problems)
    [--filter <PREFIX>]   # Only theorems whose ORIGINAL name starts with this
    [--limit <N>]         # Cap imported count
```

Outputs `<output>/minif2f_<original-name>/{Manifest.md, Defs.lean}` for
each parsed theorem. `set_option maxHeartbeats 0` is preserved in
Defs.lean (miniF2F sets unbounded elaboration time per problem).

## Running adapter tests

```bash
python -m pytest Benchmarks/minif2f/test_adapter.py
```

13 tests, fixture-based — no real miniF2F clone needed for tests.

## Why this lives outside `Tooling/` and `tests/`

`Tooling/` is Asterism framework's own Python: dispatcher, gateway,
verify, library promote, etc. `tests/` is its test suite. Neither
should contain benchmark-specific code — the miniF2F adapter is one
of potentially many external benchmark drivers, kept under
`Benchmarks/<name>/` so the framework/benchmark boundary stays clean:

- Framework knows nothing about benchmarks.
- Benchmark code knows the framework's public interface (Manifest
  format, asterism CLI), not its internals.
- Adding `Benchmarks/putnambench/` later requires zero `Tooling/` change.

## Past pilots

- `runs/minif2f_pilot.md` — 5-problem `mathd_algebra_` pilot
  (2026-05-11). 5/5 proved, ~18 min wall. Surfaced the slot-starvation
  TimeoutError misclassification, fixed in commit `17c71fe`.
