### _progress.md

```
# Progress note

## Decomposition shape
Split into 3 sub-goals: two `sin(...) ≠ 0` non-vanishing facts (drawn from `h₀`) plus one pure-algebra identity that consumes both as hypotheses; combinator just applies the algebra fact to the two non-vanishing hypotheses.

## Sub-pieces (each must include all parent binders n, x, h₀, h₁, k, then `0 < k →`)

- `sin_two_pow_k_ne_zero` — `Real.sin (2 ^ k * x) ≠ 0` (direct: apply `h₀ k hk m` after `Real.sin_ne_zero_iff` / `sin_eq_zero_iff_of_lt_of_neg` style; pick `m` from witness).
- `sin_two_pow_pred_ne_zero` — `Real.sin (2 ^ (k-1) * x) ≠ 0` (uses `h₀ k hk (2*m)` so `2m·π/2^k = m·π/2^(k-1)`; works uniformly for k=1 and k>1).
- `csc_pow_eq_cot_diff_alg` — given the two `sin ≠ 0` hypotheses, `1/sin(2^k·x) = 1/tan(2^(k-1)·x) - 1/tan(2^k·x)`. Builder per LESSONS.md: `rw [tan_eq_sin_div_cos, tan_eq_sin_div_cos]`, then `pow_succ`/`Nat.sub_add_cancel hk` to expose `2 * (2^(k-1)·x)`, then `sin_two_mul`, `cos_two_mul`, `field_simp [...]; ring`.

## Verified in LSP
Combinator type-checks with `have ... : <type> := by sorry` placeholders — goal closes after `exact h_alg h_sin_pred h_sin_k`. Sole blocker was MCP timeout when switching to real sub-goal references; structure is sound, just need to finalize patch.lean + 3 stub files.

## Alternative direction
none — direction sound.

```
