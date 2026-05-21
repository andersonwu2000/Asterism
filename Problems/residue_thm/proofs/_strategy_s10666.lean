import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_reparam_with_flat_phi_gives_witness
import Problems.residue_thm.proofs.L_smoothstep_phi_exists

namespace Problems.residue_thm

-- Strategy: choose γ' = γ ∘ φ where φ : ℝ → ℝ is a smoothstep on Icc 0 1
-- (C¹, φ 0 = 0, φ 1 = 1, derivWithin φ vanishes at both endpoints, maps
-- Icc 0 1 into itself). Sub-goal 1 builds such a φ (polynomial like
-- 3 t^2 - 2 t^3). Sub-goal 2 packages the seven conjuncts about γ ∘ φ
-- from the chain rule + change-of-variables. Both are strictly simpler
-- than the parent: (1) is a pure existence about a fixed polynomial,
-- (2) is the same conjunction but with φ in scope as an explicit hypothesis.
theorem s10666
    {Q : ℂ → ℂ} {a : ℂ} {γ : ℝ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∃ γ' : ℝ → ℂ,
      ContDiffOn ℝ 1 γ' (Set.Icc 0 1) ∧
      γ' 0 = γ 0 ∧
      γ' 1 = γ 1 ∧
      derivWithin γ' (Set.Icc 0 1) 0 = 0 ∧
      derivWithin γ' (Set.Icc 0 1) 1 = 0 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, γ' t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (γ' t) * deriv γ' t) =
        (∫ t in (0 : ℝ)..1, Q (γ t) * deriv γ t)  := by
  have h_smoothstep := smoothstep_phi_exists
  obtain ⟨φ, hφC1, hφ0, hφ1, hdφ0, hdφ1, hφmaps⟩ := h_smoothstep
  have h_compose :=
    reparam_with_flat_phi_gives_witness (Q := Q) (a := a)
      hγ havoid hφC1 hφ0 hφ1 hdφ0 hdφ1 hφmaps
  exact ⟨γ ∘ φ, h_compose⟩

end Problems.residue_thm
