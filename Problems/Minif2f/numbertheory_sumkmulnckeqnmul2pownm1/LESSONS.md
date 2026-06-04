<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `Finset.sum_subset` closes goals of the form `∑ x ∈ s, f x = ∑ x ∈ t, f x` when `s ⊆ t` and extra elements contribute 0; for `k * C(n,k)` sums, the `k=0` term vanishes so `simp [Finset.mem_Icc, Finset.mem_range]` + `omega` + `simp [this]` suffice for both subgoals.
