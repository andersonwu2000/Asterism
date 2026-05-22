import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_span_iic_succ
import Problems.LinearAlgebra.schur_triangularization.proofs.L_flag_span_iic_zero

namespace Problems.LinearAlgebra.schur_triangularization

-- Induct on j.val to lift the per-index chain equation `W j.val ⊔ span {v j} = W (j.val+1)`
-- into the running span equality.  Two simpler sub-goals:
--   * `flag_span_iic_zero` — base case j.val = 0: with `W 0 = ⊥` and the chain step at index 0,
--     `span (v '' Set.Iic 0) = span {v 0} = W 1`.
--   * `flag_span_iic_succ` — step case: given `span (v '' Set.Iic ⟨n,_⟩) = W (n+1)`, the chain
--     step at index n+1 promotes it to `span (v '' Set.Iic ⟨n+1,_⟩) = W (n+2)`.
-- Combinator: `Nat.rec` on the underlying ℕ of `j.val`, then apply at `j.val, j.isLt`.
theorem s10849 :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V)
      (v : Fin (Module.finrank K V) → V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      (∀ n, n < Module.finrank K V →
        ∃ vnext, vnext ∈ W (n + 1) ∧
          W n ⊔ Submodule.span K {vnext} = W (n + 1)) →
      (∀ j : Fin (Module.finrank K V),
        W j.val ⊔ Submodule.span K {v j} = W (j.val + 1)) →
      ∀ j : Fin (Module.finrank K V),
        Submodule.span K (v '' Set.Iic j) = W (j.val + 1)  := by
  intro K _ V _ _ _ W v hW0 hWmono hWrank hext hstep j
  have h_base := flag_span_iic_zero W v hW0 hWmono hWrank hext hstep
  have h_succ := flag_span_iic_succ W v hW0 hWmono hWrank hext hstep
  have hgen : ∀ (n : ℕ) (hn : n < Module.finrank K V),
      Submodule.span K (v '' Set.Iic (⟨n, hn⟩ : Fin (Module.finrank K V)))
        = W (n + 1) := by
    intro n
    induction n with
    | zero => intro h; exact h_base h
    | succ k ih => intro hkn; exact h_succ k hkn (ih (Nat.lt_of_succ_lt hkn))
  simpa using hgen j.val j.isLt

end Problems.LinearAlgebra.schur_triangularization
