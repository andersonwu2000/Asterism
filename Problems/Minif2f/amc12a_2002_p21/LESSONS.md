<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- The minif2f statement is unprovable: `h₂ : ∀ n ≥ 2, u(n+2) = (u n + u(n+1)) % 10` leaves `u 2` and `u 3` unconstrained, so `u 2 := 10000` (with `u 0=4, u 1=7, u 3=0, u k=0` for k≥4) satisfies all hypotheses but gives `∑ k ∈ Finset.range 3, u k = 10011 > 10000` at n=3 < 1999 — decline as `unprovable`, do not attempt induction.
