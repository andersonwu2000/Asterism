<!--
Ready-to-post GitHub issue body for yangky11/miniF2F-lean4.

  gh issue create \
    --repo yangky11/miniF2F-lean4 \
    --title "9 false-as-written theorems in MiniF2F/Valid (kernel-verified counterexamples)" \
    --body-file docs/errata/minif2f/upstream_issue.md
-->

While running an automated theorem-proving framework against
`MiniF2F/Valid/`, our agents reported nine theorems as `unprovable`
with explicit counterexamples. We then formalized each counterexample
as a standalone Lean 4 disproof and verified that the negation of the
transcribed statement is a kernel-clean theorem (only `propext` /
`Classical.choice` / `Quot.sound`, **no `sorryAx`**).

These nine theorems appear to be **transcription bugs** — the
formalization in Lean does not match the original competition / dataset
problem. The mathematical content of the original problems is
unaffected; only the formal transcription needs adjustment.

> **Note on suggested intent**: The "Apparent intent" lines below
> describe how each theorem appears to fail compared to the original
> competition statement. We have not exhaustively cross-checked every
> case against the primary competition source (AMC / AIME / IMO
> archives, MATH dataset originals). Maintainers are in the best
> position to decide the canonical fix.

## Bug class summary

| # | Theorem | Class |
|---|---|---|
| 1 | `imo_1967_p3` | `∏` body precedence cuts off subtraction |
| 2 | `imo_1962_p4` | answer-set step too fine (admits non-solutions) |
| 3 | `amc12a_2020_p13` | ℕ-division trivializes radical-tower equation |
| 4 | `mathd_algebra_282` | ℕ-division in cube root term |
| 5 | `aime_1988_p3` | missing precondition + log convention |
| 6 | `aime_1984_p5` | `Real.log` even ⇒ sign unconstrained |
| 7 | `amc12a_2002_p21` | recurrence over-restricted (`∀ n ≥ 2` leaves u₂, u₃ free) |
| 8 | `mathd_numbertheory_126` | minimality scope error |
| 9 | `mathd_algebra_433` | answer value disagrees with stated `f` |

## Detailed bugs

### 1. `imo_1967_p3` — `∏` body precedence cuts off subtraction

Mathlib's `BigOperators` notation `∏ i ∈ s, body` declares body at
precedence 67. Natural-subtraction is at precedence 65, so

```lean
∏ i ∈ Finset.Icc 1 n, c (m + i) - c k
```

parses as `(∏ i ∈ Finset.Icc 1 n, c (m + i)) - c k` — a product, then
subtract — rather than a product of differences.

**Counterexample**: `k = 5, m = 1, n = 2, c(s) = s · (s + 1)`. All four
hypotheses hold; LHS = `c 1 · c 2 = 12`; RHS = `c 2 · c 3 − c 5 = 72 − 30 = 42`;
`12 ∤ 42`.

**Apparent intent**: the IMO 1967 P3 statement is a product of
differences `∏ i ∈ Finset.Icc 1 n, (c (m + i) - c k)`.

### 2. `imo_1962_p4` — answer-set step too fine

The third and fourth branches of the answer set use step `π / 6`,
admitting `x = 0` as a member (third branch, `m = -1`), but
`cos²(0) · 3 = 3 ≠ 1`, so `0` is not in the LHS.

**Counterexample**: take `S` as the LHS set; then `0 ∈ RHS` but `0 ∉ S`.

**Apparent intent**: the IMO 1962 #4 solution `cos(3x) = 0` has form
`3x = π/2 + kπ`, giving step `π / 3`.

