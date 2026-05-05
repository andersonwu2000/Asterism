### _progress.md

```
# Progress note for s50_sub_3

## Approach
Case-split on membership of x, z ∈ {a,b,c} (6 non-diagonal cases via `rcases hx/hz`), assume `Collinear x p z` and derive `Collinear p a b` by contradiction, using `Collinear` = determinant `(p.1-r.1)*(q.2-r.2) = (p.2-r.2)*(q.1-r.1)`.

## Tactic shape
```lean
intro p a b c x z hpab habc hab hx hz hxz
simp only [Finset.mem_insert, Finset.mem_singleton] at hx hz
unfold Collinear at *
intro hxpz; apply hpab
rcases hx with rfl | rfl | rfl <;> rcases hz with rfl | rfl | rfl <;> simp_all
  <;> linear_combination ...
```
Cases x,z ∈ {a,b} close with `linear_combination habc` or `linarith`. Cases involving c need explicit coefficients.

## Key algebra for c-cases (e.g. x=a, z=c)
Given `habc: u*t = v*s` and `hxpz: u*w = v*r` (u=a.1-c.1, v=a.2-c.2, s=b.1-c.1, t=b.2-c.2, r=p.1-c.1, w=p.2-c.2):
- `u*(s*w - t*r) = s*(u*w) - r*(u*t) = s*(v*r) - r*(v*s) = 0`
- `v*(s*w - t*r) = 0` similarly
So `s*w - t*r = 0` iff `u=0 ∧ v=0`, but `a ≠ c` prevents that. Need `have key: u*(s*w-t*r) = 0 := by linear_combination s*hxpz - r*habc`, then case split on `a.1 = c.1 ∨ a.1 ≠ c.1` to extract `s*w - t*r = 0`, then `linear_combination` to reach goal.

## Stuck point
Finding the right `linear_combination` coefficient to go from `s*w - t*r = 0` (collinear p,b,c) to the goal `Collinear p a b`, given `habc`. The two are equivalent given collinearity of a,b,c but the exact coefficient for `linear_combination` needs verifying.

```
