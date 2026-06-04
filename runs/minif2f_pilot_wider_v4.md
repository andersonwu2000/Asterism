# miniF2F wider pilot v4 — full event-loop fix validated

HEAD `40ff2a8` (gateway: all MCP tool bodies offloaded to thread pool)
Daemon pid **111508**, started 2026-05-12 01:11:01
Background task: `bbun26avc`
Scope: `Minif2f.%`, pool=15, entry=Backward × 20

## Pre-state

| | Count |
|---|---|
| Goals open | 19 |
| Goals shelved (carry from v3 kill) | 1 (Minif2f.amc12a_2002_p21, agent_infeasible) |
| Entry kind | all Backward |

The shelved goal is genuine `agent_infeasible` decline — same outcome
in v1 (pool=3 hotfix). Won't be retried this run; counts in final
total as 1 shelve.

## Pre-flight check (T+2min)

`/health` responsive within 1s (vs v3's 30s+ timeout no response —
confirms `40ff2a8` event-loop fix root-cause-resolved).

```json
{"backend_ready": true, "workers_total": 3, "workers_busy": 3,
 "sessions_active": 9, "acquires": {
   "n_hot": 0, "n_cold_warmup": 3, "n_cold_evicted": 3,
   "n_cold_noswap": 10, "n_busy_polls": 8391, "hot_rate": 0.0}}
```

- `workers_busy: 3` — all 3 lean workers actively executing (event
  loop healthy)
- `n_cold_evicted: 3` (vs v3's 27 at similar point) — slot churn
  drastically lower because event loop is responsive between calls
- `n_busy_polls: 8391` — slot contention real but no longer blocks
  event loop (polling happens in worker threads via
  `asyncio.to_thread`, not on the main loop)

**Anomaly counts at T+2min**:
- transient_timeout: 0
- release timed out: 0
- IOCP / WinError 64: 0
- Backward Goal → success: 3
- verify Strategy → proved: 3 (Goals 480, 481, 495)
- → failed: 35 (lake_build_error retries, framework correctly retrying)
- → exhausted: 0

**First 3 proofs — Backward leaf-bypass path**:

```
[backward leaf-bypass] strategy=s443 → ready_for_verify
[cascade] Backward Goal=481 → success
[verify] Strategy=443 → proved
[verify] Strategy=442 → proved
[verify] Strategy=459 → proved
```

Backward agents on trivial problems chose **leaf-bypass** (write
direct proof, no sub-goals). This is exactly the framework path we
wanted for entry=Backward on miniF2F-mix: trivial problems get a
1-spawn shortcut without wasting decomposition overhead, hard
problems get the real cascade.

## Cron monitor

Job `647cd0e2` — fires :19/:39/:59 each hour. Reports cumulative
progress + worker utilization. Auto-stops on session end (7 day max).

## Pending: cadence findings + final results
