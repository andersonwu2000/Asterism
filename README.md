# Asterism

Asterism is an autonomous theorem-proving framework for Lean 4. You state a
problem in natural language; a fleet of LLM agents decomposes it, argues about
it, writes and critiques proofs — and nothing counts as proved until the Lean
kernel says so. Trust lives in the kernel, never in a model.

## How it works

Proof search is abstracted into BFS over an AND/OR graph:

```
Goal      = OR  : any one Strategy succeeds → Goal succeeds
Strategy  = AND : all sub-Goals succeed → Strategy succeeds
```

Leaf goals are closed directly by an LLM writing tactics; non-leaf goals are
decomposed into strategies. Four worker roles drive the loop:

- **Formalizer** — the sole proving worker: triages intake, proves leaves,
  splits goals, mints toolkit lemmas.
- **Strategist** — plans at the problem level: proposes decision batches as
  written research proposals, judged round-by-round by an isolated
  **Adversary** before anything commits.
- **Scholar** — fetches and indexes papers into a citable shelf.
- **Librarian** — harvests proved results through a five-stage chain into a
  growing Library whose entries must re-pass every gate.

Soundness is the one non-negotiable: `proved` is only marked after the proof's
axiom set is verified against a whitelist; deduplication goes through Lean
kernel probes; and harvested results pass per-declaration axiom gates again
after every high-risk rewrite. A human signs off before anything enters the
Library. The full design lives in [docs/architecture.md](docs/architecture.md).

## Results

All completions below are kernel-checked (`#print axioms` clean — no
`sorryAx`). The model column records the seat lineup active during each run;
the framework is model-agnostic.

| Result | Scope | Completed | Models |
|---|---|---|---|
| miniF2F | 244 imported statements: **235 proved**, 9 shown false as transcribed (see errata note) | May 11–17, 2026 | Claude Opus · Sonnet |
| Residue theorem | complex analysis, single problem | May 21, 2026 | Claude Opus · Sonnet |
| Jordan normal form | linear algebra, single problem | May 31, 2026 | Claude Opus 4.8 |
| Stokes' theorem | 19-lemma program incl. integration on currents | Jun 10 – Jul 1, 2026 | Opus 4.8 workers · Fable-5 strategist |

> **miniF2F errata note.** The remaining 9 statements are not open failures:
> each was identified as a transcription bug in the upstream benchmark and
> refuted with a standalone kernel-verified counterexample (no prior issue or
> PR existed on any upstream repo). See
> [docs/errata/minif2f/README.md](docs/errata/minif2f/README.md) — all nine
> disproofs re-verify with `lake env lean`.

## Install

**Windows — no terminal, ever:**

1. Get this folder (download & unzip, or clone).
2. Double-click **`Asterism.exe`** — the one door. On a fresh machine
   your browser opens a setup page that detects what's already there
   and installs the rest with one button — Python, the engine, Git,
   the Lean prover (or adopts one you already have), the multi-GB
   math library, and Claude Code. Each target shows live progress in
   a checklist; the only step that needs you is the one-time Claude
   login (a browser tab opens — click Authorize). When it's all green
   the page hands off to the Asterism console by itself. Every day
   after, the same exe (or the Desktop shortcut it creates) opens the
   console directly. Then: create a problem, press Run.

   (If Windows SmartScreen objects to a downloaded copy: More info →
   Run anyway. AV blocking the exe entirely? Right-click
   `installer\setup-server.ps1` → Run with PowerShell, then open
   http://127.0.0.1:8641/ in your browser.)

Re-running the exe is always safe; if anything is missing or broken it
reopens the setup page, and finished parts are skipped.

**macOS / Linux:** `bash installer/install.sh`, then `asterism serve`
and open http://127.0.0.1:8642.

## Quick start

<!-- TODO: screenshot / GIF of the web console -->

1. `asterism serve` and open the console.
2. Create a problem from a name and a natural-language description.
3. Press Run on its page.
4. Watch the run strip name the phase while the constellation draws
   the proof's shape.
5. When the inbox lights up, review and sign off.

## The web console

One serve process per workspace; the whole lifecycle runs in the browser.
A live run strip names the phase and each agent's unit; the constellation
draws the proof's true shape — root-grown work above a horizon, forward work
beneath it with citation threads crossing where it is used. Papers live on a
shelf you can bind citations from; the Library page draws the harvested
corpus as one searchable sky. An inbox collects everything that needs a
human, with age escalation on blocking requests. The UI is read-only against
the engine database; every action goes through the same chokepoints as the CLI.

## Documentation

- [Architecture](docs/architecture.md) — roles, state, invariants
- [Data flow](docs/data-flow.md) — one dispatcher tick, pipeline by pipeline
- [Failure modes](docs/failure_modes.md) — the outcome × transition vocabulary
- [Notes & devlog](https://andersonwu2000.github.io/asterism-notes/) —
  longer write-ups live here

## Development

```
pip install -e ".[dev]"
cd web && npm install && npm run build && cd ..
lake exe cache get        # Mathlib olean cache
asterism serve            # http://127.0.0.1:8642
```

- Tests: `pytest` (parallel via xdist by default; `-n0` for serial debugging)
- Web smoke suite: `cd web && npm run smoke` (Playwright against a live serve)
- CI runs the lint + full suite blocking on both Windows and Ubuntu

## Uninstall

Delete the Asterism folder (everything heavy — the math library, the
database, your problems and proofs — lives inside it) and the Desktop
shortcut. That's it.

The setup may also have installed shared developer tools — Python,
Git, the Lean toolchain (`%USERPROFILE%\.elan`), Claude Code — which
other software on your machine may now use; remove them the standard
way (Settings → Apps, or delete `.elan`) only if you're sure nothing
else needs them.

## License

Released under the [MIT License](LICENSE). Benchmark-derived problem data under
`Problems/` and `Benchmarks/` remains subject to its upstream licenses.
