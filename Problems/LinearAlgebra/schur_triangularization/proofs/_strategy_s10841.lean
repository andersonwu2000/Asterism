import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_dim_step_existence
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_seq_build_from_step

namespace Problems.LinearAlgebra.schur_triangularization

-- Decompose into (1) the dimensional step-existence lemma — given any submodule U ≤ W(j+1)
-- of dimension j, there is a vector in W(j+1) outside U — and (2) a recursive construction
-- that consumes that step-existence to build the full Fin n → V sequence and proves the
-- initial-span equality by induction on j. (1) is purely a finrank inequality; (2) carries
-- the dependent recursion + induction-on-j proof obligation.
theorem s10841 :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      ∃ v : Fin (Module.finrank K V) → V,
        ∀ j : Fin (Module.finrank K V),
          Submodule.span K (v '' Set.Iic j) = W (j.val + 1)  := by
  intro K _ V _ _ _ W hW0 hWmono hWdim
  have h_step := flag_dim_step_existence W hW0 hWmono hWdim
  exact flag_seq_build_from_step W hW0 hWmono hWdim h_step

end Problems.LinearAlgebra.schur_triangularization
