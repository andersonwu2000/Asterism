import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_to_basepoint_avoiding

namespace Problems.residue_thm

-- Skolemize: pick basepoint z₀ = a + 1, and use Classical.choose over the
-- "every z ≠ a has a C¹ path from a+1 avoiding a" existence claim to construct ψ.
-- Sub-goal `path_to_basepoint_avoiding` carries the C¹-path-connectedness of ℂ \ {a}.
theorem s10505
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0) :
    ∃ z₀ : ℂ, ∃ ψ : ℂ → (ℝ → ℂ),
      z₀ ≠ a ∧ ∀ z : ℂ, z ≠ a →
        ContDiffOn ℝ 1 (ψ z) (Set.Icc 0 1) ∧
        ψ z 0 = z₀ ∧ ψ z 1 = z ∧
        (∀ t ∈ Set.Icc (0:ℝ) 1, ψ z t ≠ a) := by
  have h_path := path_to_basepoint_avoiding hQ_an h_loops

  refine ⟨a + 1, fun z => if h : z ≠ a then Classical.choose (h_path z h) else fun _ => a + 1,
    ?_, ?_⟩
  · intro h
    have h1 : (1 : ℂ) = 0 := by linear_combination h
    exact one_ne_zero h1
  · intro z hz
    have hspec := Classical.choose_spec (h_path z hz)
    simp only [dif_pos hz]
    exact hspec


end Problems.residue_thm
