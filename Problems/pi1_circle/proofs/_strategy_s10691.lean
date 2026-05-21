import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_winding_quot_bijective
import Problems.pi1_circle.proofs.L_winding_quot_function_char
import Problems.pi1_circle.proofs.L_winding_quot_refl_zero
import Problems.pi1_circle.proofs.L_winding_quot_trans_add

namespace Problems.pi1_circle

open Real

-- Decompose via the lifted endpoint Γ γ 1 ∈ 2π·ℤ: (1) build W' on the
-- homotopy quotient with characterizing equation Γ γ 1 = W'⟦γ⟧ * (2π);
-- (2-4) the three properties refl=0 / trans=add / bijective each follow
-- from that characterizing equation (W'⟦refl⟧=0 via `liftPath_const`,
-- additivity via `liftPath_trans` + translation invariance of lifts,
-- bijectivity via `monodromy_bijective` + standard loops `t ↦ exp(t·n·2π)`).
theorem s10691 :
    ∃ (W' : Path.Homotopic.Quotient (1 : Circle) 1 → ℤ),
      W' (⟦Path.refl (1 : Circle)⟧ : Path.Homotopic.Quotient (1 : Circle) 1) = 0 ∧
      (∀ (γ γ' : Path (1 : Circle) 1),
          W' (⟦γ.trans γ'⟧ : Path.Homotopic.Quotient (1 : Circle) 1)
            = W' (⟦γ⟧ : Path.Homotopic.Quotient (1 : Circle) 1)
              + W' (⟦γ'⟧ : Path.Homotopic.Quotient (1 : Circle) 1)) ∧
      Function.Bijective W'  := by
  obtain ⟨W', h_char⟩ := winding_quot_function_char
  refine ⟨W', ?_, ?_, ?_⟩
  · exact winding_quot_refl_zero W' h_char
  · exact winding_quot_trans_add W' h_char
  · exact winding_quot_bijective W' h_char

end Problems.pi1_circle
