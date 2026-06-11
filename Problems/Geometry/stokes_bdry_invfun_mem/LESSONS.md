<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To apply `isBoundaryPoint_iff_of_mem_atlas` in `∞`-smooth manifold context, provide `hn := (by exact_mod_cast ENat.top_ne_zero : (∞ : WithTop ℕ∞) ≠ 0)` with the explicit type annotation — without it Lean leaves the smoothness order metavariable unresolved and fails to find the `IsManifold` instance; afterward `(chartAt H x).extend I = extChartAt I x` is `rfl`, so `right_inv hy` closes the rewritten goal.
- To show `y ∈ frontier (extChartAt I x).target` from `y ∈ frontier (range I)` and `y ∈ target`: `rw [extChartAt_target]` decomposes target as `t ∩ range I` (where `t = I.symm ⁻¹' (chartAt H x).target`), note `IsOpen t` via `open_target.preimage continuous_symm`, then `frontier_inter_open_inter ht` gives `frontier (range I ∩ t) ∩ t = frontier (range I) ∩ t`; combine hypotheses, rewrite backward, extract `.1`.
- `frontier_range_modelWithCornersEuclideanHalfSpace` needs `[NeZero n]`; for `n+1` variables supply `haveI : NeZero (n+1) := ⟨Nat.succ_ne_zero n⟩`, then `simp [EuclideanSpace.basisFun_apply, Fin.succ_ne_zero]` closes 0-th-coordinate-equals-zero goals on `faceEmbed`-style sums (each summand uses `basisFun i.succ` whose 0-th coordinate vanishes by `Fin.succ_ne_zero`).
- Pre-seeded patch.lean skeletons here don't parse until you add `open scoped Manifold ContDiff` and `open Library.Geometry.ManifoldBoundary.CompactBdry` after the namespace line — Defs.lean's opens don't propagate, so `𝓡∂` and `Bdry` are otherwise unknown (same applies to every new_*.lean stub).
