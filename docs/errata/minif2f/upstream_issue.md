# Upstream issue draft — 9 kernel-verified errata in `yangky11/miniF2F-lean4`

Target repository: <https://github.com/yangky11/miniF2F-lean4>
Audited against `MiniF2F/Valid/` as of 2026-05-12.

## Suggested issue title

> 9 false-as-written theorems in `MiniF2F/Valid` (kernel-verified counterexamples attached)

## Suggested issue body (paste into GitHub)

---

While running an automated theorem-proving framework against
`MiniF2F/Valid/`, our agent reported nine theorems as `unprovable`
with explicit counterexamples. We formalized each counterexample as
a standalone Lean 4 disproof and verified that the negation of the
transcribed statement is a kernel-clean theorem (only `propext` /
`Classical.choice` / `Quot.sound`, **no `sorryAx`**).

Each bug below has its own `#print axioms`-clean disproof file. We
are happy to upstream the disproofs as a PR if useful, or to keep
them in our errata directory (links available on request).

### Bug class summary

| # | Theorem | Class |
|---|---|---|
| 1 | `imo_1967_p3` | `∏` body precedence cuts off subtraction |
| 2 | `imo_1962_p4` | answer-set step too fine (admits non-solutions) |
| 3 | `amc12a_2020_p13` | ℕ-division trivializes radical-tower equation |
| 4 | `mathd_algebra_282` | ℕ-division in cube root term |
| 5 | `aime_1988_p3` | missing `x > 1` precondition + log convention |
| 6 | `aime_1984_p5` | `Real.log` even ⇒ sign unconstrained |
| 7 | `amc12a_2002_p21` | recurrence over-restricted (`∀ n ≥ 2` leaves u₂, u₃ free) |
| 8 | `mathd_numbertheory_126` | minimality scope error |
| 9 | `mathd_algebra_433` | answer value simply wrong (f(8) = 1, not 19) |

### Detailed bugs

#### 1. `imo_1967_p3` — `∏` body precedence cuts off subtraction

Mathlib's `BigOperators` notation `∏ i ∈ s, body` declares body at
precedence 67. Natural-subtraction is at precedence 65, so the RHS

```lean
∏ i ∈ Finset.Icc 1 n, c (m + i) - c k
```

parses as `(∏ i ∈ Finset.Icc 1 n, c (m + i)) - c k` — product, then
subtract — not the intended IMO 1967 P3 product of differences
`∏ i ∈ Finset.Icc 1 n, (c (m + i) - c k)`.

**Counterexample** (kernel-verified): `k = 5, m = 1, n = 2, c(s) = s · (s + 1)`.
All four hypotheses hold; LHS = `c 1 · c 2 = 12`, RHS = `c 2 · c 3 − c 5 = 72 − 30 = 42`;
`12 ∤ 42`.

**Fix**: parenthesize the body — `∏ i ∈ Finset.Icc 1 n, (c (m + i) - c k)`.

#### 2. `imo_1962_p4` — answer-set step too fine

The third and fourth branches of the answer set use step `π / 6`, but
the IMO 1962 #4 solution `cos(3x) = 0` requires step `π / 3` (from
`3x = π/2 + kπ`). The over-fine step admits `x = 0` as a member of
the RHS (third branch, `m = -1`), but `cos²(0) · 3 = 3 ≠ 1`, so `0`
is not in the LHS.

**Counterexample**: take `S` as the LHS set; then `0 ∈ RHS` but `0 ∉ S`.

