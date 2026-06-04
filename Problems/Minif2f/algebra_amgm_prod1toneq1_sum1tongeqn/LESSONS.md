<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `Real.finsetProd_rpow s f hs r : (∏ i ∈ s, f i ^ r) = (∏ i ∈ s, f i) ^ r` bridges the AM-GM output form `∏ x i ^ w` to the goal form `(∏ x i) ^ w`; `rw [Real.finsetProd_rpow _ _ hx] at amgm` rewrites the hypothesis after applying AM-GM.
- Mathlib's `Real.geom_mean_le_arith_mean_weighted (s) (w z) (hw_nn) (hw_sum1) (hz_nn) : ∏ i in s, z i ^ w i ≤ ∑ i in s, w i * z i` is the canonical AM-GM pivot; specialize with uniform weights `w i = 1/n` to deduce `n ≤ ∑ x` from `∏ x = 1`.
