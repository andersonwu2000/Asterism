import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Flatten the nested direct sum into a product-indexed one (direct proof, no sub-goals).
-- `sigmaLcurryEquiv.symm` curries `⨁ a ⨁ b N a b` back to the sigma-indexed `⨁ (Σ a, β) N`,
-- then `lequivCongrLeft (Equiv.sigmaEquivProd α β)` reindexes `Σ a:α, β` onto `α × β`;
-- the reindexed family `N (h.symm k).1 (h.symm k).2` is defeq to `N k.1 k.2`.
theorem s11582 {R : Type*} [CommRing R]
    {α β : Type*} [DecidableEq α] [DecidableEq β]
    (N : α → β → Type*) [∀ a b, AddCommGroup (N a b)] [∀ a b, Module R (N a b)] :
    Nonempty (DirectSum α (fun a => DirectSum β (fun b => N a b)) ≃ₗ[R]
      DirectSum (α × β) (fun ab => N ab.1 ab.2))  := by
  exact ⟨(DirectSum.sigmaLcurryEquiv R (δ := fun a (b : β) => N a b)).symm.trans
    (DirectSum.lequivCongrLeft R (Equiv.sigmaEquivProd α β))⟩



end Problems.LinearAlgebra.invariant_factor_decomposition
