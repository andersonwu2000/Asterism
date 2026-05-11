# miniF2F pilot — 5 mathd_algebra problems

HEAD `2bcad9f` (Benchmarks/ separation + adapter)
Daemon pid **103560**, started 2026-05-11 19:44:48
Background task: `bg7mhau3d`
Backward model: claude-opus-4-7 / Builder: claude-sonnet-4-6 (current Asterism.yaml)

## Purpose

Validate end-to-end:
- miniF2F adapter generates valid Asterism Problem dirs
- Framework dispatches Builder on imported problems
- LSP gateway elaborates `import Mathlib` + `set_option maxHeartbeats 0`
- Get first pilot success/failure numbers for demo

## Imported problems

| Slug | Original miniF2F name |
|---|---|
| minif2f_mathd_algebra_10 | mathd_algebra_10 |
| minif2f_mathd_algebra_101 | mathd_algebra_101 |
| minif2f_mathd_algebra_104 | mathd_algebra_104 |
| minif2f_mathd_algebra_109 | mathd_algebra_109 |
| minif2f_mathd_algebra_11 | mathd_algebra_11 |

All entry_kind=Builder (miniF2F problems are leaf-shaped — single-shot
proof attempts rather than multi-level decomposition).

## Cadence 1 — 19:51 local (+~7 min)

Daemon pid 103560 alive. Gateway alive.

**🎯 First miniF2F problem proved**: `mathd_algebra_10` (Goal=435).

DB state:
- Goal 435 (mathd_algebra_10): **proved** (attempts=1)
- Goal 436, 437, 438: open / in-flight Builder
- Goal 439 (mathd_algebra_11): open, attempts=1 (retry in flight)

**Framework discovery — slot starvation under parallel pilot dispatch**:

```
[dispatch] Builder Goal=435/436/437/438/439 — 5 simultaneous spawns
[cascade] worker exception on Builder Goal=435: timed out; treating as failed
[cascade] worker exception on Builder Goal=439: timed out; treating as failed
[dispatch] Builder Goal=435/439 re-dispatched
```

Gateway `/health` after the timeouts:
- `workers_total: 3` (gateway slot pool)
- `sessions_active: 7` (5 + 2 retries)
- `hot_rate: 0.26` (75% acquires were cold — high churn)

**Root cause**: gateway worker pool size (3) < simultaneous Builder
spawns (5). Spawns 4 and 5 wait for slot, some inner RPC times out
during the wait, exception propagates → framework counts as failed
attempt + 30s cooldown + re-dispatch. The re-dispatched spawn
eventually got a slot and succeeded (Goal 435 → proved).

**Severity**: medium for benchmark runs.
- Per-problem still succeeds (re-dispatch path works)
- BUT slot starvation costs an `attempts++`. For miniF2F's
  `SHELVE_THRESHOLD=3`, 3 slot-starvation timeouts could premature
  shelve a problem that would actually be solvable.
- 5-problem pilot ran into 2 timeouts on first wave. For 244-problem
  benchmark with N concurrent spawns, the issue scales linearly.

**Fix candidates (post-pilot)**:
1. Classify `TimeoutError` from slot-wait as transient infra (like
   `gateway_unreachable`) → no attempts++, just cooldown + retry
2. Bump gateway worker pool from 3 → 5-8 (matches typical concurrent
   spawn count)
3. Throttle dispatcher to ≤ workers_total simultaneous spawns

Recommend (1) — cheapest, preserves existing parallelism, just fixes
the misclassification.

**Transport health (real)**:
- 0 IOCP / WinError 64 in current gateway log
- 0 axiom_violation events
- 0 `gateway_unreachable` (gateway is healthy; timeouts are slot-wait)

No cut. Continue monitoring.

## TERMINATION — 2026-05-11 20:02:34 — 🏆 5/5 proved + library-promoted

Daemon idle-exited cleanly. Wall time **~18 min** (19:44:48 → 20:02:34).
Background task `bg7mhau3d` reported rc=0.

