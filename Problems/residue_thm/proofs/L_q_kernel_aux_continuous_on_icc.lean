import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- q_kernel_aux_continuous_on_icc: ContinuousOn of Q-kernel integrand on Icc 0 1 ×ˢ Icc 0 (2π)
-- Uses continuousOn_derivWithin for γ, circleMap sphere membership for non-vanishing denom.
theorem q_kernel_aux_continuous_on_icc
    {P Q : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {R : ℝ}
    (hR : 0 < R)
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hP_rep : ∀ z, z ≠ a → ∀ ε : ℝ, 0 < ε → ε < dist z a → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(a, ε), Q w / (w - z)))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_R : ε < R)
    (hε_sep : ∀ t ∈ Set.Icc (0:ℝ) 1, ε < dist (γ t) a) :
    ContinuousOn
      (Function.uncurry (fun (t θ : ℝ) =>
        derivWithin γ (Set.Icc (0:ℝ) 1) t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi)) := by
  -- circleMap a ε θ is never equal to a (it lives on the sphere of radius ε > 0)
  have hcm_ne_a : ∀ θ : ℝ, circleMap a ε θ ≠ a := by
    intro θ h
    have hmem := circleMap_mem_sphere a hε_pos.le θ
    simp only [Metric.mem_sphere, h, dist_self] at hmem
    linarith
  -- circleMap a ε θ ≠ γ t for t ∈ Icc 0 1 (γ t is outside the circle)
  have hne : ∀ p : ℝ × ℝ, p ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi) →
      circleMap a ε p.2 - γ p.1 ≠ 0 := by
    intro p hp h
    rw [sub_eq_zero] at h
    have hmem := circleMap_mem_sphere a hε_pos.le p.2
    rw [Metric.mem_sphere, h] at hmem
    linarith [hε_sep p.1 hp.1]
  -- Q ∘ circleMap a ε is continuous (Q analytic off {a}, circleMap avoids a)
  have hQ_cts : Continuous (fun θ => Q (circleMap a ε θ)) :=
    hQ_an.continuousOn.comp_continuous (continuous_circleMap a ε)
      (fun θ => Set.mem_diff_of_mem (Set.mem_univ _)
        (fun h => hcm_ne_a θ (Set.mem_singleton_iff.mp h)))
  -- derivWithin γ (Icc 0 1) is continuous on Icc 0 1
  have hdγ : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  -- γ is continuous on Icc 0 1
  have hγcts : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  -- deriv (circleMap a ε) is continuous (circleMap is smooth)
  have hdcm : Continuous (deriv (circleMap a ε)) :=
    (contDiff_circleMap a ε (n := ⊤)).continuous_deriv le_top
  -- Assemble: uncurry f p = f p.1 p.2
  change ContinuousOn (fun p : ℝ × ℝ =>
    derivWithin γ (Set.Icc (0:ℝ) 1) p.1 *
      (deriv (circleMap a ε) p.2 •
        (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1))))
    (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi))
  have hsmul : ∀ p : ℝ × ℝ,
      deriv (circleMap a ε) p.2 • (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1)) =
      deriv (circleMap a ε) p.2 * (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1)) :=
    fun p => smul_eq_mul _ _
  simp_rw [hsmul]
  refine ContinuousOn.mul ?_ ?_
  · exact hdγ.comp continuousOn_fst (fun p hp => hp.1)
  · refine ContinuousOn.mul ?_ ?_
    · exact hdcm.continuousOn.comp continuousOn_snd (fun p _ => Set.mem_univ _)
    · refine ContinuousOn.div ?_ ?_ ?_
      · exact hQ_cts.continuousOn.comp continuousOn_snd (fun p _ => Set.mem_univ _)
      · refine ContinuousOn.sub ?_ ?_
        · exact (continuous_circleMap a ε).continuousOn.comp
            continuousOn_snd (fun p _ => Set.mem_univ _)
        · exact hγcts.comp continuousOn_fst (fun p hp => hp.1)
      · intro p hp
        exact hne p hp

end Problems.residue_thm
