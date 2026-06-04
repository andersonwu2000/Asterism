# SG run #8 — autonomous monitor log

HEAD: 722472d (fresh-rescue + all prior fixes)
Background task: b2gg137l1
Daemon pid: 94796
Started: 2026-05-10T00:09:58Z

## Cumulative fixes being validated
- bail option (commit b6ece82)
- TIMEOUT salvage + bail discriminator strict (2504650)
- forensic bug fix (55e38f6)
- fresh-rescue replaces 2-phase rescue (722472d)
- snapshot-once / cascade race / leaf-bypass axiom probe / decline directives (prior session)

## Cadence findings (autonomous)


### Cadence at 2026-05-10T00:21Z (~25min into run)
- daemon: alive (pid 94796)
- goals: 1 proved (sg_noncollinear_finset_nonempty), 2 attempting (root + sg_kelly_ordinary), 1 unknown — total 3 goals
- hot_rate: 47.8%, cold_evicted: 1
- pipelines done: 2 (Backward 271→success, Builder 273→proved)
- fresh-rescue events: 0
- **timeout-salvage events: 1** ← `sid=e6c3b132 salvaged outcome=success despite subprocess timeout` (Backward 271 root)
- agent_bailed events: 0
- decline reason distribution: none yet
- anomalies: none

**Notable**: TIMEOUT salvage worked on the very first goal (root Backward 271). watchdog defer fired (silence=30s < 480s threshold), agent ran past wall_cap to full subprocess timeout 900s, salvage parse_fn caught valid output and returned success. This is the g266-class anomaly fix in action — would have been discarded under pre-2504650 logic.

