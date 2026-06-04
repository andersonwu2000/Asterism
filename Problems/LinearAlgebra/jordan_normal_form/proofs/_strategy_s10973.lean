import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10973
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩)
    (t : Fin p) (j i : Fin (l t)) (hij : (i : ℕ) + 1 = (j : ℕ))
    (hMij : M (d ⟨t, j⟩) = d ⟨t, i⟩) :
    ∀ idx : (Σ t : Fin p, Fin (l t)), d.repr (M (d idx)) ⟨t, i⟩ = d.repr (d idx) ⟨t, j⟩ := by
  rintro ⟨t', j'⟩
  rw [Module.Basis.repr_self_apply]
  rcases Nat.eq_zero_or_pos (j' : ℕ) with h0 | hpos
  · have hne : ¬ ((⟨t', j'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t, j⟩) := by
      intro heq
      have h2 : (j' : ℕ) = (j : ℕ) := congrArg (fun x => (x.2 : ℕ)) heq
      omega
    simp [hbot t' j' h0, hne]
  · obtain ⟨i', hi', hMi'⟩ := hshift t' j' hpos
    rw [hMi', Module.Basis.repr_self_apply]
    rcases eq_or_ne t' t with ht | ht
    · subst ht
      have hcond : ((⟨t', i'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t', i⟩) ↔
          ((⟨t', j'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t', j⟩) := by
        simp only [Sigma.mk.injEq, heq_eq_eq, Fin.ext_iff]
        constructor <;> rintro ⟨h1, h2⟩ <;> exact ⟨h1, by omega⟩
      simp only [hcond]
    · have hne1 : ¬ ((⟨t', i'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t, i⟩) :=
        fun heq => ht (congrArg Sigma.fst heq)
      have hne2 : ¬ ((⟨t', j'⟩ : Σ t : Fin p, Fin (l t)) = ⟨t, j⟩) :=
        fun heq => ht (congrArg Sigma.fst heq)
      rw [if_neg hne1, if_neg hne2]

end Problems.LinearAlgebra.jordan_normal_form
