import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs

namespace Problems.LinearAlgebra.schur_triangularization

-- basis_from_flag_spans: v with initial spans matching the flag is itself a basis
-- v spans V (last span = W n = ⊤) and is LI (Fintype.card ≤ finrank span = n);
-- Basis.mk packages it, and mk_apply shows b = v pointwise so span conditions transfer.
theorem basis_from_flag_spans :
    ∀ {K : Type*} [Field K]
      {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
      (W : ℕ → Submodule K V),
      W 0 = ⊥ →
      (∀ i, W i ≤ W (i + 1)) →
      (∀ i, Module.finrank K (W i) = min i (Module.finrank K V)) →
      ∀ v : Fin (Module.finrank K V) → V,
        (∀ j : Fin (Module.finrank K V),
            Submodule.span K (v '' Set.Iic j) = W (j.val + 1)) →
        ∃ b : Module.Basis (Fin (Module.finrank K V)) K V,
          ∀ j : Fin (Module.finrank K V),
            Submodule.span K (b '' Set.Iic j) = W (j.val + 1) := by
  intro K _ V _ _ _ W _hW0 _hWmono hWrank v hv
  -- Step 1: W (finrank K V) = ⊤
  have hWn_top : W (Module.finrank K V) = ⊤ := by
    apply Submodule.eq_top_of_finrank_eq
    have h := hWrank (Module.finrank K V)
    simp only [min_self] at h; exact h
  -- Step 2: span K (Set.range v) = ⊤
  have hrange_top : Submodule.span K (Set.range v) = ⊤ := by
    rcases Nat.eq_zero_or_pos (Module.finrank K V) with hn | hn
    · -- finrank = 0: V is trivial, so span ∅ = ⊥ = ⊤
      have hIsEmpty : IsEmpty (Fin (Module.finrank K V)) := by rw [hn]; exact Fin.isEmpty
      rw [Set.range_eq_empty_iff.mpr hIsEmpty, Submodule.span_empty]
      apply Submodule.eq_top_of_finrank_eq
      simp [finrank_bot K V, hn]
    · -- finrank > 0: use the last index j = ⟨n-1, ...⟩
      let j : Fin (Module.finrank K V) := ⟨Module.finrank K V - 1,
        Nat.sub_lt hn Nat.one_pos⟩
      have hjval : j.val + 1 = Module.finrank K V := Nat.succ_pred_eq_of_pos hn
      have hIic_univ : Set.Iic j = Set.univ := by
        ext i
        simp only [Set.mem_Iic, Set.mem_univ, iff_true]
        exact Nat.le_sub_one_of_lt i.isLt
      rw [show Set.range v = v '' Set.Iic j from by rw [hIic_univ, Set.image_univ],
          hv j, hjval]
      exact hWn_top
  -- Step 3: LinearIndependent K v via linearIndependent_iff_card_le_finrank_span
  have hLI : LinearIndependent K v := by
    rw [linearIndependent_iff_card_le_finrank_span]
    simp only [Set.finrank, Fintype.card_fin]
    rw [hrange_top, finrank_top]
  -- Step 4: Package v as a basis; b i = v i by mk_apply, so span conditions transfer
  exact ⟨Module.Basis.mk hLI hrange_top.symm.le, fun j => by
    have hbv : ⇑(Module.Basis.mk hLI hrange_top.symm.le) = v :=
      funext (Module.Basis.mk_apply hLI hrange_top.symm.le)
    rw [hbv]; exact hv j⟩

end Problems.LinearAlgebra.schur_triangularization
