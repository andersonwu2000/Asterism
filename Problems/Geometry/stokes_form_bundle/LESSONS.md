<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- When proving goals involving `alternatization h.toContinuousMultilinearMap`, include `ContinuousAlternatingMap.coe_toContinuousMultilinearMap` in the initial `simp only` block so that `h.toContinuousMultilinearMap (v ∘ σ)` reduces to `h (v ∘ σ)` before any `simp_rw` with `map_perm`-derived rewrites — without it, `simp_rw [hperm]` makes no progress.
- To case-split on `u : ℤˣ` being ±1 (e.g. `Equiv.Perm.sign σ`), use `rcases Int.isUnit_iff.mp (Units.isUnit u) with h | h`; then convert `(u : ℤ) = 1` → `u = 1` via `Units.val_eq_one.mp (by exact_mod_cast h)` and `(u : ℤ) = -1` → `u = -1` via `Units.ext h` — `Int.units_eq_iff` does not exist in this Mathlib version.
- `ContDiff.comp` on a function through `compContinuousLinearMapContinuousMultilinear` fails because `NormedAddCommGroup (ContinuousMultilinearMap ℝ M G →L[ℝ] ContinuousMultilinearMap ℝ M' G)` synthesis times out — `show`-casts and explicit `haveI ContinuousLinearMap.toNormedAddCommGroup` both still fail since the `addCommMonoid` path (`ContinuousMultilinearMap.addCommMonoid` vs `NormedAddCommGroup.toAddCommGroup.toAddCommMonoid`) mismatches; bypass `ContDiff.comp` entirely and use `CPolynomialAt.contDiffAt` instead.
- For `alternatization`-scalar goals, use `simp only [alternatization_apply_apply, ContinuousAlternatingMap.smul_apply, ContinuousMultilinearMap.smul_apply, Finset.smul_sum, smul_comm c]` — bare `smul_comm` (without the explicit `c`) causes max-recursion because simp loops on the ℝ/ℤˣ interaction.
- Signatures using `ℕ∞ω` fail with cryptic `unexpected identifier; expected '}'` unless your patch/stub file adds `open scoped ContDiff` itself — Defs.lean opens it but scoped notation does not propagate to importers.
