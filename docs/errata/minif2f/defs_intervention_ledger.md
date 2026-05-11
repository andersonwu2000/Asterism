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
