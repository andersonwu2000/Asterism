# miniF2F wider pilot v2 — fixes validated

HEAD `7b5ea29` (entry=Backward default + event loop offload + nested layout)
Daemon pid **86536**, started 2026-05-12 00:28:40
Background task: `bww265ax1`
Scope: `Minif2f.%` (SG / PN untouched)
Pool: **15** (NOT the pool=3 hotfix — testing the actual fix)
Entry kind: Backward (all 20)

## Changes from v1 (yesterday's first wider pilot)

| Fix | Commit | Validates |
|---|---|---|
| Event loop deadlock | `ad07102` | `/verify` sync body now in `asyncio.to_thread` — pool=15 shouldn't deadlock |
| entry=Backward default | `7b5ea29` | Framework-spirit alignment — decomposition first, not Builder one-shot |
| Nested Problems layout | `608bbc5` | `Problems/Minif2f/<name>/` instead of flat `minif2f_<name>` |

## Hypothesis

1. pool=15 runs cleanly without event-loop deadlock (vs v1 where it
   accumulated 44 transient_timeouts with 0 proved)
2. Backward entry produces healthy mix: shallow decomposition for
   trivial problems, real decomposition for hard ones
3. Success rate comparable or better than v1 (pool=3 hotfix: 17/20 = 85%)
4. agent_infeasible decline still works correctly (some amc12a may
   honestly be beyond Sonnet)

## Imported problems

20 problems × 4 categories — same set as v1:

| Category | Count | Examples |
|---|---|---|
| algebra | 5 | `algebra_2complexrootspoly_xsqp49eqxp7itxpn7i`, etc |
| amc12a | 5 | `amc12a_2002_p1` through `_p24` |
| mathd_algebra | 5 | `mathd_algebra_10` / `_11` / `_101` / `_104` / `_109` |
| mathd_numbertheory | 5 | `mathd_numbertheory_101`..`_126` |

## Pending: cadence findings + final results
