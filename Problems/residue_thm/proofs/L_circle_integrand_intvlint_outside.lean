import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- circle_integrand_intvlint_outside: ContinuousOn on [0,2π] → IntervalIntegrable via
-- continuity of deriv(circleMap), g∘circleMap, and nonvanishing denominator (ζ outside circle)
theorem circle_integrand_intvlint_outside
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r)) :
    ∀ ζ : ℂ, r < dist ζ c →
      IntervalIntegrable
        (fun θ => deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ)))
        MeasureTheory.volume 0 (2 * Real.pi) := by
  intro ζ hζ
  apply ContinuousOn.intervalIntegrable
  have hderiv : ∀ θ : ℝ, deriv (circleMap c r) θ = circleMap 0 r θ * Complex.I :=
    fun θ => (hasDerivAt_circleMap c r θ).deriv
  simp_rw [hderiv]
  apply ContinuousOn.smul
  · exact ((continuous_circleMap 0 r).mul continuous_const).continuousOn
  · apply ContinuousOn.div
    · exact hg.comp (continuous_circleMap c r).continuousOn
        (fun θ _ => circleMap_mem_sphere c hr.le θ)
    · exact ((continuous_circleMap c r).sub continuous_const).continuousOn
    · intro θ _
      intro heq
      have hmem := circleMap_mem_sphere c hr.le θ
      rw [Metric.mem_sphere] at hmem
      have hze : circleMap c r θ = ζ := sub_eq_zero.mp heq
      have hd : dist ζ c = r := hze ▸ hmem
      linarith

end Problems.residue_thm