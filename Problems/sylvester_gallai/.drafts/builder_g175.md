### _progress.md

```
# Progress note for s92_sub_1

## Approach
Pure polynomial inequality. Key polynomial identity from `hcol` (Collinear p q s):

  cross_srp² · |q-p|²  =  cross_pqr² · |s-p|²        (IDENT)

where
  cross_srp = (r.1-s.1)(p.2-s.2) - (r.2-s.2)(p.1-s.1),
  cross_pqr = (q.1-p.1)(r.2-p.2) - (q.2-p.2)(r.1-p.1),
  |s-p|²    = (s.1-p.1)² + (s.2-p.2)².

So the goal reduces to `cross_pqr² · |s-p|² < cross_pqr² · |r-s|²`,
i.e., `|s-p|² < |r-s|²` once cross_pqr² > 0 from ¬Collinear p q r.

To prove `|s-p|² < |r-s|²`: use Lagrange `|r-p|²·|q-p|² = dot_pr² + cross_pqr²`,
combined with hsame (`dot_pr·dot_sr ≥ 0`) and hdotle (`dot_pr² ≤ dot_sr²`)
which together imply `dot_pr² ≤ dot_pr·dot_sr` (case-split on signs),
hence `dot_pr² - 2·dot_pr·dot_sr ≤ -dot_pr·dot_sr ≤ 0 < cross_pqr²`.

Then `|r-s|² - |s-p|² = (|r-p|² - 2(r-p)·(s-p))` and `(r-p)·(s-p) =
(dot_pr² - dot_pr·dot_sr)/|q-p|²`, so `|q-p|²·(|r-s|² - |s-p|²) =
|r-p|²·|q-p|² - 2(dot_pr² - dot_pr·dot_sr) = cross_pqr² + dot_pr² -
2dot_pr² + 2dot_pr·dot_sr = cross_pqr² - (dot_pr² - 2dot_pr·dot_sr) > 0`.

## Tactic shape
```
intro P _ _ p hp q hq r hr hpq hncol s hs hcol hsp hsq hsame hdotle
unfold Collinear at hcol hncol
-- IDENT via linear_combination from hcol (need explicit polynomial coeff K)
have hident :
    ((r.1-s.1)*(p.2-s.2) - (r.2-s.2)*(p.1-s.1))^2 *
        ((q.1-p.1)^2 + (q.2-p.2)^2)
      = ((q.1-p.1)*(r.2-p.2) - (q.2-p.2)*(r.1-p.1))^2 *
        ((s.1-p.1)^2 + (s.2-p.2)^2) := by
  linear_combination (?? : ℝ) * hcol      -- COEFFICIENT UNKNOWN
have hcross_ne :
    (q.1-p.1)*(r.2-p.2) - (q.2-p.2)*(r.1-p.1) ≠ 0 := by
  intro h; apply hncol; linarith         -- A-B = C-D, verified by ring
have hcross_pos : 0 < ((q.1-p.1)*(r.2-p.2) - (q.2-p.2)*(r.1-p.1))^2 :=
  pow_two_pos_of_ne_zero _ hcross_ne
-- |q-p|² > 0 from hpq via Prod.ext
-- |s-p|² < |r-s|²: nlinarith [hsame, hdotle, sq_nonneg (dot_sr-dot_pr), ...]
nlinarith [hident, hcross_pos, hsame, hdotle, sq_nonneg ..., ...]
```

## Stuck point
The `linear_combination` coeffic

... (truncated; full file was 2629 chars)
```
