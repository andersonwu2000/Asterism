# `Tooling/lab/` — running an experiment ON the framework

An experiment is **slice × workspace × driver → record**, and each of
those four has exactly one implementation here.

| noun | what it is | who owns it |
|---|---|---|
| **slice** | one problem's state, taken out of a live workspace (a `carry` bundle), optionally rewound to a historical instant | `snapshot.py`, `rewind.py` |
| **workspace** | a throwaway place to wake the framework in: the base skeleton, the slice, `Tooling/` at a named commit, the arm's overlay | `build.py` |
| **driver** | what is actually woken in it — one of five | `driver.py` |
| **record** | `run_record.json` + `_out/`, the only things that survive the workspace | `run.py` |

## The root is never defaulted

The lab's state — `snapshots/`, `runs/`, `docs/<exp>/lab.yaml` — lives in
the operator's **development area**, and production (daemon, agent,
pipeline, prompts) may not reference that area at all. A default
compiled in here would be exactly such a reference, shipped to every
checkout. So the root comes from `--root <dir>` or `ASTERISM_LAB_ROOT`
and from nowhere else; with neither, every action refuses.

`Tooling/lab/` ships with the framework because it has tests and moves
with the schema. Its **inputs** do not: overlay files, prompt files and
recovered decision files are resolved relative to the `lab.yaml` that
names them.

## The CLI

```
asterism lab snapshot --scope <problem> [--rewind <ISO instant>] [--root R]
asterism lab build    <exp> <arm> [--root R]
asterism lab run      <exp> <arm> [--reps N] [--keep] [--root R]
asterism lab gc       [--keep-latest 3] [--root R]
```

* `snapshot` runs **while a daemon writes** (`mode=ro` + the sqlite
  backup API), which is why it exists beside `carry export` rather than
  inside it. `--rewind` moves the rows **and the file plane** in one
  action and writes `_rewind_ledger.json` saying, per directory, what
  was kept, what was dropped and on which provenance signal.
* `build` refuses a target holding `daemon.pid`, never puts a `.git` in
  the workspace, takes `Tooling/` from a **commit** (never the working
  tree), lands the slice with `carry import --allow-migrate`, and
  junctions `.lake/packages` — the dependency tree only. Not `.lake`:
  `build/` under it is the live workspace's own output, written right
  now by the running daemon under lake's lock, so the lab workspace gets
  its own and pays a cold build for it.
* `run` builds a fresh workspace per repetition, spawns the driver with
  `cwd` in that workspace (so the arm's prompt overlay and seat config
  are the ones actually read), copies artefacts and both providers'
  transcripts into `_out/`, writes `run_record.json`, and clears the
  workspace unless `--keep`.
* `gc` clears finished workspaces, and drops slices that no `lab.yaml`
  names beyond the newest N.

## `lab.yaml`

One file per experiment, at `<root>/docs/<exp>/lab.yaml`.

```yaml
snapshot: Combinatorics.union_closed@20260902-233100Z   # a slice id
# ...or the slice to take if it is not there yet (reproducible, so it is
# taken once and reused):
rewind:
  problem: Combinatorics.union_closed
  cutoff: "2026-09-02T23:31:00+00:00"

code_commit: 300a6e89        # optional; default HEAD of this repo
reps: 2                      # optional; --reps overrides

arms:
  <name>:
    kind: judge_round | strategist_wake | theory_wake | push_wake | daemon
    prompts:                 # <path under Tooling/prompts/>: <file beside lab.yaml>
      adversary/adversary.md: overlays/rubric_v2/adversary.md
    seats:                   # <seat>: provider/model[:effort]
      adversary: codex/gpt-5:xhigh
    # ...plus the kind's own inputs:
    #   judge_round      group, rows (programme_revisions ids), trigger, decisions
    #   strategist_wake  group, trigger, since
    #   theory_wake      group, request: {objective, situation}
    #   push_wake        group, trigger, prompt, prompt2
    #   daemon           scope, once, stop: {proved: N | revisions: N | wall_sec: S}
```

Every key is checked and an unknown one is a refusal that names the keys
that level takes. The failure a hand-written `lab.yaml` is exposed to is
not a crash: a `prompt:` where `prompts:` was meant runs the arm against
the unedited prompt and **looks like it worked**.

An overlay must **replace** a prompt the workspace already has, and must
differ from it — an overlay with no target is one whose prompt moved,
and a byte-identical one is a control the report will call a variant.

`stop:`'s `proved`/`revisions` count what the RUN produced, not what the
workspace holds: the slice arrives with the problem's whole history in
it.

## The record

`run_record.json` (in `_out/` and beside it) carries the slice id, the
code commit, the arm's own options as they were when it ran, the
**sha256 of every file under the workspace's own `Tooling/prompts/`**
(what the seat read, not what the arm declared),
the seats as the driver read them inside the workspace, the provider's
own token/turn/wall accounting from `spawn_usage`, the outcome, and the
artefact list.

`_out/` holds each pipeline's attempts tree **whole** — refused verdicts
included, which is the artefact that mattered the one time it was
deleted — plus the landed theory documents, both providers' transcripts,
and the driver's own `driver_result.json`.
