<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For ℕ inequality goals of the form `a ≤ k*b` arising from a Vieta identity `a^2+b^2=(a*b+1)*k`, `zify at *` then `nlinarith [sq_nonneg ((a : ℤ) - k*b), sq_nonneg ((a : ℤ) - b), sq_nonneg ((b : ℤ))]` closes the goal directly without manual case analysis.
- When bounding a natural-number quotient `k` from an equation `(a^2+1)*k = 2*a^2`, `nlinarith [sq_nonneg a]` closes `k < 2` directly without manual `by_contra` + `Nat.mul_le_mul_left` scaffolding.
