import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_seq_build_from_extends
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_step_extends_span

namespace Problems.LinearAlgebra.schur_triangularization

-- Decompose into (1) a packaged step lemma — under the parent's step-existence and
-- finrank hypotheses, for each n < finrank K V there is `vnext ∈ W (n+1)` with
-- `W n ⊔ span K {vnext} = W (n+1)` (folds the dimension argument into the step) —
-- and (2) a pure iterative construction — given that packaged step, build the
-- `Fin (finrank K V) → V` sequence and prove the span equality by induction on j.
-- (1) is a one-shot rank/sup argument; (2) carries the dependent recursion.
theorem s10845 :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ (j : ℕ), j < Module.finrank K V →
        ∀ (U : Submodule K V), U ≤ W (j + 1) → Module.finrank K U = j →
        ∃ v, v ∈ W (j + 1) ∧ v ∉ U) →
      ∃ v : Fin (Module.finrank K V) → V,
        ∀ j : Fin (Module.finrank K V),
          Submodule.span K (v '' Set.Iic j) = W (j.val + 1)  := by
  intro K _instK V _instAG _instMod _instFD W hW0 hmono hrank hstep
  have h_extends := flag_step_extends_span W hW0 hmono hrank hstep
  exact flag_seq_build_from_extends W hW0 hmono hrank h_extends



end Problems.LinearAlgebra.schur_triangularization
