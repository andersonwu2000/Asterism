# Spawn Sandbox

Framework state isolation per spawn: framework-managed file mutations
during a spawn are staged in a sandbox copy; the real path is committed
on success (via pipeline-specific callback) or rolled back on failure,
with a recovery sweep for SIGKILL'd spawns that bypassed the cleanup
hook.

Status: design (2026-05-11), revised after review.
Triggered by SG run #15 Goal=343 deadlock — s300 Backward Opus
mutated goal_lean via LSP `apply_edit`, SIGKILL'd at spawn_timeout,
framework's restore-on-exit didn't propagate; later spawns saw a
broken goal_lean and instant-failed with `parent_stub_not_decomposable`.

---

## 1 Problem class

```
1. framework writes state to a shared file (goal_lean / scratch / olean / session / Root.lean.backup / ...)
2. spawn process dies (SIGKILL on watchdog / spawn_timeout / OS kill / crash)
3. framework's restore-on-exit doesn't fire OR doesn't reach disk
4. next operation reads broken state → cascade failure (or silent corruption)
```

Observed instances:

| BUG | Artifact | Severity | Status |
|---|---|---|---|
| SG run #15 s300/301/302 | goal_lean (theorem name) | high (deadlock) | this design |
| Builder LSP edit leak (latent) | goal_lean | high | this design |
| Verify mid-promote crash | parent_lean (alias rewrite) | medium | this design |
| Stale olean after failed verify | `.lake/build/lib/lean/<scratch>.olean` | low | §6.3 |
| `_strategy_s<N>.lean` scratch leak | proofs/_strategy_s<N>.lean | low | this design |
| Root.lean / Library leak (F49 promotion mid-fail) | Root.lean, Library/<Topic>/<problem>.lean, INDEX.md | medium | §6.4 |
| Gateway session leak on SIGKILL | gateway `_state.sessions[token]` | medium | §11 deferred |
| WorkArea attempts_dir not rmtree'd | `.attempts/<pid>/` | low | already handled |

Patching each individually has failed multiple times — every new
artifact re-opens "do we remember to clean up on crash?". The class
needs an architectural answer.

---

## 2 Core invariant

**For every framework-managed file path P touched during spawn S:**

```
∀ S, ∀ P ∈ framework_managed_paths(S):
    P.contents_after_S = P.contents_before_S        (S didn't commit)
                       ∨ P.contents_committed_by_S  (S explicitly committed)
                       
                       NEVER: P.contents = partial mutation by S
```

Must hold under: normal exit, Python exception, SIGKILL of the spawn
process, SIGKILL of the daemon, daemon crash, OS reboot.

---

## 3 Architecture

### 3.1 Merger: SpawnWorkspace = WorkArea ⊕ SpawnSandbox

Current `Tooling/agent.py` `WorkArea` owns the `.attempts/<pid>/`
lifecycle (mkdir on enter, rmtree on success exit, leave on failure
for forensic). Sandbox layers cleanly inside attempts_dir but couples
to WorkArea's cleanup order: **commit MUST happen before WorkArea
rmtree's the directory**. Two separate context managers = order
fragility.

**Decision**: collapse into one `SpawnWorkspace` context manager.
WorkArea + Sandbox become inseparable. One enter, one exit, single
ordered commit path.

```python
class SpawnWorkspace:
    """Replaces Tooling.agent.WorkArea. Owns attempts_dir lifecycle
    AND sandbox staging."""
    
    def __init__(self, attempts_dir: Path, real_paths: list[Path]):
        # ... same fields as draft §3.2 ...
    
    def __enter__(self) -> "SpawnWorkspace":
        # 1. mkdir attempts_dir (WorkArea behavior)
        # 2. mkdir attempts_dir/sandbox/
        # 3. snapshot real_paths into sandbox/ with manifest
        ...
    
    def commit(self, real_writes: list[tuple[Path, bytes]]) -> None:
        """Caller-driven commit. Pipeline knows what should land where
        (see §3.2). Sandbox only enforces atomicity, not semantics."""
        ...
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Order is fixed and explicit:
        # 1. If not committed: rollback (real_paths untouched, just delete sandbox/)
        # 2. If committed: confirm; sandbox/ already consumed by commit()
        # 3. WorkArea cleanup: rmtree attempts_dir on success OR retain on failure
        ...
```

