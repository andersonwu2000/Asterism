### _progress.md

```
# Progress note for s50_sub_1

## Approach
Case-split on `x ∈ {a,b,c}` and `z ∈ {a,b,c}` (9 cases); for cases not involving `c`, `ring` closes; for the 4 cases involving `c`, use `linear_combination coeff * h_simp` where `h_simp : (a.1-c.1)*(a.2-b.2) = (a.2-c.2)*(a.1-b.1)` (derived from `hcol` via `linear_combination -hcol`).

## Tactic block (complete — just needs compilation verified)
```lean
  intro p a b c x z hcol hab hx hz
  unfold Collinear at hcol
  simp only [Finset.mem_insert, Finset.mem_singleton] at hx hz
  have h_simp : (a.1 - c.1) * (a.2 - b.2) = (a.2 - c.2) * (a.1 - b.1) := by
    linear_combination -hcol
  rcases hx with rfl | rfl | rfl <;> rcases hz with rfl | rfl | rfl
  · ring  -- x=a, z=a
  · ring  -- x=a, z=b
  · linear_combination  -- x=a, z=c
      (((a.1-c.1)*(a.2-b.2) + (a.2-c.2)*(a.1-b.1)) * ((p.2-a.2)^2 - (p.1-a.1)^2) +
       2*(p.1-a.1)*(p.2-a.2)*((a.1-c.1)*(a.1-b.1) - (a.2-c.2)*(a.2-b.2))) * h_simp
  · ring  -- x=b, z=a
  · ring  -- x=b, z=b
  · linear_combination  -- x=b, z=c
      2*((a.2-b.2)*(p.1-a.1) - (a.1-b.1)*(p.2-a.2)) *
        ((a.1-b.1)*(p.1-a.1) + (a.2-b.2)*(p.2-a.2)) * h_simp
  · linear_combination  -- x=c, z=a (same coeff as x=a,z=c)
      (((a.1-c.1)*(a.2-b.2) + (a.2-c.2)*(a.1-b.1)) * ((p.2-a.2)^2 - (p.1-a.1)^2) +
       2*(p.1-a.1)*(p.2-a.2)*((a.1-c.1)*(a.1-b.1) - (a.2-c.2)*(a.2-b.2))) * h_simp
  · linear_combination  -- x=c, z=b (same coeff as x=b,z=c)
      2*((a.2-b.2)*(p.1-a.1) - (a.1-b.1)*(p.2-a.2)) *
        ((a.1-b.1)*(p.1-a.1) + (a.2-b.2)*(p.2-a.2)) * h_simp
  · ring  -- x=c, z=c
```

## Stuck point
Could not run `lake env lean patch.lean` to confirm compilation — the coefficients are derived analytically and should be correct, but need the compile check to confirm `ring` closes each `linear_combination` residual.

```
