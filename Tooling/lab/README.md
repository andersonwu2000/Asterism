# `Tooling/lab/` — running an experiment ON the framework

An experiment is **slice × workspace × driver → record**, and each of
those four has exactly one implementation here.

| noun | what it is | who owns it |
|---|---|---|
| **slice** | one problem's state, taken out of a live workspace (a `carry` bundle), optionally rewound to a historical instant | `snapshot.py`, `rewind.py` |
| **workspace** | a throwaway place to wake the framework in: the base skeleton, the slice, `Tooling/` at a named commit, the arm's overlay | `build.py` |
| **driver** | what is actually woken in it — one of eight | `driver.py`, `gauntlet.py`, `continuity.py` |
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
asterism lab run      standard <set|set/item|all> [--seats S=P/M] [--root R]
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
* `--seats <seat>=<provider>/<model>[:<effort>]` moves one seat for a
  whole run, merged over whatever the arm or the set declares.
  Repeatable.

## `lab run standard` — the sets with recorded answers

An experiment asks a question nobody has asked; a **standard set** asks
one that has an `expected.json`. Same four nouns, one thing added: the
record is SCORED, and the score is appended to `<root>/scorecard.md` —
the only file under the lab root this runner writes outside `runs/`.
`standard` is therefore a reserved experiment name.

```
<root>/sets/standard.yaml      the table: sets, their items, each item's
                               kind, inputs, seats and expectation
<root>/sets/base/Problems/…    seed problems — copied into `<root>/base/`
                               and INITIALISED there by `lab build`
                               (`seed_base_problems`), so a set's own
                               problems need no slice
<root>/sets/<set>/<item>/…     that item's inputs + expected.json
<root>/scorecard.md            one row per item, ever appended
```

A set's `kind:` / `problem:` / `group:` / `trigger:` / `seats:` are the
defaults its items inherit; `group: root` is the problem's top group,
resolved at run time (an integer in the table goes stale the first time
a base is rebuilt, and goes stale silently). `base.problems` names the
seeds; `base.reuse_workspace_problems` names problems the LIVE workspace
holds — those arrive as slices, taken once and then reused, so every
item of a run and every run a scorecard compares sees one scene.

**One fresh workspace per item, not per set.** The judge leaves no scene
behind, so a shared workspace would be sound on the DB — but `claude`
files its transcript under a name derived from the CWD, so items sharing
a workspace share one transcript directory and `tools_touched` could no
longer be attributed to the item that earned it.

Scored per kind: `judge_round` on the verdict, on every `must_fire`
criterion having a fired bullet and on no `must_not_fire` one firing
(the control item is what stops "always rebut" from scoring five green);
`daemon` on `proved_at_least` / `wall_sec_at_most` / `tools_touched`;
`theory_wake` on the document's own verdict and its rounds; `gauntlet`
on how many bricks came back proved. `tools_touched` is read out of
`_out/transcripts/` (both providers' own session records — the only
place the `asterism_tools` half appears, since that server is a stdio
MCP the gateway never sees) and `_out/mcp_logs/` (the gateway's per-call
log, authoritative for the LSP half).

The `gauntlet` kind is the retired `.asterism/gauntlet/harness.py` with
its semantics kept and its paths gone: single-decl bricks, proof
stripped to `sorry`, one shot with no tools, `sorry`/`admit`/`axiom`
rejected before the compiler, `lake env lean` for the verdict. The
bricks are INPUT (`sets/gauntlet/bricks/*.lean`) rather than a query
against the live board, and with none there the kind refuses and names
what it needs.

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
    kind: judge_round | strategist_wake | theory_wake | push_wake
        | daemon | gauntlet
    prompts:                 # <path under Tooling/prompts/>: <file beside lab.yaml>
      adversary/adversary.md: overlays/rubric_v2/adversary.md
    seats:                   # <seat>: provider/model[:effort]
      adversary: codex/gpt-5:xhigh
    # ...plus the kind's own inputs:
    #   judge_round      group, trigger, and exactly one of
    #                    rows (programme_revisions ids) | proposal (a
    #                    file), with decisions (a file)
    #   strategist_wake  group, trigger, since
    #   theory_wake      group, request: {objective, situation}
    #   push_wake        group, trigger, prompt, prompt2
    #   daemon           scope, once, stop: {proved: N | revisions: N | wall_sec: S}
    #   gauntlet         items_dir (a directory of one-decl .lean bricks)
    #   theory_review_round | judge_review_round
    #                    group, round_no, chain, sessions_root,
    #                    resume_sid, [author_resume_sid,
    #                    author_resume_turns, from_arm, resume_note],
    #                    plus the round's frozen inputs — a theory
    #                    round's `request`/`report`/`dialogue`, a judge
    #                    round's `proposal`/`decisions`/`dialogue`
