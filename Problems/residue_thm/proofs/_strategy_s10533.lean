import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_segment_avoids_pole
import Problems.residue_thm.proofs.L_segment_const_deriv
import Problems.residue_thm.proofs.L_segment_contdiff

namespace Problems.residue_thm

-- Straight-line segment trick: apply hF to γ(t) := z + (t:ℂ)·h.
-- Sub-goals: (1) segment_contdiff — Builder: γ is C¹ on Icc 0 1.
-- (2) segment_avoids_pole — Builder: ‖h‖ < dist z a ⇒ γ t ≠ a on Icc.
-- (3) segment_const_deriv — Builder: deriv γ t = h pointwise.
-- Combine: γ 0 = z, γ 1 = z+h via push_cast/ring; integrand rewrite via h_deriv.
theorem s10533
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0)
    (F : ℂ → ℂ)
    (hF : ∀ γ : ℝ → ℂ,
      ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) →
      F (γ 1) - F (γ 0) = ∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) :
    ∀ z ∈ Set.univ \ ({a} : Set ℂ), ∀ h : ℂ, ‖h‖ < dist z a →
      F (z + h) - F z = ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h) * h  := by
  intro z hz h hh
  have h_C1 : ContDiffOn ℝ 1 (fun t : ℝ => z + (t:ℂ) * h) (Set.Icc 0 1) :=
    segment_contdiff z h
  have h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, z + (t:ℂ) * h ≠ a :=
    segment_avoids_pole z hz h hh
  have h_deriv : ∀ t : ℝ, deriv (fun s : ℝ => z + (s:ℂ) * h) t = h :=
    fun t => segment_const_deriv z h t
  have hpath := hF (fun t : ℝ => z + (t:ℂ) * h) h_C1 h_avoid
  have h0 : (fun t : ℝ => z + (t:ℂ) * h) 0 = z := by push_cast; ring
  have h1 : (fun t : ℝ => z + (t:ℂ) * h) 1 = z + h := by push_cast; ring
  rw [h0, h1] at hpath
  rw [hpath]
  refine intervalIntegral.integral_congr (fun t _ => ?_)
  simp [h_deriv]

end Problems.residue_thm
