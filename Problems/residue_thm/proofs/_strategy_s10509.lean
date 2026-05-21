import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_segment_avoids_pole
import Problems.residue_thm.proofs.L_segment_const_deriv
import Problems.residue_thm.proofs.L_segment_contdiff

namespace Problems.residue_thm

-- Straight-line segment trick: apply hF to γ(t) = z + t·h.
-- Sub-goals (each strictly simpler than the parent FTC-along-path):
--   segment_contdiff       : γ is C¹ on [0,1] (polynomial)
--   segment_avoids_pole    : γ stays in the open disk around z, so γ t ≠ a
--   segment_const_deriv    : deriv γ = h (constant)
-- Then hF gives F(γ 1) - F(γ 0) = ∫ Q(γ t) · γ' t, and γ 0 = z, γ 1 = z+h.
theorem s10509
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
  have hc : ContDiffOn ℝ 1 (fun t : ℝ => z + (t:ℂ) * h) (Set.Icc 0 1) :=
    segment_contdiff z h
  have ha : ∀ t ∈ Set.Icc (0:ℝ) 1, (fun t : ℝ => z + (t:ℂ) * h) t ≠ a :=
    segment_avoids_pole z hz h hh
  have hd : ∀ t : ℝ, deriv (fun s : ℝ => z + (s:ℂ) * h) t = h := fun t =>
    segment_const_deriv z h t
  have key := hF (fun t : ℝ => z + (t:ℂ) * h) hc ha
  have e0 : (fun t : ℝ => z + (t:ℂ) * h) 0 = z := by push_cast; ring
  have e1 : (fun t : ℝ => z + (t:ℂ) * h) 1 = z + h := by push_cast; ring
  rw [e0, e1] at key
  rw [key]
  apply intervalIntegral.integral_congr
  intro t _
  change Q (z + (t:ℂ) * h) * deriv (fun s : ℝ => z + (s:ℂ) * h) t
      = Q (z + (t:ℂ) * h) * h
  rw [hd t]

end Problems.residue_thm
