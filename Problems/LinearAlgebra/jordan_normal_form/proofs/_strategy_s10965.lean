import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_chain_bottoms_li
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_ker_eq_span_chain_bottoms

namespace Problems.LinearAlgebra.jordan_normal_form

-- ker M is spanned by the chain bottoms {d⟨t,0⟩ : 0 < l t}, an LI sub-family of basis d.
-- finrank(span) = card of the bottom index = #{t // 0 < l t} = filter card.
theorem s10965
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    Module.finrank K ↥(LinearMap.ker M)
      = (Finset.univ.filter (fun t : Fin p => 0 < l t)).card  := by
  classical
  have hLI := chain_bottoms_li M d hbot hshift
  have hspan := ker_eq_span_chain_bottoms M d hbot hshift
  rw [hspan, finrank_span_eq_card hLI]
  exact Fintype.card_subtype (fun t : Fin p => 0 < l t)

end Problems.LinearAlgebra.jordan_normal_form
