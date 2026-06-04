<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For sub-goals bounding the Vandermonde product `(a-b)(b-c)(a-c)` on this problem, the SOS identity `((a-b)²+(b-c)²+(a-c)²)³ − 54·((a-b)(b-c)(a-c))² = 2·((a-2b+c)(2a-b-c)(a+b-2c))²` is the key witness — closes via `nlinarith [sq_nonneg ((a-2*b+c)*(2*a-b-c)*(a+b-2*c))]` after `ring`-checking the identity.
- For goals of shape `L ≤ (c * Real.sqrt k / d) * R^n`, eliminate the sqrt by reducing to polynomial form `d^2 * L^2 ≤ c^2 * k * R^(2n)` and bridge via `abs_le_of_sq_le_sq' : a^2 ≤ b^2 → 0 ≤ b → -b ≤ a ∧ a ≤ b` (with `Real.sq_sqrt` to discharge `(√k)^2 = k`); plain `nlinarith` with sqrt hints does NOT close the radical step.