### 3.2 Commit is callback-driven, not "copy sandbox → real"

The naive "commit = copy all sandbox files to real" breaks Builder.
Builder doesn't commit `sandbox/goal_lean` to real — it commits
`sandbox/patch.lean`'s content into real goal_lean (translation, not
copy). Backward commits agent's `patch.lean` + `new_*.lean` to scratch
and proofs paths (different real path than the snapshotted ones).

`commit()` accepts an explicit `real_writes` list from the caller:

```python
# Backward (pipeline/backward.py)
ws.commit(real_writes=[
    (workspace / strategy.scratch_path,            # real destination
     (ws.sandbox_dir / "patch.lean").read_bytes()),
    *[(workspace / f"Problems/{problem}/proofs/L_{slug}.lean",
       (ws.sandbox_dir / f"new_{slug}.lean").read_bytes())
      for slug in sub_slugs],
])

# Builder Phase 2 (pipeline/builder.py)
ws.commit(real_writes=[
    (workspace / goal.lean_path,                   # real goal_lean
     (ws.sandbox_dir / "patch.lean").read_bytes()),  # FROM patch.lean, not goal_lean
])

# Verify (verify.py)
ws.commit(real_writes=[
    (workspace / strategy.lean_path,               # alias-rewritten parent
     rewritten_parent_bytes),
    (workspace / strategy.scratch_path,            # validated strategy patch
     validated_scratch_bytes),
])
```

`sandbox/goal_lean.lean` is **always throwaway** — agent's
exploratory edits there have no commit semantics. Only paths the
caller explicitly names in `real_writes` get promoted. Everything
else in sandbox dies at commit time (or rollback).

Manifest's `real_paths[]` is what gets ROLLED BACK on non-commit
(rollback always restores all snapshotted real paths). Commit's
`real_writes` is independent — what the caller explicitly chose to
promote.

### 3.3 Daemon-startup sweep with owner-PID check

```python
def sweep_orphan_sandboxes(workspace: Path) -> None:
    """Cleans sandbox/ dirs whose owning daemon is dead."""
    for sb_dir in workspace.glob(".attempts/*/sandbox/"):
        manifest_path = sb_dir / "_manifest.json"
        if not manifest_path.exists():
            shutil.rmtree(sb_dir)
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            shutil.rmtree(sb_dir)
            continue
        
        # Skip if owner daemon still alive — concurrent daemon
        # (operator error) or our own running daemon's sandbox.
        owner_pid = manifest.get("owner_pid")
        if owner_pid and _pid_alive(owner_pid):
            print(f"[sandbox-sweep] skip {sb_dir} — owner pid "
                  f"{owner_pid} still alive", flush=True)
            continue
        
        if manifest.get("committed"):
            shutil.rmtree(sb_dir)
            continue
        
        # Spawn died without commit. Real paths should already be
        # pristine (we never wrote during the spawn). Confirm via SHA
        # to catch out-of-sandbox writers.
        for entry in manifest["real_paths"]:
            real = Path(entry["real"])
            if real.exists():
                actual = hashlib.sha256(real.read_bytes()).hexdigest()
                if actual != entry["sha_before"]:
                    print(f"[sandbox-sweep] WARNING drift on {real}: "
                          f"expected {entry['sha_before'][:12]}, "
                          f"got {actual[:12]} — out-of-sandbox write?",
                          flush=True)
                    # Auto-restore from sha_before? Risky without keeping
                    # original bytes. Initial impl: warn only, operator
                    # restores manually (git).
        shutil.rmtree(sb_dir)


def _pid_alive(pid: int) -> bool:
    """Cross-platform 'is this pid running'. On Windows we use
    psutil.pid_exists; on Linux/Mac, os.kill(pid, 0)."""
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
```

Sweep runs at daemon startup, ONCE, before pool dispatch. Adding it
to per-tick would create churn for no benefit (the only failure mode
that needs post-startup recovery is SIGKILL of the daemon's worker
THREAD, which `__exit__` already handles).

### 3.4 LSP buffer hygiene when switching file paths

Gateway worker's `did_open(uri)` caches per-URI elaborated state. If a
worker previously did_opened `Problems/<p>/proofs/L_<slug>.lean`
(serving a prior spawn) and now needs to serve the same logical goal
under `.attempts/<pid>/sandbox/goal_lean.lean`, stale buffer state
risks inconsistency.

