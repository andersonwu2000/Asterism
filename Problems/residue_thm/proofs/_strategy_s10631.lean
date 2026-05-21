import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_analytic_seg_primdiff_wrap
import Problems.residue_thm.proofs.L_chord_int_primdiff_lerp_form

namespace Problems.residue_thm

-- Use the row-0 ball-cover primitive at column j: g analytic on `Metric.ball (c 0 j) (r 0 j) ⊆ U`
-- gives a holomorphic primitive `F` on the ball. The γ-segment integral on `[j/N, (j+1)/N]`
-- equals `F (γ((j+1)/N)) - F (γ(j/N))` by FTC along the C¹ subpath (γ maps the subinterval into
-- the ball via `hH0` + `hgrid 0 j` at `τ=0`). The chord integral equals the same primitive
-- difference because the ball is convex (the lerp segment lies inside the ball). Both integrals
-- therefore coincide.
theorem s10631
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hH0 : ∀ t ∈ Set.Icc (0:ℝ) 1, H 0 t = γ t)
    (hHmaps : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U)
    (N : ℕ) (hNpos : 0 < N) (c : ℕ → ℕ → ℂ) (r : ℕ → ℕ → ℝ)
    (hgrid : ∀ i j, i < N → j < N →
      0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
        (∀ τ ∈ Set.Icc ((i:ℝ)/N) (((i:ℝ)+1)/N),
          ∀ t ∈ Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N),
            H τ t ∈ Metric.ball (c i j) (r i j)))
    (j : ℕ) (hj : j ∈ Finset.range N) :
    (∫ t in ((j:ℝ)/N)..(((j:ℝ)+1)/N), g (γ t) * deriv γ t) =
      (∫ s in (0:ℝ)..1,
        g ((1 - (s:ℂ)) * γ ((j : ℝ) / N) + (s:ℂ) * γ (((j : ℝ) + 1) / N))
          * (γ (((j : ℝ) + 1) / N) - γ ((j : ℝ) / N)))  := by
  have hj_lt : j < N := Finset.mem_range.mp hj
  have hjN : (0 : ℝ) < N := Nat.cast_pos.mpr hNpos
  have hjle : ((j:ℝ)/N) ≤ (((j:ℝ)+1)/N) := by
    have h := one_div_nonneg.mpr (le_of_lt hjN)
    have heq : ((j:ℝ)+1)/N - (j:ℝ)/N = 1/N := by
      field_simp; ring
    linarith
  have hsub_Icc : Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N) ⊆ Set.Icc (0:ℝ) 1 := by
    intro t ht
    refine ⟨?_, ?_⟩
    · have h0 : (0:ℝ) ≤ (j:ℝ)/N := by positivity
      linarith [ht.1]
    · have h2 : ((j:ℝ)+1)/N ≤ 1 := by
        rw [div_le_one hjN]; exact_mod_cast hj_lt
      linarith [ht.2]
  obtain ⟨hrpos, hrsub, hrτt⟩ := hgrid 0 j hNpos hj_lt
  have hf_diff : DifferentiableOn ℂ g (Metric.ball (c 0 j) (r 0 j)) :=
    (hg.mono hrsub).differentiableOn
  have hγ_seg : ContDiffOn ℝ 1 γ (Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N)) :=
    hγ.mono hsub_Icc
  have h0_in : (0:ℝ) ∈ Set.Icc (((0:ℕ):ℝ)/N) ((((0:ℕ):ℝ)+1)/N) := by
    refine ⟨by simp, ?_⟩
    have : (1:ℝ)/N ≥ 0 := by positivity
    simpa using this
  have hγU_seg : Set.MapsTo γ (Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N)) (Metric.ball (c 0 j) (r 0 j)) := by
    intro t ht
    have ht01 : t ∈ Set.Icc (0:ℝ) 1 := hsub_Icc ht
    have hHt := hrτt 0 h0_in t ht
    rw [hH0 t ht01] at hHt
    exact hHt
  obtain ⟨F, hF, hgamma_eq⟩ :=
    analytic_seg_primdiff_wrap hjle hf_diff hγ_seg hγU_seg
  have hzmem : γ ((j:ℝ)/N) ∈ Metric.ball (c 0 j) (r 0 j) :=
    hγU_seg ⟨le_refl _, hjle⟩
  have hwmem : γ (((j:ℝ)+1)/N) ∈ Metric.ball (c 0 j) (r 0 j) :=
    hγU_seg ⟨hjle, le_refl _⟩
  have hchord := chord_int_primdiff_lerp_form hF hzmem hwmem
  rw [hgamma_eq, ← hchord]
end Problems.residue_thm
