### _progress.md

```
## Decomposition shape
`pow_csc_eq_cot_diff`: prove `1/sin(2^k·x) = cot(2^(k-1)·x) − cot(2^k·x)` pointwise, then apply `Finset.sum_congr` + telescoping algebra to close the parent sum identity.

## Sub-piece with clear formulation
**slug:** `pow_csc_eq_cot_diff`
**statement:** `∀ k : ℕ, 0 < k → 1 / Real.sin (2^k * x) = 1 / Real.tan (2^(k-1) * x) - 1 / Real.tan (2^k * x)`

Tactic shape nearly assembled: `set α := 2^(k-1)*x`, derive `2^k*x = 2*α`, then `rw [div_sub_div _ _ hsin_α hsin_2α]` + `key : cos α * sin(2α) - sin α * cos(2α) = sin α` (proved by `rw [sin_two_mul, cos_two_mul]; ring`), close with `field_simp [hsin_α]`.

## Specific blocker
Two stuck points:
1. `hsin_α` / `hcos_α` non-zero hypotheses: extracting `sin α ≠ 0` from `h₀` requires threading `Real.sin_eq_zero_iff` + the `x ≠ m*π/2^k` hypothesis; the intermediate `hx` step (`eq_div_iff` + `linarith [mul_comm]`) elaborated but couldn't be stitched with `hsin_2k` in time.
2. `div_sub_div` side-condition ordering: Lean expects `hsin_α` before `hsin_2α` and the numerator must match `cos α * sin(2α) - sin α * cos(2α)` exactly.

## Alternative direction
Skip `div_sub_div` entirely: use `have : Real.tan α - Real.tan (2*α) = 1/Real.sin(2*α)` proved by `rw [Real.tan_eq_sin_div_cos, Real.tan_eq_sin_div_cos, Real.sin_two_mul, Real.cos_two_mul]` then `field_simp [hsin_α, hcos_α]; ring` — avoids the numerator-ordering fragility of `div_sub_div`.

```