**Rule**: each `apply_edit` / `goal_at` / `errors_at` /
`validate_file` call that switches to a new URI does:

```python
# In Tooling/lsp_gateway.py tool wrappers:
def _ensure_did_open_for(slot, new_uri: str):
    if slot.current_uri and slot.current_uri != new_uri:
        slot.send_did_close(slot.current_uri)
    if slot.current_uri != new_uri:
        slot.send_did_open(new_uri, file_content)
    slot.current_uri = new_uri
```

Slot tracks `current_uri`. Switching paths always flushes the old
buffer. Cost: 1 LSP didClose + 1 didOpen per path switch (~5-50ms).
Negligible for our concurrency.

Already partially implemented for slot swap-in (different concept —
swap-in changes WHICH file the slot serves; we additionally need
swap-in to fire didClose+didOpen on the URI switch too).

### 3.5 Per-pipeline real_paths

| Pipeline kind | real_paths snapshotted (rollback target) |
|---|---|
| Backward | `goal_lean` (parent stub), `scratch_path` (strategy patch, if Phase 2) |
| Builder | `goal_lean` (the goal's `.lean` file) |
| Verify housekeeping | parent `.lean` (alias rewrite), scratch `.lean`, olean files (§6.3) |
| Fresh-rescue stage 2 / stage 3 | same as broken spawn's pipeline kind — see §3.4.5 |
| Reflection | LESSONS.md (§6.1 special-case) |
| F49 library promotion | `Root.lean`, `Library/<Topic>/<problem>.lean`, `Library/<Topic>/INDEX.md`, `Root.lean.backup` (§6.4) |

Each pipeline's run helper declares its paths up-front before calling
`SpawnWorkspace(real_paths=...)`. Adding a new pipeline kind = adding
one row to this table.

### 3.5.1 Fresh-rescue takeover semantics

When watchdog kills a Backward / Builder and fresh-rescue stage 2
launches a NEW claude process with the SAME attempts_dir
(`--resume <broken_sid>` flow per `_retry.py`), the question is what
happens to sandbox/.

**Rule**: fresh-rescue stage 2 entry **discards and re-snapshots** the
sandbox. The broken spawn's rollback has already restored real paths;
stage 2 takes a fresh snapshot from those (now-pristine) real paths.

```python
# In Tooling/pipeline/_retry.py fresh-rescue takeover entry:
def _enter_fresh_rescue_stage2(attempts_dir, real_paths):
    # Broken spawn's __exit__ should have rolled back already.
    # Confirm sandbox/ is gone or roll back manually if not.
    sb_dir = attempts_dir / "sandbox"
    if sb_dir.exists():
        _force_rollback_from_manifest(sb_dir)
        shutil.rmtree(sb_dir)
    # Now enter fresh SpawnWorkspace as normal.
    return SpawnWorkspace(attempts_dir, real_paths).__enter__()
```

Stage 3 (postmortem) inherits stage 2's sandbox state, same as today.

---

## 4 Failure modes covered

| Scenario | Outcome |
|---|---|
| Agent illegal signature edit | Hits sandbox; spawn finishes; pipeline rejects bad sig; nothing committed; real path pristine |
| Spawn ships cleanly | Pipeline-defined `commit(real_writes=...)` applies caller-named bytes to real paths; sandbox discarded |
| Spawn raises Python exception | `__exit__` triggers rollback; real paths untouched |
| Spawn SIGKILL by watchdog (mid-thinking trap) | No `__exit__`; manifest on disk; next daemon startup sweep cleans |
| Daemon crash mid-spawn | Sandbox + manifest persist; next daemon start sweep cleans |
| Two parallel spawns on same goal (OR-race) | Each owns its attempts_dir/sandbox; the loser doesn't commit |
| Out-of-sandbox writer drift | Sweep SHA check warns; operator restores via git |
| Concurrent daemon (operator error) | Sweep skips sandboxes whose owner_pid is alive |
| Fresh-rescue takeover takes over a trapped spawn | Stage 2 forces rollback of broken sandbox, re-snapshots from pristine reals |

## 5 Failure modes NOT covered

| Scenario | Why |
|---|---|
| Out-of-sandbox writer (framework code path bypasses sandbox) | SHA sweep warns but cannot auto-correct. Mitigation: invariant test scanning `Tooling/*` for direct `Path.write_*` calls on framework_managed_paths. |
| Disk full mid-commit | Per-file `os.replace` is atomic but multi-file commit is not. Accept: retry on next dispatcher tick (commits are idempotent). |
| OS filesystem corruption | Same problem as any disk state. |
| Multi-host distribution | Single-host filesystem only. |

---

## 6 Special cases

### 6.1 LESSONS.md (append-only, concurrent writers)

LESSONS.md is appended-to by reflection spawn. Multiple reflections
may run in parallel. Naive line-count truncate rollback would
clobber concurrent appends.

**Mechanism**: Each reflection append carries a unique marker comment:

```
- (lesson body) [reflect-sid: a3f2c91b]
```

Rollback finds and removes only the spawn's own marker line, leaving
sibling appends intact. ~20 LOC in `pipeline/reflection.py`.

### 6.2 BRIEF.md (framework-rendered, agent reads only)

`BRIEF.md` is regenerated from `Manifest.md` at dispatcher startup.
Agents never write it. Not in sandbox — no leak risk.

### 6.3 Olean cleanup on rollback

`.lake/build/lib/lean/<scratch_module>.olean` is written by lake when
gateway verifies a scratch file with `write_olean=True`. Rollback
should delete this olean to prevent stale-olean-pollution on later
verifies.

**Specification**:
- Tracked olean path = `workspace / ".lake/build/lib/lean" / module_path(scratch_path)`
- On rollback, delete the olean if it exists AND was written by THIS
  spawn (mtime > spawn start time)
- Verify housekeeping is the primary writer; declares oleans in its
  `real_paths` so they roll back same as other paths

No sandbox copy of oleans — they're large and rebuilt cheaply. Just
delete on rollback.

### 6.4 F49 Library promotion

Library promotion (`Tooling/library.py:promote`) runs in cascade_one
after root proved. It writes `Root.lean`, `Library/<Topic>/<problem>.lean`,
`Library/<Topic>/INDEX.md`, and creates `Root.lean.backup`. Crash mid-
promotion can leak `.backup` and partial writes.

**Decision**: promotion is framework housekeeping, not a spawn, but
shares the same state-leak class. Wrap promotion in a
`SpawnWorkspace`-like helper (`HousekeepingTransaction` — same code,
no spawn process attached). Phase 3 work.

---

## 7 Scope of change

| Module | LOC delta | Note |
|---|---|---|
| **`Tooling/spawn_sandbox.py`** (new) | ~350 | SpawnWorkspace + sweep + olean helper + HousekeepingTransaction |
| `Tooling/agent.py` `WorkArea` | -80 / +0 | WorkArea retired; replaced by SpawnWorkspace |
| `Tooling/pipeline/backward.py` | +60 / -50 | Body wrapped, explicit `commit(real_writes=...)` |
| `Tooling/pipeline/builder.py` | +60 / -40 | Same |
| `Tooling/verify.py` | +50 / -30 | promote_to_alias + olean writes inside transaction |
| `Tooling/lsp_gateway.py` | +50 | did_open/did_close URI hygiene on slot swap |
| `Tooling/context.py` | +20 | Render `goal_lean` as sandbox path in Context.md |
| `Tooling/dispatcher.py` | +30 | Startup sweep call |
| `Tooling/pipeline/_retry.py` | +40 | Fresh-rescue stage 2 sandbox reset |
| `Tooling/pipeline/reflection.py` | +25 | LESSONS.md marker-line append/rollback |
| `Tooling/library.py` | +30 / -20 | promote in HousekeepingTransaction |
| **Test impact** | ~50 fixtures + 1 new file | See §12 |

Net: ~700 LOC added, ~220 LOC removed (ad-hoc snapshot/restore retired).

---

## 8 Implementation phases

```
Phase 1 — Foundation (~3 hr)
  - spawn_sandbox.py: SpawnWorkspace, sweep, _pid_alive
  - test_spawn_sandbox.py: enter/commit/rollback + simulated crash
  - retire WorkArea (agent.py)

Phase 2 — Pipeline integration (~3 hr)
  - backward.py wraps run_backward, explicit commit(real_writes)
  - builder.py wraps run_builder, explicit commit
  - context.py renders sandbox path for goal_lean
  - dispatcher.py startup sweep
  - lsp_gateway.py did_open/did_close URI hygiene
  - Fresh-rescue stage 2 sandbox reset (_retry.py)
  - Adjust ~30-50 fixtures in test_pipeline_*

Phase 3 — Verify + Housekeeping (~2 hr)
  - verify.py promote_to_alias in transaction + olean tracking
  - library.py promote in HousekeepingTransaction
  - reflection.py marker-line append/rollback

Phase 4 — Cleanup retired ad-hoc paths (~1 hr)
  - Remove backward.py:300-330 ad-hoc snapshot
  - Remove claude_cli.py cleanup overlaps
  - Audit and delete stale rollback paths
```

Each phase one logical commit. Phase 1 lands first standalone (no
behavior change for production; just adds infrastructure + tests).

---

## 9 Open decisions resolved

| Decision | Resolution |
|---|---|
| Sandbox location | `attempts_dir/sandbox/` (inside WorkArea/SpawnWorkspace) |
| Olean handling | Tracked in real_paths, deleted on rollback (no sandbox copy) (§6.3) |
| Sweep timing | Daemon startup only |
| Sandbox dir exists at enter | Delete + recreate (sweep should have cleaned) |
| Commit atomicity | Per-file `os.replace`; multi-file partial commit accepted with idempotent retry |
| WorkArea + Sandbox separation | Merged into SpawnWorkspace |
| Commit semantics | Callback-driven `commit(real_writes=...)` from pipeline |
| Out-of-sandbox writers | SHA warning at sweep; invariant test as guard |
| LESSONS.md concurrent appends | Marker-line per spawn, surgical rollback |
| Fresh-rescue takeover | Force-rollback + re-snapshot at stage 2 entry |
| LSP URI switch | didClose + didOpen on URI change per slot |

---

## 10 Cross-references

- `docs/asterism_archive/architecture-v2.5.md` §7.3 "Commit 協議
  (atomic_pipeline)" — long-term v3 framing this design instantiates.
- `runs/sg_run_15.md` cut reason — forensic motivating this design.
- `Tooling/agent.py` `WorkArea` — retired by this design.
- `Tooling/pipeline/backward.py:300-330` — existing ad-hoc snapshot,
  retired.
- `Tooling/lsp_gateway.py` slot swap-in (`_acquire_slot`) — already
  switches file content per swap; this design adds URI hygiene
  on top.

---

## 11 Deferred follow-ups (not part of this design)

| Issue | Class | Why deferred |
|---|---|---|
| Gateway `_state.sessions[token]` memory leak after SIGKILL | Same state-leak class but server-side, not file-based | Different mechanism (memory not disk); needs gateway `keepalive` HTTP endpoint, separate PR |
| dedupe `_batch_isdefeq` temp .lean files | Short-lived, cleaned in its own try/finally | Not the same class — single-call locality |
| Asterism v3 schema migration (Goal × Strategy × Attempt × Knowledge) | Architectural | Sandbox is orthogonal and lands earlier |
| Multi-host distribution | Out of single-host scope | Speculative |

---

## 12 Test impact

736 tests pass today. Estimated fixture churn:

| Test file | Tests affected | Reason |
|---|---|---|
| `test_pipeline_backward_retry.py` | ~12 | Mock file paths now go through sandbox indirection |
| `test_pipeline_builder.py` | ~8 | Same |
| `test_verify.py` | ~6 | promote_to_alias mocking via transaction |
| `test_dispatcher.py` | ~3 | Add startup-sweep invocation expectation |
| `test_lsp_gateway.py` | ~4 | did_open/did_close URI switch expectation |
| `test_workarea_lifecycle.py` (if exists) | merge into test_spawn_sandbox.py |  |
| New: `test_spawn_sandbox.py` | ~25 tests | Invariant + crash-recovery + SHA-drift detection |
| Total fixture churn | ~35-40 tests | ~1-2 hr extra work |

**Total estimate including test churn**: Phase 1 + 2 + 3 + 4 + tests
≈ 10-12 hr work, ~970 LOC net.

---

## 13 Out of scope (explicitly)

- v3 schema migration.
- Multi-host distribution.
- Crash safety against kernel/OS crash (filesystem's job).
- Encryption.
- Gateway session memory leak (§11 deferred).