### Cadence at 2026-05-10T00:41Z (~45min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 1 attempting root, 1 attempting (272 retry, attempts=1)
- hot_rate: 62.2% (up from 47.8%), cold_evicted: 1 (no growth)
- pipelines done: 3 (added Backward 272 → exhausted)
- fresh-rescue events: 0 (no STUCK_THINKING yet)
- timeout-salvage events: 1 cumulative (still just the g271 success from cadence #1)
- agent_bailed events: 0
- decline reason distribution: 1 agent_timeout (g272 first try)
- anomalies: none

**Notable**: g272 (sg_kelly_ordinary) hit watchdog wall_cap with silence=0s (agent active) → defer → subprocess timeout 900s → salvage parse called but returned non-terminal (no `[timeout-salvage] salvaged` log line) → postmortem path → exhausted as agent_timeout. attempts=1, dispatcher spawned new pipeline e9dc44c2 for retry. Behavior is correct: salvage tried, agent didn't have shippable output, fell through normally. No regression.

### Cadence at 2026-05-10T01:01Z (~65min into run)
- daemon: alive (pid 94796)
- goals: 1 proved (273), 2 attempting (271 root, 272 retry-success), 1 open (274 kelly_smaller_triple depth-2)
- hot_rate: 60.5%, cold_evicted: 1
- pipelines done: 4 (added Backward 272 retry → success)
- fresh-rescue events: 0 (no STUCK_THINKING events firing — idle-window guard handling everything)
- timeout-salvage events: 1 cumulative (still just g271)
- agent_bailed events: 0
- decline reason distribution: 1 agent_timeout (g272 first try)
- anomalies: none

**Notable**: g272 (sg_kelly_ordinary) recovered on retry. The retry pipeline (e9dc44c2) hit watchdog wall_cap with silence=300s < 480s → deferred → agent finished between wall_cap (720s) and subprocess timeout (900s) → clean rc=0 → cascade success, no salvage needed. This is the IDEAL idle-window guard outcome: agent gets extra ~180s budget and finishes. Tree growing: g274 kelly_smaller_triple (depth-2) just dispatched.

### Cadence at 2026-05-10T01:21Z (~85min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 2 attempting (271, 272), 1 open (274 retry, attempts=1)
- hot_rate: 60.5% (same), cold_evicted: 1
- pipelines done: 5 (added Backward 274 → exhausted)
- **fresh-rescue events: 1 (in flight)** — broken_sid=386b3c15 → fresh_sid=9f528d51, prior_analysis_dumped=True
- timeout-salvage events: 1 cumulative (g271)
- agent_bailed events: 0
- decline reason distribution: 2 agent_timeout (g272 first try, g274 first try)
- anomalies: none

**MAJOR EVENT**: First fresh-rescue triggered on g274 (kelly_smaller_triple) retry pipeline 2f888447. sid=386b3c15 hit watchdog with silence=690s (>480s threshold = truly stuck), killed for rescue. Helper dumped prior thinking from broken jsonl successfully (`prior_analysis_dumped=True`), minted fresh sid 9f528d51, fresh-cold rescue spawn in flight. Waiting for `[fresh-rescue] sid=9f528d51 rc=... dur=...s` to see if mechanism works in production. Note also: g274 first try pipeline 5c4fac6a hit watchdog with silence=240s (active, deferred) → subprocess timeout 900s → no salvage success → exhausted as agent_timeout.

### Cadence at 2026-05-10T01:41Z (~105min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 2 attempting, 1 open (g274 attempts=2)
- hot_rate: 60.5% (no acquires growth — workers idle while g274 stuck)
- pipelines done: 5 (no new completions)
- **fresh-rescue events: 1 completed** — sid=9f528d51 rc=128 dur=720s **(FAILED — fresh session also stuck-killed!)**
- timeout-salvage events: 1 cumulative
- agent_bailed events: 0
- decline reason distribution: 2 agent_timeout + 1 agent_stuck_thinking pending
- anomalies: **fresh-rescue did NOT recover the broken session as expected from probe**

**MAJOR FINDING — fresh-rescue failure mode**:

The fresh session (9f528d51, freshly minted, prior_analysis dumped) ALSO hit watchdog stuck-thinking with silence=690s. So even with a clean session id and prior analysis available as a file, Sonnet still entered the deep-thinking pattern on this goal.

This is qualitatively different from the probe finding. Probe (16176de5 → 236ced1d) shipped patch + sub-lemma in 4min. Production fresh-rescue (386b3c15 → 9f528d51) entered same stuck-thinking and got killed at wall_cap.

Possible reasons (speculation, not verified):
1. **Goal-inherent difficulty**: kelly_smaller_triple (depth-2) is genuinely too hard for Sonnet adaptive thinking, regardless of session state.
2. **MCP overhead** in production vs probe: probe didn't have full MCP setup.
3. **Probe goal was simpler** (kelly_min_ordinary, depth-1).

Goal 274 retry loop continues: helper buffered agent_stuck_thinking, will try iter 2 (warm retry on fresh sid 9f528d51) — but that session is already broken too. May enter cycle.

**Cut criterion check**: original cut was "same sid ≥3 fresh-rescue fails" — but each fresh-rescue mints a NEW sid by design, so this never triggers. **Cut criterion needs reframing** when wakeful (e.g. "consecutive fresh-rescue rc=128 across sids ≥3"). For now: continuing to observe; goal-level shelve_threshold=5 will eventually catch g274 if pattern persists.

### Cadence at 2026-05-10T02:01Z (~125min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 2 attempting, 1 open (g274 attempts=3/5, approaching shelve)
- hot_rate: 60.5% (no growth — workers idle on g274)
- pipelines done: 6 (added Backward 274 second try → exhausted)
- **fresh-rescue events: 1 cumulative (rc=128 fail)** — fresh sid 9f528d51 ALSO got stuck-killed
- timeout-salvage events: 1 cumulative
- agent_bailed events: 0
- decline reason distribution: 3 agent_timeout + 1 agent_stuck_thinking
- anomalies: g274 stuck-thinking pattern persists across all rescue mechanisms

**g274 second pipeline (2f888447) full sequence**:
1. iter 0 main (sid=386b3c15): STUCK_THINKING after 720s wall_cap + 690s idle
2. fresh-rescue (sid=9f528d51): ALSO STUCK_THINKING after 720s + 690s idle → rc=128
3. iter 1 warm (reused sid=9f528d51): wall_cap deferred (silence=300s < 480s) → subprocess timeout 900s → postmortem 180s timeout → exhausted

**Net waste per failed g274 pipeline**: ~3 × 900s ≈ 45 min wall, 0 deliverable. shelve_threshold=5, currently at attempts=3 → 2 more iterations before shelve. Then dispatcher will probably try Builder on parent g272 or shelve cascade.

Not at cut yet (1/3 fresh-rescue fails; 3 agent_timeout not strictly consecutive due to g272 success between). Continuing.

**Pattern getting clearer**: kelly_smaller_triple (depth-2) appears genuinely too hard for Sonnet under current adaptive thinking — every spawn enters deep thinking, hits max_tokens or wall_cap, no progress regardless of session state.

### Cadence at 2026-05-10T02:21Z (~145min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 2 attempting, 1 open (g274 attempts=4/5 — one more failure → shelve)
- hot_rate: 60.5% (no growth — workers idle on g274 cycles)
- pipelines done: 7 (added g274 third try → exhausted)
- **fresh-rescue events: 2 attempted** — first sid=9f528d51 rc=128 fail; second sid=4d477057 IN FLIGHT (broken_sid=3e325786, prior_analysis_dumped=True)
- timeout-salvage events: 1 cumulative
- agent_bailed events: 0
- decline reason distribution: 4 agent_timeout + 1 agent_stuck_thinking
- anomalies: g274 stuck pattern continues; 3 consecutive g274 pipelines exhausted with agent_timeout

**Cut criterion check**:
- "≥4 consecutive same-reason dead_attempts" — last 4 are agent_timeout but interleaved with 1 agent_stuck_thinking, so technically not 4 strictly consecutive. Borderline.
- "shelve_threshold reached" — g274 at 4/5, next failure auto-shelves.
- 2 fresh-rescue completed/in-flight, not at the (poorly-defined) "≥3 same sid" cut.

**Decision**: NOT cutting yet. g274 will auto-shelve on next failure (one more iteration), which will naturally:
- propagate shelve to parent g272
- propagate to root g271
- pipeline may terminate via root-shelved condition

Continuing observation. If second fresh-rescue (4d477057) also fails AND g274 shelves cleanly, the system is recovering itself — no manual cut needed. If something pathological happens (gateway crash, hot_rate drop, unbounded retry), cut then.

### Cadence at 2026-05-10T02:41Z (~165min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 1 attempting (271 root), 1 open (272 attempts=2), **1 SHELVED (274 attempts=5/5)**
- hot_rate: 60.5% (still no growth)
- pipelines done: 8 (added g274 fourth try → exhausted)
- **fresh-rescue events: 2 completed, both rc=128 fail** (sid=9f528d51, sid=4d477057)
- timeout-salvage events: 1 cumulative
- agent_bailed events: 0
- decline reason distribution: 4 agent_timeout + 2 agent_stuck_thinking
- shelved%: 25% (1/4) — well below 70% cut
- anomalies: g274 shelved (expected); system recovering — dispatcher moved to retry g272

**System recovery happening as designed**:
1. g274 (kelly_smaller_triple, depth-2) accumulated 5 attempts → auto-shelved
2. Cascade did NOT propagate shelve up to parent g272 (g272 status reset to open with attempts=2)
3. Dispatcher spawned new Backward pipeline e5ceeabe for g272 — system trying a fresh decomposition with knowledge that the prior split's child was unprovable

**Key observations on fresh-rescue mechanism**:
- Both fresh-rescue events were on g274 (the truly hard goal)
- Both fresh sessions ALSO entered deep-thinking deadlock and got stuck-killed
- prior_analysis dump worked (no errors); but Sonnet didn't use it productively to avoid the deadlock
- This suggests: fresh-rescue helps when session contamination is the issue (the probe case), but NOT when the goal itself triggers Sonnet's deep-thinking even fresh

**Cost so far**: ~165min wall, 1 proved, 1 shelved, 0 fresh-rescue salvages. baseline run #4 had 4 proved by similar wall time. **Lower productivity** likely because:
- this run has different decomposition (sg_kelly_ordinary instead of run #4's split)
- g274 stuck cycle ate ~80 min wall on a single shelved goal
- 4 spawn budgets per pipeline × 4 pipelines × ~15 min/spawn ≈ 240 min cumulative spawn time on g274 alone

System working as designed (no infinite loop, shelves properly), but the new mechanisms didn't avoid g274's cycle. Continue monitoring.

### Cadence at 2026-05-10T03:01Z (~185min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 1 attempting (271 root), 1 open (272 attempts=3/5), 1 shelved (274)
- hot_rate: 62.5% (slight uptick), cold_evicted: 1
- pipelines done: 9 (added Backward 272 retry → exhausted)
- fresh-rescue events: 2 cumulative (both rc=128 fail on g274)
- timeout-salvage events: 1 cumulative
- agent_bailed events: 0
- decline reason distribution: 5 agent_timeout + 2 agent_stuck_thinking
- shelved%: 25% (1/4)
- anomalies: g272 retry pattern emerging — first retry pipeline e5ceeabe exhausted with agent_timeout (sid=4749bee1, deferred at silence=180s, then subprocess timeout 900s + postmortem 180s). Now g272's second retry (7403196c) in flight.

**g272 retry analysis**: After g274 shelved, dispatcher gave g272 a fresh decomposition attempt. This pipeline (e5ceeabe) was a NEW Backward attempt — agent presumably saw g274 as a shelved sub-goal in goal_history (decline directive infrastructure should surface this). But the new attempt also timed out. So either:
1. g272 itself is hard regardless of decomposition strategy (more likely)
2. Or the new decomposition encountered another stuck-thinking sub-lemma without going through fresh-rescue (no STUCK_THINKING in this pipeline — it was deferred-then-timeout, no rescue path)

Pattern across the run:
- Pipelines ending agent_timeout (deferred + subprocess timeout): 5
- Pipelines ending agent_stuck_thinking (rescue paths): 2 (both g274)
- Successful pipelines: 3 (271, 272 first-try-retry-success, 273)

Run is grinding. g272 needs 2 more failures to shelve. If both fail: g272 shelves → root g271 cascade → run terminates.

**Wall time so far ≈ 185min, productivity 1 proved**. baseline run #4 was 4 proved at 270min. Compounded: this run will likely end with 1-2 proved (273 + maybe 272 if a retry succeeds), root SHELVED (not proved). That's a worse outcome than baseline.

Continuing observation. No cut criteria hit.

### Cadence at 2026-05-10T03:21Z (~205min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 2 attempting (271 root, 272 retry-success), 1 open (275 NEW sub kelly_smaller_triple_2), 1 shelved (274)
- hot_rate: 60.0% (down slightly), cold_evicted: 1
- pipelines done: 10 (added g272 second retry → SUCCESS)
- fresh-rescue events: 2 cumulative
- timeout-salvage events: 1 cumulative
- agent_bailed events: 0
- decline reason distribution: 5 agent_timeout + 2 agent_stuck_thinking
- shelved%: 20% (1/5)
- anomalies: g275 first attempt (a380a92e) in flight, hit watchdog deferred (silence=270s) → subprocess timeout 900s; will probably also struggle

**g272 RETRY SUCCEEDED!**: pipeline 7403196c (sid=4d2f413b) - watchdog wall_cap deferred (silence=330s < 480s) → cascade success. This is g272's third pipeline attempt. New decomposition produced sub-goal g275 (kelly_smaller_triple_2), which is suspiciously similar to the shelved g274 (kelly_smaller_triple). The agent likely re-derived the same decomposition under a slightly different name.

**g275 first try already pre-deadlocking**: pipeline a380a92e watchdog deferred (silence=270s) → subprocess timeout 900s. May follow g274's path: 5 attempts then shelve.

**System forecast**: If g275 follows g274's pattern, ~60-90 more min wall to shelve g275, then g272 cascade-up shelve, then g271 cascade-up shelve, then run terminates. Total wall ~5 hr, no useful root progress.

Cut criteria still NOT triggered:
- shelved%: 20% (well below 70%)
- consecutive same-reason dead_attempts: not strictly 4 same
- gateway healthy
- hot_rate 60%

Continuing.

### Cadence at 2026-05-10T03:41Z (~225min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 2 attempting (271, 272), 1 open (275 attempts=1/5), 1 shelved (274)
- hot_rate: 58.6% (slight decline), cold_evicted: 1 (no growth)
- pipelines done: 11 (added g275 first try → exhausted)
- **fresh-rescue events: 3 attempted** — 9f528d51 rc=128, 4d477057 rc=128, e7750c8c IN FLIGHT
- timeout-salvage events: 1 cumulative
- agent_bailed events: 0
- decline reason distribution: 6 agent_timeout + 2 agent_stuck_thinking
- shelved%: 20% (1/5)
- anomalies: g275 (kelly_smaller_triple_2) following g274's pattern exactly — first pipeline a380a92e exhausted, second pipeline ddf48b3e triggered fresh-rescue (sid=8676839b → fresh_sid=e7750c8c), in flight

**g275 deja vu of g274**:
- g275 first try (a380a92e, sid=25935cfd): wall_cap deferred (silence=270s) → subprocess timeout 900s → postmortem 180s timeout → another 120s timeout → exhausted
- g275 second try (ddf48b3e, sid=8676839b): wall_cap stuck-kill at silence=510s → fresh-rescue with sid=e7750c8c (third fresh-rescue event of run, in flight)

**Pattern confirmed**: Sonnet's deep-thinking trap is goal-content-driven, not session-state-driven. The "smaller triple" lemma family triggers it consistently, regardless of:
- which decomposition produced it (g274 from first g272, g275 from second g272)
- whether session is fresh or warm
- whether prior_analysis is available

**Cumulative wall**: ~225min (3hr 45min). Productivity: 1 proved (273), 1 shelved (274). Compared to baseline run #4: 4 proved at 270min. **Run is significantly less productive than baseline** because g274/g275 cycles each consume ~75-90min wall.

Cut criteria: NOT triggered. Continuing.

### Cadence at 2026-05-10T04:01Z (~245min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 2 attempting, 1 open (g275 attempts=2/5), 1 shelved
- hot_rate: 59.3%, cold_evicted: 1
- pipelines done: 11 (no change since last cadence — currently working through g275 second pipeline)
- **fresh-rescue events: 3 completed** — sid=9f528d51 rc=128, sid=4d477057 rc=128, sid=e7750c8c **rc=124 (TIMEOUT, different mode)**
- timeout-salvage events: 1 cumulative
- agent_bailed events: 0
- decline reason distribution: 6 agent_timeout + 2 agent_stuck_thinking
- shelved%: 20% (1/5)
- anomalies: third fresh-rescue completed differently (rc=124 instead of rc=128) — agent was active in fresh session, deferred at watchdog wall_cap, then subprocess timeout

**Third fresh-rescue (e7750c8c) flow**:
- broken_sid=8676839b → fresh_sid=e7750c8c, prior_analysis_dumped=True
- fresh session: watchdog wall_cap with silence=240s (active, deferred)
- subprocess timeout 900s → fresh-rescue rc=124

**NEW design gap noticed**: helper's fresh-rescue path treats any non-OK rc as `agent_stuck_thinking` buffer. But rc=124 (TIMEOUT) isn't really stuck — the fresh agent was active, just didn't finish. **Should fresh-rescue rc=124 also trigger salvage parse?** Currently skipped, even though TIMEOUT path on regular spawns has salvage. This is a code gap: salvage logic only applies to main spawn TIMEOUT, not to fresh-rescue spawn TIMEOUT. Worth user attention when wakeful.

g275 helper now continues retry loop. Probably another iter against warm fresh sid e7750c8c → likely also stuck/timeout.

Cumulative wall ~245min, productivity 1 proved + 1 shelved. Continuing observation.

### Cadence at 2026-05-10T04:21Z (~265min into run)
- daemon: alive (pid 94796)
- goals: 1 proved, 2 attempting, 1 open (g275 attempts=3/5), 1 shelved
- hot_rate: 59.3% (no change), cold_evicted: 1
- pipelines done: 11 (no new completions — currently inside g275 second pipeline grinding)
- **fresh-rescue events: 4 attempted** — 9f528d51 rc=128, 4d477057 rc=128, e7750c8c rc=124, 68d9f792 rc=124
- timeout-salvage events: 1 cumulative
- agent_bailed events: 0
- decline reason distribution: 6 agent_timeout + 2 agent_stuck_thinking
- shelved%: 20% (1/5)
- anomalies: **recursive fresh-rescue within single pipeline** — g275 pipeline ddf48b3e burning through fresh-rescues:
  - iter 0 main (sid=8676839b) → STUCK → fresh-rescue #3 (e7750c8c) rc=124
  - iter 1 warm (sid=e7750c8c reused) → STUCK → fresh-rescue #4 (68d9f792) rc=124
  - **same pipeline, 2 fresh-rescues, both rc=124 timeout**

**Pattern is now stable / predictable**:
- Every fresh-rescue on this hard-goal class fails (rc=128 stuck or rc=124 timeout)
- Within a single pipeline, helper retries → triggers another fresh-rescue → another fail → another fresh-rescue → ...
- Each pipeline burns ~30-40min wall on 2 fresh-rescues alone

**Cut criteria assessment**:
- Original "same sid ≥3 fresh-rescues" — design flaw, never triggers (each fresh-rescue mints new sid)
- "≥4 consecutive same-reason" — borderline; recent failures are timeout-heavy but mixed with stuck
- shelved% 20% — far below 70%
- gateway healthy

**Decision: NOT cutting.** System is wasting wall but technically progressing (g275 attempts=3/5, will auto-shelve in ~2 more iterations ≈ 60-90 min). Letting it terminate naturally to gather more data on the failure pattern.

**Forecast for run end**:
- g275 reaches attempts=5 → auto-shelve (~60-90 min)
- Cascade may shelve g272 (currently attempts=3/5) or g272 may re-decompose again
- If g272 also exhausts → root g271 cascade-shelve → run terminates
- Estimated remaining wall: 2-3 hours
- Final estimated state: 1 proved (g273), root shelved

---

## FINAL SUMMARY (run terminated by 4hr30min budget cutoff)

**Termination reason**: `[dispatcher] 16200s budget exceeded; stopping` — natural budget exhaustion, NOT crash, NOT cut.

**Total wall**: 00:10:20 → 04:40:54 UTC = **270 min** (exactly the budget)

### Final state

| Goal | slug | status | attempts | depth |
|---|---|---|---|---|
| 271 | main | attempting | 0 | 0 |
| 272 | sg_kelly_ordinary | attempting | 3/5 | 1 |
| 273 | sg_noncollinear_finset_nonempty | **proved** | 0 | 1 |
| 274 | kelly_smaller_triple | **shelved** | 5/5 | 2 |
| 275 | kelly_smaller_triple_2 | open | 4/5 | 2 |

### Pipeline outcomes

| kind/status | count |
|---|---|
| Backward succeeded | 3 |
| Backward failed | 8 |
| Builder succeeded | 1 |
| **Total** | 12 |

### Failure reason breakdown (11 dead_attempts)

| reason | count |
|---|---|
| agent_timeout | 7 |
| agent_stuck_thinking | 4 |

### New mechanism statistics

| mechanism | count | success | comment |
|---|---|---|---|
| timeout-salvage | 1 | 1 (g271 root saved) | works when agent ships before subprocess timeout |
| fresh-rescue | 4 | 0 | all on hard goals (g274/g275); all failed (rc=128 stuck or rc=124 timeout) |
| agent_bailed | 0 | n/a | agents did not use bail option (always entered deep thinking) |
| watchdog idle-window defer | 9+ | n/a | mechanism active; productive agents avoided premature kill |

### Comparison vs baseline run #4 (270min wall)

| metric | run #4 (no new mech) | run #8 (all new mech) |
|---|---|---|
| wall | 270min | 270min (budget cutoff) |
| proved | 4 | **1** |
| shelved | 5 | 1 |
| root status | unknown (probably partial) | unproved (root never finished) |

**Run #8 was significantly less productive than baseline.**

### Root cause analysis

1. **Hard sub-lemmas trigger Sonnet's deep-thinking trap consistently**: kelly_smaller_triple (g274) and its rename kelly_smaller_triple_2 (g275) both entered max_tokens deadlock on EVERY attempt, regardless of:
   - session state (broken vs fresh)
   - prior_analysis availability (dumped successfully but Sonnet didn't avoid the deadlock)
   - which decomposition produced the sub-lemma (g272 first vs g272 retry)

2. **fresh-rescue mechanism fails on goal-content-driven deadlocks**: 4 fresh-rescue attempts, 0 successes. The probe (16176de5 → 236ced1d) worked because the original was just a session-state issue; production runs with hard goals show the deadlock is goal-content driven.

3. **Recursive fresh-rescue within single pipeline observed**: g275 pipeline ddf48b3e did 2 fresh-rescues in one helper retry loop (e7750c8c → 68d9f792, both rc=124). Burning ~30-40min wall per failed pipeline on rescue cycles alone.

4. **One unambiguous win**: timeout-salvage saved g271 root from being discarded after subprocess timeout — confirms that mechanism is sound for the cargo-cult-pattern anomaly (commit 2504650).

### Observations / design gaps for user attention

- **fresh-rescue rc=124 (TIMEOUT) doesn't go through salvage parse** like main spawn TIMEOUT does. Code gap in `_retry.py` STUCK_THINKING branch — fresh-rescue is treated as binary OK/fail; TIMEOUT path's salvage logic isn't applied.
- **Cut criterion "same sid ≥3 fresh-rescue fails" never triggers by design** because each fresh-rescue mints a new sid. Better criterion: "≥3 fresh-rescue failures within N minutes" or "≥2 consecutive fresh-rescue failures regardless of sid."
- **fresh-rescue's value proposition is questionable for production**: the probe success was on session-state contamination; production runs show hard goals don't benefit. **Maybe roll back fresh-rescue and accept that hard goals shelve faster?** Pre-fresh-rescue, --resume rescue at 180s budget produced 0 events but completed in 3 min instead of 25+ min per fresh-rescue cycle.
- **The deeper issue is Sonnet's adaptive thinking on hard goals**: no framework-side mechanism we've tried (idle-window guard, salvage, bail, fresh-rescue) prevents Sonnet from hitting max_tokens on these specific lemmas. Real fix likely requires either: (a) Anthropic API thinking budget cap (deprecated/unreliable per docs), (b) drastically lower `--effort medium`, or (c) different model.

### State for next session

- Daemon stopped (budget exhaustion).
- Cron `bbf7cd10` deleted.
- Code uncommitted: none (all fixes through 722472d already committed + pushed).
- Files dirty: only daemon-managed Problems/sylvester_gallai state (proofs, .attempts, etc.) — typical post-run.
- Next session decisions: roll back fresh-rescue? Tune effort? Different goal selection? See observations above.
