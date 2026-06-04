import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- chain_bottoms_li: LinearIndependent.comp on basis d — chain bottoms are an injective
-- subfamily of the Jordan basis, hence LI directly from d.linearIndependent.
-- entry_kind: Builder
theorem chain_bottoms_li
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    LinearIndependent K (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩) := by
  apply d.linearIndependent.comp
      (fun t : {t : Fin p // 0 < l t} => (⟨t.1, ⟨0, t.2⟩⟩ : Σ t : Fin p, Fin (l t)))
  intro a b hab
  simp only [Sigma.mk.inj_iff] at hab
  exact Subtype.ext hab.1

end Problems.LinearAlgebra.jordan_normal_form
