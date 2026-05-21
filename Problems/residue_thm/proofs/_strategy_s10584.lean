import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_q_kernel_aux_continuous_on_icc
import Problems.residue_thm.proofs.L_q_kernel_deriv_eq_deriv_within_ae_prod

namespace Problems.residue_thm

-- Integrability of the Q-kernel on `Ioc 0 1 × Ioc 0 (2π)` via continuity on a compact set
-- with an auxiliary integrand using `derivWithin γ (Icc 0 1)` (continuous on `Icc 0 1`)
-- in place of the possibly-junk `deriv γ`, then transferring via a.e. equality.
--   (1) `q_kernel_aux_continuous_on_icc` — the auxiliary uncurried integrand (using
--       `derivWithin γ (Icc 0 1)` instead of `deriv γ`) is `ContinuousOn`
--       `Icc 0 1 ×ˢ Icc 0 (2π)`; on a compact set this yields `IntegrableOn`.
--   (2) `q_kernel_deriv_eq_derivWithin_ae_prod` — original and auxiliary integrands
--       agree a.e. on the product measure (they coincide on `Ioo 0 1 × Ioc 0 (2π)`,
--       whose complement in `Ioc 0 1 × Ioc 0 (2π)` is `{1} × Ioc 0 (2π)`, measure 0).
theorem s10584
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
    MeasureTheory.Integrable
      (Function.uncurry (fun (t θ : ℝ) =>
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
      ((MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1)).prod
       (MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) (2 * Real.pi))))  := by
  have h_cont :
      ContinuousOn
        (Function.uncurry (fun (t θ : ℝ) =>
          derivWithin γ (Set.Icc (0:ℝ) 1) t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi)) :=
    q_kernel_aux_continuous_on_icc hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed
      hε_pos hε_R hε_sep
  have h_eq :
      (Function.uncurry (fun (t θ : ℝ) =>
          deriv γ t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
        =ᵐ[((MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1)).prod
            (MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) (2 * Real.pi))))]
        (Function.uncurry (fun (t θ : ℝ) =>
          derivWithin γ (Set.Icc (0:ℝ) 1) t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))))) :=
    q_kernel_deriv_eq_deriv_within_ae_prod hR hQ_an hP hP_tendsto hP_rep hγ h_avoid hclosed
      hε_pos hε_R hε_sep
  have h_compact :
      IsCompact (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi)) :=
    isCompact_Icc.prod isCompact_Icc
  have h_int_aux_on :
      MeasureTheory.IntegrableOn
        (Function.uncurry (fun (t θ : ℝ) =>
          derivWithin γ (Set.Icc (0:ℝ) 1) t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi))
        (MeasureTheory.volume.prod MeasureTheory.volume) :=
    h_cont.integrableOn_compact h_compact
  have h_subset :
      Set.Ioc (0:ℝ) 1 ×ˢ Set.Ioc (0:ℝ) (2 * Real.pi) ⊆
        Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) (2 * Real.pi) :=
    Set.prod_mono Set.Ioc_subset_Icc_self Set.Ioc_subset_Icc_self
  have h_int_aux_sub :
      MeasureTheory.IntegrableOn
        (Function.uncurry (fun (t θ : ℝ) =>
          derivWithin γ (Set.Icc (0:ℝ) 1) t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
        (Set.Ioc (0:ℝ) 1 ×ˢ Set.Ioc (0:ℝ) (2 * Real.pi))
        (MeasureTheory.volume.prod MeasureTheory.volume) :=
    h_int_aux_on.mono_set h_subset
  have h_int_aux :
      MeasureTheory.Integrable
        (Function.uncurry (fun (t θ : ℝ) =>
          derivWithin γ (Set.Icc (0:ℝ) 1) t *
            (deriv (circleMap a ε) θ •
              (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
        ((MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1)).prod
         (MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) (2 * Real.pi)))) := by
    rw [MeasureTheory.Measure.prod_restrict]
    exact h_int_aux_sub
  exact h_int_aux.congr h_eq.symm

end Problems.residue_thm
