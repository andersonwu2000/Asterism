### _progress.md

```
# Progress note

## Proof approach
Contradiction via Lagrange identity: multiply h1 and h2 by L to get `dot²+DA²≤L²` (hA) and `(dot-t·L)²+DA²≤(t-1)²·L²` (hB), then use the ring identity `(t-1)·(L²-dot²-DA²) + ((t-1)²·L²-(dot-t·L)²-DA²) + t·(L-dot)² + t·DA² = 0` to derive `0 ≥ t·DA² > 0`.

## Tactic shape (already written to patch.lean)
```lean
have hD2 := sq_pos_of_ne_zero _ (sub_ne_zero.mpr hncol)
rw [hc1, hc2] at h2
-- lag_a, lag_c, bc_sq, hDeq by ring
-- hA: nlinarith [lag_a, mul_le_mul_of_nonneg_right h1 hpos.le]
-- hB: nlinarith [lag_c, bc_sq, mul_le_mul_of_nonneg_right h2 hpos.le]
nlinarith [sq_nonneg (L - dot), mul_nonneg (t-1 ≥ 0) (L²-dot²-DA² ≥ 0),
           mul_pos (t > 0) (DA² > 0)]
```

## Sticking point
Uncertain whether the final `nlinarith` closes with those hints — the polynomial certificate requires a degree-4 product `(t-1)*(L²-dot²-DA²)` where the coefficient is a variable `t-1`, which nlinarith may not handle without an explicit `mul_nonneg` subgoal. The `mul_nonneg` inner proof `0 ≤ L²-dot²-DA²` itself needs `nlinarith [hA]`.

```
