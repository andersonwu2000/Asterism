<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `contDiffOn_ext_coord_change` takes `(x x' : M)` where `x` is the **target** chart and `x'` is the source, so to get `ContDiffOn` of `extChartAt q ∘ (extChartAt p).symm` you must call `contDiffOn_ext_coord_change q.val p.val` (reversed from the composition order).
- Membership in `((extChartAt I p.val).symm ≫ extChartAt I q.val).source` splits definitionally via `refine ⟨h_target, ?_⟩` (first component is `(extChartAt p.val).target`), but the preimage component then displays `.symm.symm.symm` — normalize with `simp only [PartialEquiv.symm_symm, Set.mem_preimage]` before any `rw` against a `.symm`-stated lemma.
- The transition `((bdryChart p).symm ≫ₕ bdryChart q)` unfolds definitionally: applying it to `z` is `change chartToFun q (chartInvFun p z) = _`, and source membership `hz` yields `hz.1 : z ∈ chartTarget p` directly (no `trans_source` simp needed), after which `chartInvFun_val_eq_extChartAt_symm_faceEmbed` rewrites the inner point.
- The key names live in four different Library namespaces — `Bdry` in `Library.Geometry.ManifoldBoundary.CompactBdry`, `faceProj`/`chartToFun`/`chartSource`/`chartTarget` in `...ManifoldBoundary.Defs`, `faceEmbed` in `...ManifoldBoundary.HalfSpaceFrontier`, `bdryChart` in `...ManifoldBdry.ChartedBdry` — open all four (all reachable via the problem's Defs import) or you'll hit "Unknown identifier"/autoImplicit surprises one name at a time.
- `EuclideanSpace.proj i` now returns a `StrongDual`, which won't unify with `ContinuousLinearMap.contDiff`'s `?E →L[?𝕜] ?F` — ascribe it explicitly (`(EuclideanSpace.proj i : EuclideanSpace ℝ (Fin n) →L[ℝ] ℝ)`) in any coordinate-wise smoothness argument (faceProj/faceEmbed/chart maps).
- Pre-seeded patch.lean skeletons lack the opens that Defs.lean has, so add `open scoped Manifold ContDiff` and `open Library.Geometry.ManifoldBoundary.Defs` above the theorem yourself — otherwise `∞` fails with "expected token" and `faceProj (n := n)` with "Invalid argument name `n`".
