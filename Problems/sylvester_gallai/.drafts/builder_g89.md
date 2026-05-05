### _progress.md

```
# Progress Note

## Approach
Prove two auxiliary equalities via `have` + case-split on z, then close the main goal with a single `linear_combination` using both auxiliaries.

## Auxiliary lemmas (both proved by `rcases hz with rfl|rfl|rfl` + `linear_combination hcol` or `ring`):
```lean
have hk : (c.1 - z.1) * (a.2 - b.2) = (c.2 - z.2) * (a.1 - b.1) := by
  simp only [Finset.mem_insert, Finset.mem_singleton] at hz
  rcases hz with rfl | rfl | rfl
  · linear_combination hcol   -- z=a
  · linear_combination hcol   -- z=b
  · ring                      -- z=c, trivially 0=0
have hq : (z.1 - b.1) * (a.2 - b.2) = (z.2 - b.2) * (a.1 - b.1) := by
  simp only [Finset.mem_insert, Finset.mem_singleton] at hz
  rcases hz with rfl | rfl | rfl
  · ring                      -- z=a, uv=vu
  · ring                      -- z=b, 0=0
  · linear_combination hcol   -- z=c
```

## Main close (no case split needed):
```lean
linear_combination
  (((c.1-z.1)*(a.2-b.2)+(c.2-z.2)*(a.1-b.1))*((p.2-z.2)^2-(p.1-z.1)^2) +
   2*(p.1-z.1)*(p.2-z.2)*((c.1-z.1)*(a.1-b.1)-(c.2-z.2)*(a.2-b.2))) * hk -
  (2*((p.1-z.1)*(a.2-b.2)-(p.2-z.2)*(a.1-b.1)) +
   ((z.1-b.1)*(a.2-b.2)-(z.2-b.2)*(a.1-b.1))) * ((c.1-z.1)^2+(c.2-z.2)^2) * hq
```

## Stuck point
The previous attempt (direct `linear_combination K*hcol` after `rcases rfl`) failed with "Unknown identifier `a`" — `rcases rfl` on `z=a` was likely eliminating `a` instead of `z` (both free vars). The `have`-based approach avoids this because the main `linear_combination` runs with `z` still a free variable (no case split in outer context). The algebraic identity is verified: `LHS - RHS = K1*(hk_LHS-hk_RHS) - K2*(hq_LHS-hq_RHS)` by polynomial ring identity. The `linear_combination hcol` inside the have blocks works regardless of subst direction (verified by ring check both ways). Key risk: `ring` inside the final `linear_combination` may time out on the degree-4 polynomial.

```
