import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- fin_offset_block_enum: block enumeration via finSigmaFinEquiv.symm with prefix-sum offsets
theorem fin_offset_block_enum {m : ℕ} (ν : Fin m → ℕ) :
    ∃ (e : Fin (∑ i, ν i) ≃ Σ i : Fin m, Fin (ν i)) (o : Fin m → ℕ),
      ∀ p : Fin (∑ i, ν i), (p : ℕ) = o (e p).1 + ((e p).2 : ℕ) := by
  refine ⟨finSigmaFinEquiv.symm, fun i => ∑ j : Fin i, ν (Fin.castLE i.isLt.le j), fun p => ?_⟩
  have h := finSigmaFinEquiv_apply (finSigmaFinEquiv.symm p)
  simp [Equiv.apply_symm_apply] at h
  exact h



end Problems.LinearAlgebra.jordan_normal_form
