<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To unfold `chartInvFun p z` for `z ∈ chartTarget p`, the canonical two-step is: `rw [chart_target_eq_face_embed_preimage p] at hz` to produce `hmem : faceEmbed z ∈ (extChartAt ...).target`, then `simp only [chartInvFun, dif_pos hmem]`; `rwa [← chart_target_eq_face_embed_preimage p]` fails because the rewrite must target the hypothesis not the goal.
- `Bdry n M`'s topology instance `instTopologicalSpaceBdry` is only defeq (not syntactically equal) to `instTopologicalSpaceSubtype`, so `rw` with subtype-topology lemmas (e.g. `Topology.IsInducing.subtypeVal.continuousOn_iff`) fails to match — apply them via `exact ....mpr`/term-mode instead, which unifies up to defeq.
- Sibling landed bricks (e.g., `continuous_face_proj`) are not auto-imported; any patch citing one must add `import Problems.Geometry.stokes_bdry_chart_topo.proofs.L_<slug>` explicitly, otherwise the name is unknown.
- Goals binding `(p : Bdry n M)` need the explicit `variable {n : ℕ} {M : Type*} [TopologicalSpace M] [ChartedSpace (EuclideanHalfSpace (n + 1)) M] [IsManifold (𝓡∂ (n + 1)) ∞ M]` block in patch.lean (instance binders aren't auto-bound), and BRIEF-cited `BoundaryCoord` lemmas need `import Library.Geometry.ManifoldBoundary.BoundaryCoord` since Defs.lean's import chain stops at HalfSpaceFrontier.
- Bare names like `faceProj`/`faceEmbed`/`chartToFun` fail to resolve in patch.lean because the problem's Defs.lean opens `Library.Geometry.ManifoldBoundary.{Defs,CompactBdry,HalfSpaceFrontier}` only file-locally — copy those `open` lines into your patch before the namespace.