**Note**: [facebookresearch/miniF2F PR #36](https://github.com/facebookresearch/miniF2F/pull/36)
has merged a fix for this in their fork, but `yangky11/miniF2F-lean4`
still ships the broken version.

**Fix**: change the step in branches three and four to `π / 3`.

#### 3. `amc12a_2020_p13` — ℕ-division trivializes the equation

The exponents `1/a`, `1/b`, `1/c`, `1/36` are all evaluated as natural-
number division because `a b c : ℕ` and the literals elaborate as ℕ.
For any natural `k ≥ 2`, `1 / k = 0`. So `n ^ (1/k) = n ^ 0 = 1` under
the monoid power on `NNReal`, collapsing both sides of `h₂` to
`1 = 1` regardless of `n`. The conclusion `b = 3` is completely
unconstrained.

**Counterexample**: `a = b = c = 2, n = 2`. The original AMC 2020 12A
#13 uses real exponents (a radical tower); the Lean transcription
uses ℕ-division, trivializing the constraint.

**Fix**: cast exponents to `ℝ` (or use a fractional power on `NNReal`).

#### 4. `mathd_algebra_282` — ℕ-division in cube root

The first term `f (8 ^ (1 / 3))` intends `8^(1/3) = 2` (the cube root),
but Lean elaborates `1 / 3` as ℕ-division (both literals are ℕ), so
`1 / 3 = 0` and `(8 : ℝ) ^ (0 : ℕ) = 1`. The term becomes `f(1) = 1`,
not `f(2) = 2`, and the sum becomes `1 + 9 + 64 + 4 = 78 ≠ 79`.

**Counterexample**: any `f` satisfying both `h₀` and `h₁` is forced to
`f(1) = 1`, `f(-π) = 9`, `f(√50) = 64`, `f(9/2) = 4` — sum 78.

Same ℕ-division pattern as `amc12a_2020_p13`.

**Fix**: cast `1/3` to ℝ (or use `Real.rpow`).

#### 5. `aime_1988_p3` — missing `x > 1` precondition

The transcribed statement only requires `0 < x` (not `x > 1`). At
`x = 1`, both inner logarithms become `log_b 1 = 0`. Mathlib's
convention `Real.log 0 = 0` (and hence `Real.logb _ 0 = 0`) makes
`h₁` trivially `0 = 0`, while the conclusion `(Real.logb 2 1) ^ 2 = 27`
evaluates to `0 = 27`, false.

**Counterexample**: `x = 1`.

**Fix**: strengthen `h₀ : 0 < x` to `h₀ : 1 < x`.

#### 6. `aime_1984_p5` — `Real.log` is even, signs unconstrained

Mathlib defines `Real.log` as the even extension of natural log:
`Real.log_neg_eq_log : Real.log (-x) = Real.log x`. The transcribed
statement gives only logarithmic equations in `a` and `b`, which
cannot distinguish signs; but the conclusion `a * b = 512` is
sign-sensitive. The original AIME problem implicitly works over the
positive reals — the intended unique solution is `(a, b) = (64, 8)` —
but the Lean version drops the positivity assumption.

**Counterexample**: `a = 64, b = -8`. Both hypotheses hold (using
`Real.log_neg_eq_log` to evaluate `logb 8 (-8) = logb 8 8 = 1`), yet
`a * b = -512 ≠ 512`.

**Fix**: add `0 < a` and `0 < b` (or constrain via `b > 1`, `a > 0` etc.).

#### 7. `amc12a_2002_p21` — recurrence over-restricted

Hypothesis `∀ n ≥ 2, u (n + 2) = (u n + u (n + 1)) % 10` leaves `u 2`
and `u 3` unconstrained — both indices are below 4 = (n+2) when n=2
is the smallest in the constraint set. The original AMC problem
defines the recurrence for `n ≥ 0`.

**Counterexample**: `u 0 = 4, u 1 = 7, u 2 = 10000, u 3 = 0, u k = 0
for k ≥ 4`. Satisfies all hypotheses; `∑_{k<3} u k = 10011 > 10000`
while the conclusion asserts `1999 > 3`.

**Fix**: change recurrence quantifier to `∀ n, u (n + 2) = (u n + u (n+1)) % 10`.

#### 8. `mathd_numbertheory_126` — minimality scope error

Hypothesis `h₃` requires `a` to be minimal among `b` satisfying
`gcd b 40 = x + 3 ∧ lcm b 40 = x * (x + 3)` **for the same fixed `x`**.
The original problem demands minimality across all valid `(x', b)`
pairs. Two solutions exist: `(x=5, a=8)` and `(x=37, a=1480)`; `h₃`
rules out the second branch within `x=37` only, so `a=1480` is a valid
counterexample to the conclusion `a=8`.

**Fix**: rewrite minimality as `∀ x' b, gcd ... → lcm ... → a ≤ b`.

#### 9. `mathd_algebra_433` — answer value simply wrong

The expected value is wrong. With `f x = 3 · √(2x - 7) - 8`,
`f 8 = 3 · √9 - 8 = 9 - 8 = 1`, not 19. Either the source MATH-dataset
problem asked for a different point or had a different expected value.

**Counterexample**: `f x = 3 · √(2x - 7) - 8` satisfies `h₀`
reflexively but `f(8) = 1`.

**Fix**: recompute correct value from original source.

---

### How to reproduce

Each disproof is a standalone Lean 4 file. Per file:

```bash
lake env lean docs/errata/minif2f/<name>_disproof.lean
```

Expected output: clean elaboration; the trailing `#print axioms`
returns `[propext, Classical.choice, Quot.sound]` (no `sorryAx`).

### Methodology

`Asterism` is a multi-agent theorem-proving framework (Opus Backward
+ Sonnet Builder). On a 244-problem pilot against `MiniF2F/Valid/`,
nine agents shelved with `failure_reason=agent_infeasible` and an
explicit counterexample comment as the strategy patch's leading
block. Each counterexample was then formalized as a kernel-clean
disproof and committed alongside the framework's audit ledger.

We audited against the November-2025 [`miniF2F_v2c`](https://github.com/roozbeh-yz/miniF2F_v2)
which rewrites two problems in `IsLeast` format; the other seven are
not addressed by `v2c`. We also checked `openai/miniF2F`,
`facebookresearch/miniF2F`, and prior GitHub issues on each repo —
no existing issue mentions these nine theorems (audited 2026-05-12),
with the one exception of `imo_1962_p4` (fixed in `facebookresearch`
PR #36 but never merged here).

---

## Notes for the maintainer

- Disproofs can be released as a single PR adding `Errata/` directory,
  or kept private. We prefer PR.
- If desired, our adapter can also generate fixed versions of the
  statements (open-source patch) — willing to contribute.
- Eight of these are formal-version-only bugs (the original
  competition problems are correct); they're transcription bugs and
  fixing them does not alter the dataset's mathematical content.

## Audit metadata (for our own use, do not paste into GitHub)

- Dispatched via: `python -m Tooling.adapters.minif2f` import + pilot run
- Pilot date: 2026-05-12
- Framework: Asterism v2 (HEAD `562d8a9` at time of disproof writeup; `147bec5` post-fix)
- Disproof commits (chronological): `4cf375e`, `bd29b48`, `c237d67`, `e752d5f`, `5c7de7d`, `afa23bf`, `ff8f187`
  + amc12a_2002_p21 + mathd_numbertheory_126 (earlier batch)
- Output of `lake env lean docs/errata/minif2f/<each>_disproof.lean` is in conversation log
