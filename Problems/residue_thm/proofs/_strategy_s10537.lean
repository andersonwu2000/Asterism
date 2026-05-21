import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c1_path_in_punctured_plane_from_one

namespace Problems.residue_thm

-- Reduce to path-connectedness of ℂ\{0} from basepoint 1 by translation z ↦ z - a.
-- Given C¹ path γ from 1 to (z-a) avoiding 0, define φ t = a + γ t to get
-- a C¹ path from a+1 to z avoiding a.
theorem s10537
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0) :
    ∀ z : ℂ, z ≠ a →
      ∃ φ : ℝ → ℂ, ContDiffOn ℝ 1 φ (Set.Icc 0 1) ∧
        φ 0 = a + 1 ∧ φ 1 = z ∧
        (∀ t ∈ Set.Icc (0:ℝ) 1, φ t ≠ a)  := by
  intro z hz
  have h_core := c1_path_in_punctured_plane_from_one
  obtain ⟨γ, hC1, h0, h1, havoid⟩ := h_core (z - a) (sub_ne_zero.mpr hz)
  refine ⟨fun t => a + γ t, ?_, ?_, ?_, ?_⟩
  · exact contDiffOn_const.add hC1
  · change a + γ 0 = a + 1
    rw [h0]
  · change a + γ 1 = z
    rw [h1]; ring
  · intro t ht hcontra
    have hcontra' : a + γ t = a := hcontra
    have hgt : γ t = 0 := by linear_combination hcontra'
    exact havoid t ht hgt

end Problems.residue_thm

