# Defs.lean intervention ledger

Honest record of miniF2F-244 problems where Asterism's agent shelved
with `agent_shelved` (decline: shelve — "needs helper outside Backward
scope") and was rescued by a human (Claude) writing helper definitions
into `Problems/Minif2f/<problem>/Defs.lean`.

For benchmark-integrity reporting, these proofs should be counted as
"proved with helper assistance" rather than "fully autonomous".

| Problem | Goal | Helper added | Date | Eventual outcome |
|---|---|---|---|---|
| `amc12a_2009_p25` | g596 | `noncomputable def θ : ℕ → ℝ` — Fibonacci angle sequence for the tan-addition / Pisano-period approach (θ 1 = π/4, θ 2 = π/6, θ (n+2) = θ n + θ (n+1)) | 2026-05-12 | (pending re-attempt) |
| `imo_1993_p5` | g642 | `noncomputable def goldA (n : ℕ) : ℕ := ⌊n·φ⌋.toNat` — Wythoff lower row only, no supporting lemmas. **Stress-test minimal hint**: agent must invent witness shape (`goldF n := goldA (n+1) - 1`), discover Beatty pair identity `⌊n·φ²⌋ = ⌊n·φ⌋ + n`, and prove the Hofstadter identity `⌊⌊n·φ⌋·φ⌋ = ⌊n·φ⌋ + n - 1` itself. Expected success: ~5-15%. | 2026-05-12 | (pending re-attempt; on failure, draft will guide next Theorist iteration) |

## Framework cascade marked proved but kernel-tainted (manual rollback)

These goals were marked `proved` by the framework's mechanical cascade
(per-strategy `verify_strategy` + `promote_to_alias`), but a post-hoc
`#print axioms` revealed `sorryAx` in `main`'s transitive closure. The
framework's only kernel gate, `library.maybe_promote → axiom_probe`,
fires only when **all** workspace roots are proved; under our
multi-problem run with 9 shelved roots (source-bug errata),
`db.root_proved` was permanently False and the gate never ran. The
sorryAx slipped through unnoticed.

Root cause: a sub-goal lemma `L_X.lean` that was created during a
shelved branch's exploration retained its `:= by sorry` body and was
later imported (by lemma name) by alive-chain strategies. `import` +
`apply <lemma>` works at Lake build (sorry is a warning) and at LSP
`verify_file` (Mathlib-cached, no kernel re-check), but the resulting
proof inherits sorryAx.

After manual rollback (`UPDATE goals SET status='shelved'`), these
return to the final shelved tally.

| Problem | Goal | Tainted strategy chain | Date | Note |
|---|---|---|---|---|
| `imo_1990_p3` | g641 | s9295 (root) → ... → s9590/s9652 imported shelved `L_no_prime_ge_five_dvd` / `L_two_sq_eq_one_of_prime_ge_five_dvd` / `L_coprime_m_p_sub_one` (all g1142/g1213/g1476 family). Cascade marked proved but `#print axioms main` = `[propext, sorryAx]`. | 2026-05-13 | Tracked as task #113 (forbidden_lemma should scan strategy imports against shelved goal lean_paths). |

## Adapter / framework bugs (NOT source bugs, NOT Defs.lean intervention)

Distinct category: `Benchmarks/minif2f/adapter.py` generates Defs.lean
with `open BigOperators Real Nat Topology Rat`, but the framework's
`cmd_init` generates Root.lean WITHOUT those opens. Lean 4 `import`
does NOT propagate `open` clauses across files, so symbols like `π`,
`Real.sin`, etc. in the statement become auto-bound implicit
parameters (e.g. `{π : ℝ}` free for ∀-quantification), making the
theorem trivially unprovable.

Agents correctly identified this and shelved with `agent_infeasible`.
After hand-adding `open BigOperators Real Nat Topology Rat` to Root.lean
+ DB reset, these goals re-dispatch on the correctly-elaborated
statement.

| Problem | Goal | Fix | Date | Outcome |
|---|---|---|---|---|
| `aime_1997_p11` | g567 | Added `open BigOperators Real Nat Topology Rat` to Root.lean | 2026-05-12 | (re-dispatched) |
| `imo_1965_p1` | g628 | same | 2026-05-12 | (re-dispatched) |
| `imo_1966_p4` | g629 | same | 2026-05-12 | (re-dispatched) |
| `imo_1962_p4` | g625 | same (consistency only — goal stays shelved, real source bug w/ kernel-verified disproof) | 2026-05-12 | shelved (real source bug, see errata) |

**Framework follow-up**: `cmd_init` should propagate Defs.lean's `open`
clauses into Root.lean (or always emit a standard set for miniF2F
imports). Tracked as task #108 (added after this incident).

## Shelved with `agent_shelved` but NOT actionable by Defs.lean alone

These goals had the agent decline with `agent_shelved` (a "I see a math
approach but it doesn't fit Backward scope" signal), but the indicated
approach requires more than a helper definition — it would need an
entire supporting Mathlib-style library (hundreds of lines of lemmas,
not just one `def`). Defs.lean intervention is left as `(no-op)` and
the shelve stands. Recorded for honesty.

| Problem | Goal | Agent's approach | Why Defs.lean insufficient |
|---|---|---|---|
<!-- imo_1993_p5 originally in this section (Defs.lean insufficient) — moved
to the intervention table above as a deliberate stress test of the
framework with only the minimal hint `def goldA`. Recorded honestly in
both tables to reflect the design history. -->

(currently empty)

## Policy

When a Backward shelves with `agent_shelved` (NOT `agent_infeasible`),
the agent has voluntarily declined because the proof strategy needs
helper definitions that don't fit Backward's per-strategy scope. Two
signals to look for in the patch.lean leading comment:

1. "needs to lift X to a top-level def"
2. "outside Backward's per-strategy scope"
3. agent describes a working math approach but indicates the framework
   cannot encode it as theorem-stub decomposition

If the proposed helper is mathematically standard and well-defined,
write it into the problem's `Defs.lean` and reset the goal to `open`
so the daemon re-dispatches. Update this ledger.

If the agent's shelve reason is "this problem is genuinely hard for
me / I don't see the approach", don't intervene — that's a real
shelve.

## Counted separately

The final benchmark summary will report two numbers:

- **Vanilla proved**: roots that proved without any Defs.lean
  intervention. This is the headline "Asterism × miniF2F-244" number
  for head-to-head comparison with LeanDojo / DeepSeek-Prover / Sagredo.
- **Proved with Defs.lean helper**: roots in this ledger. Reported
  separately as "framework-assisted" to be honest about what was
  autonomous.
