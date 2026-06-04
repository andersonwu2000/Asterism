<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `native_decide` is rejected by leaf-bypass (rogue `_native.native_decide.ax_*` axioms); for ~100-element `Finset.Icc` sums plain `decide` also times out — prove a closed-form via induction with `Finset.sum_Icc_succ_top` + `omega` (ℕ-sub) + `ring`, then let `rw` auto-`rfl` the final small mod.
