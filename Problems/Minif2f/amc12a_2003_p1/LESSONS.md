<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `native_decide` elaborates clean but framework's leaf-bypass post-build axiom check rejects the `_native.native_decide.ax_1_1` it introduces; for finite-sum computations use `Finset.sum_congr` + `Finset.sum_add_distrib` + `Finset.sum_const` + `Finset.card_range` then `omega`/`ring` instead.
