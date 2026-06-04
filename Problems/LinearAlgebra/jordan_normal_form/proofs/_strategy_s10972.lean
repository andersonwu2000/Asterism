import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct: rewrite w = ∑ i, (d.repr w i) • d i (Basis.sum_repr), then Submodule.sum_mem.
-- Per term ⟨t,j⟩: if j = 0 it is a bottom generator (smul_mem + subset_span); if j > 0
-- the coefficient d.repr w ⟨t,j⟩ vanishes by hzero, so the term is 0.
theorem s10972
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩)
    (w : R)
    (hzero : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) → d.repr w ⟨t, j⟩ = 0) :
    w ∈ Submodule.span K
      (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩))  := by
  have key : ∀ i : Σ t : Fin p, Fin (l t),
      d.repr w i • d i ∈ Submodule.span K
        (Set.range (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩)) := by
    rintro ⟨t, j⟩
    rcases Nat.eq_zero_or_pos (j : ℕ) with hj | hj
    · have hlt : 0 < l t := lt_of_le_of_lt (Nat.zero_le _) j.isLt
      apply Submodule.smul_mem
      apply Submodule.subset_span
      refine ⟨⟨t, hlt⟩, ?_⟩
      have hjeq : (⟨0, hlt⟩ : Fin (l t)) = j := Fin.ext hj.symm
      simp only [hjeq]
    · rw [hzero t j hj, zero_smul]
      exact Submodule.zero_mem _
  rw [show w = ∑ i, d.repr w i • d i from (d.sum_repr w).symm]
  exact Submodule.sum_mem _ fun i _ => key i

end Problems.LinearAlgebra.jordan_normal_form
