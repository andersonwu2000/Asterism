# miniF2F wider pilot — 20 problems × 4 categories

HEAD `608bbc5` (nested Problems/ via dot-slug, after revert of accidental prompts commit)
Daemon pid **105752**, started 2026-05-11 22:46:21
Background task: `be3oyygd3`
Backward model: claude-opus-4-7 / Builder: claude-sonnet-4-6
Scope: `Minif2f.%` (SG / PN remain in workspace, not dispatched)

## Hypothesis

Validate the new nested-layout framework end-to-end on a broader miniF2F
mix:

1. `init-batch Problems/Minif2f` + `run --scope 'Minif2f.%'` work for
   20 imported problems
2. TimeoutError-classification fix (commit `17c71fe`) keeps spawn-side
   timeouts from costing `attempts++` (no premature SHELVE under
   slot starvation)
3. Mixed category breakdown shows which kinds of miniF2F problems
   Sonnet Builder closes cleanly vs. which need Backward decomposition

## Imported problems (5 per category)

| Category | Problems |
|---|---|
| algebra (harder algebra section) | algebra_2complexrootspoly_xsqp49eqxp7itxpn7i, algebra_2rootsintpoly_am10tap11eqasqpam110, algebra_2rootspoly_apatapbeq2asqp2ab, algebra_2varlineareq_xpeeq7_2xpeeq3_eeq11_xeqn4, algebra_3rootspoly_amdtamctambeqnasqmbpctapcbtdpasqmbpctapcbta |
| amc12a | amc12a_2002_p1, amc12a_2002_p12, amc12a_2002_p21, amc12a_2003_p1, amc12a_2003_p24 |
| mathd_algebra | mathd_algebra_10, mathd_algebra_101, mathd_algebra_104, mathd_algebra_109, mathd_algebra_11 |
| mathd_numbertheory | mathd_numbertheory_101, mathd_numbertheory_102, mathd_numbertheory_109, mathd_numbertheory_110, mathd_numbertheory_126 |

All on disk at `Problems/Minif2f/<name>/`. DB problem slugs are
`Minif2f.<name>`. Entry kind = Builder.

## Cadence 1 — 22:55 local (+~9 min)

Daemon pid 105752 alive. Gateway ready in 37s.

DB state: **all 20 still 'open'** — gateway just warmed up, first 15
Builders dispatched simultaneously (matching pool size). 0 proved
yet.

```
algebra_           : proved=0  open=5  attempting=0  shelved=0
amc12a_            : proved=0  open=5  attempting=0  shelved=0
mathd_algebra_     : proved=0  open=5  attempting=0  shelved=0
mathd_numbertheory_: proved=0  open=5  attempting=0  shelved=0
```

**🎯 TimeoutError-classification fix validated in production**:

```
[dispatch] Builder Goal=440/441/.../454  ← 15 simultaneous (pool=15)
[cascade] worker exception on Builder Goal=440: timed out; transient_timeout (no attempts++)
[cooldown] Builder Goal=440 cooled 30s after transient_timeout
           (slot contention or RPC budget exceeded; no consec
            increment — circuit breaker reserved for true
            gateway death)
[dispatch] Builder Goal=455 pid=...
[cascade] worker exception on Builder Goal=451: timed out; transient_timeout (no attempts++)
[cooldown] Builder Goal=451 cooled 30s after transient_timeout ...
[dispatch] Builder Goal=456 pid=...
```

15 simultaneous spawns × 3 gateway worker slots = expected slot
starvation. Without `17c71fe`'s fix, those 2 timed-out goals would
have charged `attempts++` and contributed to `consec_gateway_unreachable`
(could falsely trip the circuit breaker at 8 consec).

With the fix:
- `transient_timeout` classification → `no attempts++` (preserves the
  full SHELVE_THRESHOLD=3 budget for real failures)
- 30s cooldown → re-dispatches cleanly
- No CONSEC increment → daemon doesn't think gateway is dying

Cumulative `transient_timeout` events so far: **4** (out of 15 in-
flight spawns ≈ expected when contending 15 vs 3 slots).

**Transport health**:
- 0 IOCP / WinError 64 in current gateway log
- 0 axiom_violation
- 0 dead_attempts new (the historical row 166 is from SG run, not minif2f)

**Scope-filter validation**: startup log shows `scope='Minif2f.%'`.
SG (proved) and PN (proved) are listed in `problems=` but their
goals don't appear in dispatch — bfs_refill's SQL `AND g.problem LIKE
?` correctly excludes them.

No cut. Continue monitoring.