**Final results — 5/5 success on mathd_algebra mini-batch**:

| Problem | Status | Attempts | Library promote |
|---|---|---|---|
| minif2f_mathd_algebra_10 | ✅ proved | 1 (1 slot-starvation timeout, then succeeded) | ✅ |
| minif2f_mathd_algebra_101 | ✅ proved | 0 | ✅ |
| minif2f_mathd_algebra_104 | ✅ proved | 0 | ✅ |
| minif2f_mathd_algebra_109 | ✅ proved | 0 | ✅ |
| minif2f_mathd_algebra_11 | ✅ proved | 1 (1 slot-starvation timeout, then succeeded) | ✅ |

All 5 axiom-clean (`Classical.choice`, `Quot.sound`, `propext` —
mathlib standard trio). Re-exported to `Library/Misc/`.

**Transport health**:
- 0 IOCP / WinError 64 across entire run
- 1 release timeout (gracefully handled)
- 2 spawn-side timeouts on first wave (Goal=435, 439) — both
  recovered via re-dispatch
- 0 axiom_violation events
- 0 cascade verify failures (mechanical-only design held — only 5
  root verifies fired, one per problem at library promote time)

**Cost estimate** (Sonnet Builder 5× ≈ 30s LLM time per spawn × 7
spawns including retries ≈ 3-4 min cumulative billed time, ~$1-2
total).

## Conclusions

**Pilot validates end-to-end miniF2F adapter + framework integration**:
1. ✅ `Benchmarks/minif2f/adapter.py` parses real-world miniF2F format
2. ✅ Generated `Manifest.md` / `Defs.lean` accepted by Asterism's
   `cli init` — root goal seeded as Builder entry kind correctly
3. ✅ Framework dispatches Builder Sonnet, gets proofs back, library
   promotes with axiom check
4. ✅ Verify-collapse design works on miniF2F problems too — all 5
   went through one root verify each (no per-strategy cascade because
   no decomposition needed; Builder closes the leaf directly)

**Framework findings (valuable for proposal)**:

### 1. Slot-starvation timeout misclassification

5 simultaneous Builder dispatches × 3 gateway worker slots →
2 spawns timed out waiting. Framework's `_classify_worker_exception`
doesn't recognize `TimeoutError` as transient infra → counts as
real failure → attempts++ → cooldown + re-dispatch.

For miniF2F's SHELVE_THRESHOLD=3, 3 slot-starvation timeouts could
prematurely shelve a solvable problem. Recommend post-pilot fix:
classify TimeoutError as transient infra alongside `gateway_unreachable`.

### 2. 100% success rate on simple algebra batch

mathd_algebra_10 / 11 / 101 / 104 / 109 all closed by Sonnet Builder
on first real attempt (modulo slot-starvation transients). This
suggests the framework reaches at least baseline competence on
high-school-algebra-level miniF2F problems.

### 3. ~18 min wall for 5 problems @ 3 worker slots

Projection for full miniF2F validation (244 problems):
- Optimistic (all easy, no decomposition): 244 / 5 × 18 min ≈ **15 hours**
- Realistic (mix of difficulties, some need Backward decomp): **24-48 hours**

Recommend chunked runs of 20-50 problems each rather than one
244-problem batch. Easier to spot framework issues + iterate.

## Proposed next steps

| Priority | Action |
|---|---|
| **High** | Fix TimeoutError classification (no attempts++ for slot-starvation) |
| **High** | Run wider pilot: 20 problems × 3 categories (algebra, numbertheory, induction) to see if any category fails systematically |
| Medium | Bump gateway worker pool from 3 → 5-8 for benchmark runs |
| Medium | Add per-category metrics to run notes (Problem-Solving Strategies coverage) |
| Low | Full 244-problem benchmark (after fixes + wider pilot validates) |

For proposal demo: **5/5 on mathd_algebra is real, defensible data**.
Shows the framework actually closes miniF2F problems — even with the
slot-starvation issue, the recovery path worked.
