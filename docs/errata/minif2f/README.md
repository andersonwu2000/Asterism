# miniF2F errata — source-bug counterexamples found by Asterism

The miniF2F Lean transcription has known false-statement issues where the
formal version mis-translates the original AMC/competition problem. Asterism's
Backward agent identifies these by producing a `decline: unprovable`
directive with a counterexample comment in the strategy patch.

Each entry below has a kernel-verified Lean disproof (`#print axioms`
showing only `propext`/`Classical.choice`/`Quot.sound` — no `sorryAx`).

## Confirmed bugs (as of 2026-05-12)

### `amc12a_2002_p21` — recurrence over-restricted

**File:** [`amc12a_2002_p21_disproof.lean`](amc12a_2002_p21_disproof.lean)

The transcribed hypothesis `∀ n ≥ 2, u (n + 2) = (u n + u (n + 1)) % 10`
leaves `u 2` and `u 3` unconstrained — both indices are below 4 = (n+2)
when n=2 is the smallest in the constraint set. The original AMC problem
defines the recurrence for `n ≥ 0`.

Counterexample (kernel-verified): `u 0 = 4, u 1 = 7, u 2 = 10000, u 3 = 0,
u k = 0 for k ≥ 4`. Satisfies all hypotheses; `∑_{k<3} u k = 10011 > 10000`
while `1999 > 3`.

### `aime_1984_p5` — Mathlib `log` is even, signs unconstrained

**File:** [`aime_1984_p5_disproof.lean`](aime_1984_p5_disproof.lean)

Mathlib defines `Real.log` as the even extension of natural log:
`Real.log_neg_eq_log : Real.log (-x) = Real.log x`. The transcribed
statement gives the agent only logarithmic equations in `a` and `b`,
which cannot distinguish signs; but the conclusion `a * b = 512` is
sign-sensitive. The original AIME problem implicitly works over the
positive reals — the intended unique solution is `(a, b) = (64, 8)`,
but the Lean version drops the positivity assumption.

Counterexample (kernel-verified): `a = 64, b = -8`. Both hypotheses
hold (using `Real.log_neg_eq_log` to evaluate `logb 8 (-8) = logb 8 8 = 1`)
yet `a * b = -512 ≠ 512`.

### `aime_1988_p3` — missing `x > 1` precondition

**File:** [`aime_1988_p3_disproof.lean`](aime_1988_p3_disproof.lean)

The transcribed statement only requires `0 < x` (not `x > 1`). At
`x = 1`, both inner logarithms become `log_b 1 = 0`. Mathlib's convention
`Real.log 0 = 0` (and hence `Real.logb _ 0 = 0`) makes `h₁` trivially
`0 = 0`, while the conclusion `(Real.logb 2 1) ^ 2 = 27` evaluates to
`0 = 27`, which is false.

Counterexample (kernel-verified): `x = 1`. The original AIME problem
implicitly assumes `x > 1` so the inner logs are well-defined as positive
reals; the Lean statement drops that constraint.

### `mathd_numbertheory_126` — minimality scope error

**File:** [`mathd_numbertheory_126_disproof.lean`](mathd_numbertheory_126_disproof.lean)

Hypothesis `h₃` requires `a` to be minimal among `b` satisfying
`gcd b 40 = x + 3 ∧ lcm b 40 = x * (x + 3)` *for the same fixed `x`*. The
original problem demands minimality across all valid `(x', b)` pairs. Two
solutions exist: `(x=5, a=8)` and `(x=37, a=1480)`; `h₃` rules out the
second branch within `x=37` only, so `a=1480` is a valid counterexample
to the conclusion `a=8`.

## How these were found

`Asterism` is a multi-agent theorem-proving framework
(Opus Backward + Sonnet Builder, gated by `verify_strategy` mechanical
promote-to-alias). On pilot v5 runs against 20 miniF2F-valid problems,
both shelved with `failure_reason=agent_infeasible` and the agent's
counterexample comment as the strategy patch's leading block. Each
counterexample was then formalized as a standalone Lean file under this
directory and kernel-verified via `lake env lean`.

## Upstream comparison

The November-2025 paper "miniF2F-Lean Revisited" (arxiv 2511.03108)
introduced [`miniF2F_v2c`][v2c] which entirely rewrites both problems
in a multiple-choice + `IsLeast` format. The original false-as-written
statements remain in:

- [openai/miniF2F](https://github.com/openai/miniF2F)
- [yangky11/miniF2F-lean4](https://github.com/yangky11/miniF2F-lean4)
- [facebookresearch/miniF2F](https://github.com/facebookresearch/miniF2F)

No prior GitHub issue on any of these repos mentions either problem
(audited 2026-05-12).

[v2c]: https://github.com/roozbeh-yz/miniF2F_v2

## Audit script

[`audit.py`](audit.py) compares our imported Manifest statements against
miniF2F-v2c's `formal_statement` field and prints token-Jaccard similarity
per problem. Low-similarity candidates warrant manual review (mostly
turn out to be v2c's multiple-choice format conversion — not bug fixes —
except for the two confirmed bugs above).

Run (after fetching [`miniF2F_v2c.jsonl`][v2c] to this directory):
```
PYTHONPATH=. python docs/errata/minif2f/audit.py
```

## How to verify each disproof

```
cd <asterism-repo>
lake env lean docs/errata/minif2f/aime_1984_p5_disproof.lean
lake env lean docs/errata/minif2f/aime_1988_p3_disproof.lean
lake env lean docs/errata/minif2f/amc12a_2002_p21_disproof.lean
lake env lean docs/errata/minif2f/mathd_numbertheory_126_disproof.lean
```

Expected: clean elaboration. The trailing `#print axioms` line in each
file reports only `[propext, ...]` axioms; **no `sorryAx`**.
