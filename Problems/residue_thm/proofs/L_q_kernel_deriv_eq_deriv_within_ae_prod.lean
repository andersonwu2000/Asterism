import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- q_kernel_deriv_eq_deriv_within_ae_prod: deriv γ and derivWithin γ (Icc 0 1) agree
-- a.e. on Ioc 0 1 × Ioc 0 (2π); they coincide on interior Ioo 0 1 via
-- derivWithin_of_mem_nhds + Icc_mem_nhds, and the exceptional point {1} in Ioc 0 1
-- has Lebesgue measure zero, making the product-measure of the bad set zero.
theorem q_kernel_deriv_eq_deriv_within_ae_prod
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
    (Function.uncurry (fun (t θ : ℝ) =>
        deriv γ t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t)))))
      =ᵐ[((MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1)).prod
          (MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) (2 * Real.pi))))]
      (Function.uncurry (fun (t θ : ℝ) =>
        derivWithin γ (Set.Icc (0:ℝ) 1) t *
          (deriv (circleMap a ε) θ •
            (Q (circleMap a ε θ) / (circleMap a ε θ - γ t))))) := by
  simp only [Filter.EventuallyEq, Function.uncurry]
  rw [MeasureTheory.ae_iff]
  have hm : MeasurableSet (Set.univ \ Set.Ioo (0:ℝ) 1) :=
    MeasurableSet.univ.diff measurableSet_Ioo
  -- (ℝ \ Ioo 0 1) ∩ Ioc 0 1 = {1}, so the Ioc-restricted Lebesgue measure is 0 there
  have h0 : (MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1))
            (Set.univ \ Set.Ioo (0:ℝ) 1) = 0 := by
    rw [MeasureTheory.Measure.restrict_apply hm]
    have hset : (Set.univ \ Set.Ioo (0:ℝ) 1) ∩ Set.Ioc (0:ℝ) 1 = {(1:ℝ)} := by
      ext x
      simp only [Set.mem_inter_iff, Set.mem_diff, Set.mem_univ, true_and, Set.mem_Ioo,
                 not_and_or, not_lt, Set.mem_Ioc, Set.mem_singleton_iff]
      constructor
      · rintro ⟨h | h, h1, h2⟩
        · linarith
        · exact le_antisymm h2 h
      · rintro rfl; exact ⟨Or.inr le_rfl, zero_lt_one, le_rfl⟩
    rw [hset]; simp
  -- bad set ⊆ (ℝ \ Ioo 0 1) × univ: if t ∈ Ioo 0 1 then Icc 0 1 ∈ nhds t
  -- so derivWithin γ (Icc 0 1) t = deriv γ t, contradicting membership in bad set
  apply MeasureTheory.measure_mono_null
      (show {p : ℝ × ℝ | ¬(deriv γ p.1 * (deriv (circleMap a ε) p.2 •
                (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1))) =
              derivWithin γ (Set.Icc 0 1) p.1 * (deriv (circleMap a ε) p.2 •
                (Q (circleMap a ε p.2) / (circleMap a ε p.2 - γ p.1))))}
          ⊆ (Set.univ \ Set.Ioo (0:ℝ) 1) ×ˢ Set.univ by
        intro ⟨t, θ⟩ ht
        simp only [Set.mem_setOf_eq] at ht
        simp only [Set.mem_prod, Set.mem_diff, Set.mem_univ, true_and, and_true,
                   Set.mem_Ioo, not_and_or, not_lt]
        by_contra h
        rw [not_or] at h
        obtain ⟨h1, h2⟩ := h
        rw [not_le] at h1 h2
        exact ht (by congr 1; exact (derivWithin_of_mem_nhds (Icc_mem_nhds h1 h2)).symm))
  simp only [MeasureTheory.Measure.prod_prod]
  rw [h0, zero_mul]

end Problems.residue_thm
