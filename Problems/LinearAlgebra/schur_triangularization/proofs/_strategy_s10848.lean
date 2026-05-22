import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_seq_choose_step
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_seq_span_iic_from_step

namespace Problems.LinearAlgebra.schur_triangularization

-- Decompose the iterative-flag construction into two pieces:
-- (1) `flag_seq_choose_step` packages the pointwise `∃ vnext` (from `hext`) into a single
--     function `v : Fin d → V` carrying the chain-step equation per index — a Classical.choice
--     repackaging that strips off the existential layer.
-- (2) `flag_seq_span_iic_from_step` runs the induction on `j.val`: with `W 0 = ⊥` as the base
--     and the per-step chain equation, the span of `v '' Set.Iic j` advances by one along `W`.
-- Combining (1) and (2): pick `v` via (1), conclude the span equality via (2), package the ∃.
theorem s10848 :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1)) →
      ∃ v : Fin (Module.finrank K V) → V,
        ∀ j : Fin (Module.finrank K V),
          Submodule.span K (v '' Set.Iic j) = W (j.val + 1)  := by
  intro K _ V _ _ _ W hW0 hWmono hWrank hext
  have h_choose := flag_seq_choose_step W hW0 hWmono hWrank hext
  obtain ⟨v, hv⟩ := h_choose
  have h_span := flag_seq_span_iic_from_step W v hW0 hWmono hWrank hext hv
  exact ⟨v, h_span⟩

end Problems.LinearAlgebra.schur_triangularization