```

## The continuity kinds — one round, run twice

`theory_review_round` and `judge_review_round` (`continuity.py`) answer
one question the other kinds cannot ask: today every review round mints
a FRESH judge, so round 2 pays to re-read everything round 1 already
read. Each of these runs the same round twice against an identical
dossier — `resumed`, on the round-1 judge's own provider session, and
`fresh`, which is exactly today's production path — and writes both
rulings, both wall times and both `spawn_usage` rows.

* The resumed leg works by rewriting the round's COLD spawn
  (`Tooling.agent.spawn_llm`, the one seam `adversary.review` and
  `theorist/review.review` both go through) rather than by a second
  code path through those functions: the variable is session memory,
  and a reimplemented round would be measuring the reimplementation.
  The round's own `is_retry` re-spawn and the tail feedback turn are
  left alone.
* A codex session is resumable only with its ROLLOUT in place —
  `stage_resume` puts the archived
  `.asterism/codex_sessions/<pid>/[review|adversary]/r<n>/rollout-*.jsonl`
  back under the spawn's `CODEX_HOME`, writes the `_codex_sessions.json`
  the adapter looks the thread up in, and seeds `_codex_usage.json` so
  the resumed turn is billed for ITS tokens and not for the whole
  conversation. A slice carries none of that (`snapshot.py` takes the
  DB, the proofs and `_docs/`), so the arm names `sessions_root:`.
* `chain:` says what the arm runs: `pair` (one round, both legs),
  `revise_then_pair` (the author answers the verdict `from_arm:`'s
  resumed leg produced, then a round), `pair_revise_pair` (a round, the
  author answers ITS resumed verdict, then the next round).
  `author_resume_turns:` cuts a long author session back to the turns it
  had taken at the round under test — the Theorist's author holds one
  thread across a whole episode.
* Inputs are FROZEN FILES beside the lab.yaml, not DB rows: a mid-debate
  proposal body and the round-1 criticisms are not what
  `programme_revisions.body` holds, and a run whose inputs live only in
  a query cannot be read back against its verdicts.
* Only a seat on codex can run a resumed leg, and it is refused up front
  rather than after the dossier is built.

`_out/` gets `verdict_r<n>_<leg>.json` (+ a `.md` rendering) per leg,
`verdict_resumed.json` / `verdict_fresh.json` for the arm's headline
round, the revision's `draft_r<n>.md` / `proposal_r<n>.md`,
`timing.json`, and `inputs/`.

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

`_out/asterism.db` is a WAL-safe copy of the workspace's DB, taken for
**every** kind (`driver.keep_db_record`). It is not a convenience: on
the `daemon` kind it is the only record there is. Production `rmtree`s
`.attempts/<pipeline id>/` as each pipeline exits, so a daemon arm keeps
no attempts tree at all and its proposals, verdicts and dialogue exist
only as rows. That kind therefore also gets the reading beside it —
`PROGRAMME.md` / `TREE.md` / `CATALOG.md` as the problem dir held them,
`dialogue/rev<N>.json` per programme revision (every row at that rev,
since only the passed one is unique), and `theory/<doc id>.md` per landed
document.

`_out/transcripts/claude/<cwd>/` is one directory per spawn cwd, because
that is what the CLI files under: a spawn runs in its attempts dir or its
problem dir, never at the workspace root, so the workspace's own munge
names a directory that usually does not exist.
