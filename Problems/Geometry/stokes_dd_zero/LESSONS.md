<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To discharge `minSmoothness ℝ 2 ≤ ∞` (the `hr` goal of `extDerivWithin_extDerivWithin_apply`): `∞` lives in `ℕ∞ω = WithTop ℕ∞`, so `le_top` alone fails; use `norm_num [minSmoothness]; exact WithTop.coe_le_coe.mpr le_top`.
- To evaluate `formInCoord I (mextDeriv I φ) x₀ y` for `y ∈ (extChartAt I x₀).target`: `simp only [formInCoord]`, rewrite with `Trivialization.continuousLinearMapAt_apply_of_mem ℝ _ hp` (hp : `(extChartAt I x₀).symm y ∈ (chartAt H x₀).source`, baseSet defeq), where `(mextDeriv I φ) p = mextDerivFun I φ p` is `rfl`; then `mext_deriv_triv_read` + `(extChartAt I x₀).right_inv hy` lands on `extDerivWithin (formInCoord I φ x₀) (Set.range I) y`.
- To congr through `extDerivWithin … (Set.range I) (extChartAt I x₀ x₀)` when equality holds only on `(extChartAt I x₀).target`: use `extChartAt_target_mem_nhdsWithin x₀` + `Filter.eventually_of_mem` to get the `nhdsWithin` filter eq, then close with `Filter.EventuallyEq.extDerivWithin_eq`; `extDerivWithin_congr'` won't work because it needs global `EqOn` on `Set.range I`.
- Defs.lean's opens don't propagate: every patch/sub-goal file here must itself add `open scoped Manifold Bundle ContDiff Topology` and `open Bundle Library.Geometry.Manifold.DiffFormBundle/MExtDerivCoord/MExtDeriv`, or the signature fails to parse (cryptic "expected token" at `∞`, unknown `DiffForm`/`formInCoord`).
