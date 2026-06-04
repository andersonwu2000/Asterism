<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To prove a strict sum bound `Σ f < Σ g` use `Finset.sum_lt_sum` (needs `∀ i ∈ s, f i ≤ g i` + `∃ i ∈ s, f i < g i`); `simp [h] at h₁` with `h : n = 0` closes the `n ≠ 0` side-goal when h₁ equates the empty sum to a positive constant.