**Note**: [facebookresearch/miniF2F PR #36](https://github.com/facebookresearch/miniF2F/pull/36)
has merged a fix in their fork; this repo still ships the broken version.

### 3. `amc12a_2020_p13` — ℕ-division trivializes the equation

The exponents `1/a`, `1/b`, `1/c`, `1/36` are evaluated as natural-number
division because `a b c : ℕ` and the literals elaborate as ℕ. For any
`k ≥ 2`, `1 / k = 0`, so `n ^ (1/k) = n ^ 0 = 1` (monoid power on
`NNReal`), collapsing both sides of `h₂` to `1 = 1` regardless of `n`.
The conclusion `b = 3` is then unconstrained.

**Counterexample**: `a = b = c = 2, n = 2`.

**Apparent intent**: the original AMC 2020 12A #13 uses real-valued
radical exponents, not ℕ-division.

### 4. `mathd_algebra_282` — ℕ-division in cube root

The first term `f (8 ^ (1 / 3))` intends `8^(1/3) = 2` (cube root), but
Lean elaborates `1 / 3` as ℕ-division (both literals are ℕ), so
`1 / 3 = 0` and `(8 : ℝ) ^ (0 : ℕ) = 1`. The term becomes `f(1) = 1`
rather than `f(2) = 2`; the sum becomes `1 + 9 + 64 + 4 = 78 ≠ 79`.

**Counterexample**: any `f` satisfying both `h₀` and `h₁` is forced to
`f(1) = 1`, `f(-π) = 9`, `f(√50) = 64`, `f(9/2) = 4`. Same ℕ-division
pattern as `amc12a_2020_p13`.

### 5. `aime_1988_p3` — missing precondition

The transcribed statement only requires `0 < x` (not `x > 1`). At
`x = 1`, both inner logarithms become `log_b 1 = 0`. Mathlib's
convention `Real.log 0 = 0` (and hence `Real.logb _ 0 = 0`) makes `h₁`
trivially `0 = 0`, while the conclusion `(Real.logb 2 1) ^ 2 = 27`
evaluates to `0 = 27`.

**Counterexample**: `x = 1`.

**Apparent intent**: the original AIME 1988 #3 implicitly assumes
`x > 1` so the inner logs are well-defined positive reals.

### 6. `aime_1984_p5` — `Real.log` is even, signs unconstrained

Mathlib defines `Real.log` as the even extension of natural log:
`Real.log_neg_eq_log : Real.log (-x) = Real.log x`. The transcribed
statement gives only logarithmic equations in `a` and `b`, which cannot
distinguish signs; the conclusion `a * b = 512` is sign-sensitive.

**Counterexample**: `a = 64, b = -8`. Both hypotheses hold (using
`Real.log_neg_eq_log` to evaluate `logb 8 (-8) = logb 8 8 = 1`), yet
`a * b = -512 ≠ 512`.

**Apparent intent**: the original AIME 1984 #5 works over positive
reals with intended solution `(a, b) = (64, 8)`.

### 7. `amc12a_2002_p21` — recurrence over-restricted

Hypothesis `∀ n ≥ 2, u (n + 2) = (u n + u (n + 1)) % 10` leaves `u 2`
and `u 3` unconstrained — both indices are below `n+2 = 4` when n=2
is the smallest in the constraint set.

**Counterexample**: `u 0 = 4, u 1 = 7, u 2 = 10000, u 3 = 0, u k = 0
for k ≥ 4`. Satisfies all hypotheses; `∑_{k<3} u k = 10011 > 10000`
while the conclusion asserts `1999 > 3`.

**Apparent intent**: the original AMC problem defines the recurrence
from index 0.

### 8. `mathd_numbertheory_126` — minimality scope error

Hypothesis `h₃` requires `a` to be minimal among `b` satisfying
`gcd b 40 = x + 3 ∧ lcm b 40 = x * (x + 3)` **for the same fixed `x`**.
The original problem demands minimality across all valid `(x', b)`
pairs. Two solutions exist: `(x=5, a=8)` and `(x=37, a=1480)`; `h₃`
rules out the second branch within `x=37` only.

**Counterexample**: `a = 1480` (from the `x=37` branch).

**Apparent intent**: minimality should range over the joint
`(x, b)` solution set.

### 9. `mathd_algebra_433` — answer value disagrees with stated `f`

With `f x = 3 · √(2x - 7) - 8`, `f 8 = 3 · √9 - 8 = 9 - 8 = 1`, not 19.

**Counterexample**: `f x = 3 · √(2x - 7) - 8` satisfies `h₀`
reflexively but `f(8) = 1`.

**Apparent intent**: either the input point or the expected value
should be different from the original MATH-dataset transcription.

## How we verified

Each bug has a corresponding standalone Lean 4 disproof file whose
trailing `#print axioms` returns `[propext, Classical.choice, Quot.sound]`
(no `sorryAx`). Happy to share these as a PR adding an `Errata/`
directory, as a gist, or attached inline on request — whatever fits
your preferred workflow.

## Methodology

The bugs were surfaced by [Asterism](https://github.com/andersonwu2000/Asterism),
an automated theorem-proving framework, run over `MiniF2F/Valid/`.
Each agent shelved with `failure_reason=agent_infeasible` and an
explicit counterexample comment as its strategy's leading block; we
then formalized each counterexample as a kernel-clean disproof.

We checked `openai/miniF2F`, `facebookresearch/miniF2F`, and the
[miniF2F_v2c](https://github.com/roozbeh-yz/miniF2F_v2) rewrite, plus
prior GitHub issues on each repo — no existing issue mentions these
nine theorems (audited 2026-05-12), with the one exception of
`imo_1962_p4` (fixed in `facebookresearch` PR #36 but never synced
here).
