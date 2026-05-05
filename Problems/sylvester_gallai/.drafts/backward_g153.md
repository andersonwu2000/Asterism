### _progress.md

```
## Decomposition shape
Was converging on **decline (parent_type_infeasible)**: parent strategy s86's witness `(q, r, p)` for the q-closer subcase fails when `q` is at/near foot F and `p` is far — sub-goal as stated may still be provable but NOT via the witness pinned by the parent.

## Concrete counterexample to the parent's pinned witness
`p = (2, 0)`, `q = (0, 0)` (= foot F), `r = (0, 1)`, `s = (-1, 0)` ∈ P.
- ¬Collinear p q r ✓ (det = -3)
- Collinear p q s, s ≠ p, s ≠ q ✓
- dotQP(p) = -4, dotQP(q) = 0; dotQP(p)·dotQP(q) = 0 ≥ 0 ✓; dotQP(q)² = 0 < 16 = dotQP(p)² ✓
- Witness `(q, r, p)`: line qr = vertical x=0, perp²(p, line qr) = 4. RHS = h² = 1. Need 4 < 1 — FALSE.
- Sub-goal still satisfiable via witness `(s, r, q)`: line sr `x - y + 1 = 0`, perp²(q) = 1/2 < 1.

## Algebraic core
With F = origin, ℓ* = x-axis, r = (0, h), p = (a,0), q = (b,0): perp²(p, line qr) = h²(a-b)² / (h² + b²). Want < h². Reduces to `a² - 2ab < h²`, i.e. `a(a - 2b) < h²`. Holds iff `a ≤ 2b` (when both positive, b ≤ a). Fails when q far inside [F, p/2].

## Stuck point
Whether to (a) decline as `parent_type_infeasible` (parent pinned the wrong witness; sub-goal *as restated by parent's plan* infeasible) OR (b) accept that the sub-goal STATEMENT is still provable (just need to use `s` as witness when the (q,r,p) witness fails) and decompose with a case split on `a(a-2b) < h²` vs not, using `s` in the second case.

## Alternative direction (≤60 words)
**Decline.** The parent strategy s86 plans to pin witness `(q, r, p)` and "remaining work is the perp² inequality on this fixed triple" — but that fixed triple gives a FALSE inequality (counterexample above). Pushing the case-split (use s instead) one layer down would re-introduce the very pigeonhole on s that s86 was trying to eliminate. Decline forces s86 redesign with s factored in.

```
