<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- After `rw [dif_pos h_in]` exposes the `chartInvFun` Subtype literal `⟨..., ⋯⟩`, use `simp only [hfep]` (not `rw [hfep]`) to rewrite inside it — `rw` fails with "motive is not type correct" because the proof field `⋯` (e.g. `faceEmbed_symm_mem_boundary`) depends on the value being rewritten; `simp only` handles dependent rewrites in Subtype constructors correctly.
- For any goal involving `chartInvFun p z`, first establish `hw_embed : faceEmbed z ∈ (extChartAt …).target` (from `chartTarget` membership via `Set.mem_image` + `s11670`), then `simp only [chartInvFun, dif_pos hw_embed, ...]` fires the true branch and exposes a plain `PartialEquiv.map_target`/`map_source`/`left_inv`/`right_inv` sub-goal.
- The converse of `frontier_target_of_frontier_range` (frontier-of-target → frontier-of-range) uses the same `frontier_inter_open_inter ht` equation but applied left-to-right: first `rw [Set.inter_comm] at hft` to rewrite `frontier (t ∩ range)` into `frontier (range ∩ t)`, then build `hmem : y ∈ frontier (range ∩ t) ∩ t` explicitly from `hft` and `hy.1`, then `rw [key] at hmem` and take `hmem.1`.
- To convert `q ∈ (𝓡∂ (n+1)).boundary M` into `extChartAt … q ∈ frontier (extChartAt …).target`, use `isBoundaryPoint_iff_of_mem_atlas` forward with `hn := (by exact_mod_cast ENat.top_ne_zero : (∞ : WithTop ℕ∞) ≠ 0)`, `he := chart_mem_atlas _ x`, bridge `hq` via `rwa [← extChartAt_source]`, then rewrite by the `rfl`-fact `(chartAt H x).extend I = extChartAt I x`.
- Seeded `patch.lean` skeletons here don't parse standalone (`𝓡∂`/`∞` are scoped notation, `n`/`M` binders implicit): copy `Defs.lean`'s four `open` lines plus its `variable {n} {M} [TopologicalSpace M] [ChartedSpace …] [IsManifold …]` block verbatim before the theorem; also `q.2` projects through the `Bdry` def to `q.val ∈ (𝓡∂ (n+1)).boundary M` without unfolding.
- Coordinate goals on `EuclideanSpace` need `ext j` (`funext` fails on the `WithLp`/`ofLp` wrapper), and `faceEmbed` sums collapse via `Pi.single_apply` + `Fin.succ_inj` (`EuclideanSpace.single_apply` is deprecated); `faceEmbed` also needs `open Library.Geometry.ManifoldBoundary.HalfSpaceFrontier`, which seeded skeletons lack.
