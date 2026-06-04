import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_jordan_chain_ker_finrank

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- Split the combined `hd` disjunction into separate `hbot`/`hshift` premises
-- and apply `jordan_chain_ker_finrank`. The Finset.filter card from that
-- sibling lemma equals `Fintype.card {t // 0 < l t}` via `Fintype.card_subtype`.
theorem restrict_ker_finrank_count
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ M (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    Module.finrank K ↥(LinearMap.ker M) = Fintype.card {t : Fin p // 0 < l t} := by
  classical
  have hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0 := by
    intro t j hj
    rcases hd t j with ⟨_, h0⟩ | ⟨i, hi1, _⟩
    · exact h0
    · exact absurd hi1 (by omega)
  have hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩ := by
    intro t j hj
    rcases hd t j with ⟨h0, _⟩ | h
    · exact absurd h0 (by omega)
    · exact h
  have hcount := jordan_chain_ker_finrank M d hbot hshift
  rw [hcount, ← Fintype.card_subtype]

end Problems.LinearAlgebra.jordan_normal_form
