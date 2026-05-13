### _progress.md

```
# Progress note for sum_cos_eq_sum_sin_scaled

## Decomposition shape (converged)
Single substantive sub-goal carrying the pair-and-shift identity
∑cos − ∑sin = √2·∑sin; combinator in patch.lean is one `linear_combination h_diff`.
The annotation block (3 `--` lines explaining the pair-shift strategy) is already in
patch.lean above `theorem s9417`. LSP confirmed only-sorry-warning at apply_edit.

## Sub-piece (clear formulation)
- slug: `sum_cos_sub_sum_sin_eq_sqrt_two_sum_sin` (entry_kind: Backward)
- stmt: `(∑ n ∈ Finset.Icc (1:ℕ) 44, Real.cos (n*π/180)) - (∑ n ∈ Finset.Icc (1:ℕ) 44, Real.sin (n*π/180)) = Real.sqrt 2 * (∑ n ∈ Finset.Icc (1:ℕ) 44, Real.sin (n*π/180))`
- File `new_sum_cos_sub_sum_sin_eq_sqrt_two_sum_sin.lean` is already written as stub.

## Remaining work
1. `validate_file` the stub (LSP slow, ~2min per call).
2. Final apply_edit: replace `have h_diff : ... := by sorry` with
   `have h_diff := sum_cos_sub_sum_sin_eq_sqrt_two_sum_sin` (matching auto-bound π).
   May need type ascription per LESSON 2 if π unification fails.

## Blocker
LSP throughput (~2min/call); ran out of budget after the decomposition validate.

## Alternative direction
none — direction sound. Sub-goal type-checked under parent's auto-bound π.

```
