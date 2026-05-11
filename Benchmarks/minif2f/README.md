# miniF2F benchmark adapter

Drives Asterism against the [miniF2F](https://github.com/openai/miniF2F)
high-school-math theorem benchmark. Not part of Asterism framework
itself — this directory is benchmark tooling, not callable from
`Tooling/`.

## Files

- `adapter.py` — parse miniF2F Lean 4 files → Asterism `Problems/<slug>/`
- `test_adapter.py` — fixture-based tests for the adapter (no clone needed)

## Recommended: separate workspace for benchmark runs

Asterism's framework convention puts problems in `Problems/<name>/`.
Mixing 244 imported miniF2F dirs with hand-authored research problems
(SG, PN, etc) pollutes `Problems/` visually and conceptually.

**Use a separate workspace for benchmark runs**:

```bash
# 1. Clone Asterism to a benchmark-only workspace
git clone D:/Asterism D:/Asterism-miniF2F
cd D:/Asterism-miniF2F

# 2. Reset away the inherited research problems so only miniF2F lives in Problems/
for p in Problems/*/; do
    name=$(basename "$p")
    python -m Tooling.cli reset "$name"
done

# 3. Clone miniF2F source
git clone --depth 1 https://github.com/yangky11/miniF2F-lean4 _ext/minif2f

# 4. Import (pilot 10 algebra problems for quick iteration)
python Benchmarks/minif2f/adapter.py \
    --source _ext/minif2f/MiniF2F/Valid \
    --output ./Problems \
    --filter mathd_algebra_ \
    --limit 10

# 5. Init each
for d in Problems/minif2f_*; do
    python -m Tooling.cli init "$(basename $d)"
done

# 6. Launch daemon
python -m Tooling.cli run
```

## Adapter CLI

```
python Benchmarks/minif2f/adapter.py \
    --source <DIR>        # miniF2F .lean files (e.g. <clone>/MiniF2F/Valid)
    --output <PROBLEMS>   # Asterism Problems root (e.g. ./Problems)
    [--filter <PREFIX>]   # Only theorems whose ORIGINAL name starts with this
    [--limit <N>]         # Cap imported count
```

Outputs `<output>/minif2f_<original-name>/{Manifest.md, Defs.lean}`
for each parsed theorem. `set_option maxHeartbeats 0` is preserved
into Defs.lean (miniF2F sets unbounded elaboration time per problem).

## Running adapter tests

```bash
python -m pytest Benchmarks/minif2f/test_adapter.py
```

13 tests, fixture-based — no real miniF2F clone needed for tests.

## Why not part of `Tooling/` or `tests/`

`Tooling/` is Asterism framework's own Python: dispatcher, gateway,
verify, library promote, etc. `tests/` is its test suite. Neither
should contain benchmark-specific code. The miniF2F adapter is one
of potentially many external benchmark drivers — keeping them under
`Benchmarks/<name>/` makes the boundary explicit:

- Framework knows nothing about benchmarks
- Benchmarks know the framework's public interface (Manifest format,
  CLI commands), but not its internals
- Adding `Benchmarks/putnambench/` later doesn't touch `Tooling/`
