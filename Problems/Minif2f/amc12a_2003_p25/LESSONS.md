<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- The hypotheses `h₁ : ∀ x, f x = Real.sqrt _` and `h₂ : {x | 0 ≤ f x} = f '' {x | 0 ≤ f x}` are inconsistent on their own (any sign of `a`): `Real.sqrt_nonneg` makes LHS = `univ`, so `h₂` forces `f` surjective, contradicting `f x ≥ 0` (e.g. take `-1 ∈ range f`).
