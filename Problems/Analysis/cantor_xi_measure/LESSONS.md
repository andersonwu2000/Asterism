<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To prove `MeasurableSet` of sets defined by iterated affine images in ℝ, reduce via `IsCompact.isClosed.measurableSet` and prove `IsCompact` by induction using `IsCompact.image` with continuity of the affine maps (e.g. `continuous_const.mul continuous_id`); avoid `MeasurableSet.image` which requires a `MeasurableEmbedding` and is harder to satisfy.
- For affine image volume `volume ((fun x => a + c * x) '' S)`, use the image-as-preimage trick: rewrite as `(fun y => c⁻¹*(y-a)) ⁻¹' S`, decompose as `(·+(-a)) ⁻¹' ((c⁻¹*·) ⁻¹' S)`, apply translation invariance via `rw [← Measure.map_apply (measurable_add_const _) hmeas, map_add_right_eq_self]` (the lemma `measure_preimage_add` does NOT exist; `map_add_right_eq_self` is the correct `IsAddRightInvariant` field for Lebesgue on ℝ, confirmed used in `IntervalIntegral/Basic.lean:431`), then `Real.volume_preimage_mul_left` for scaling.
- To rewrite `ENNReal.ofReal (x ^ n)` into `ENNReal.ofReal x ^ n`, use `simp_rw [ENNReal.ofReal_pow h0]` where `h0 : 0 ≤ x`; the nonnegativity side condition is required and must be provided explicitly.
- To lift `∀ n, P n` to `∀ᶠ n in atTop, P n`, use `Filter.Eventually.of_forall` — the flat names `Filter.eventually_of_forall` and `eventually_of_forall` do not exist in current Mathlib and produce "unknown identifier/constant" errors.
- `ENNReal.tendsto_pow_atTop_nhds_zero_of_lt_one : {r : ENNReal} → r < 1 → Tendsto (r ^ ·) atTop (𝓝 0)` exists directly in Mathlib (Analysis.SpecificLimits.Basic); use it instead of converting from the real-valued version when working with ENNReal power sequences tending to 0.
- Use `ENNReal` not `ℝ≥0∞` in sub-goal theorem signatures — the `≥` in `ℝ≥0∞` is tokenized as a comparison operator outside opened scopes, causing an `expected token` parse error at build time.
