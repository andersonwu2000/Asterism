import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- align_offset_zero: S q ↔ intra-block offset is zero, using offset formula and hstart
theorem align_offset_zero {n p : ℕ} (S : Fin n → Prop) (l : Fin p → ℕ)
    (hpos : ∀ t : Fin p, 0 < l t)
    (e : Fin n ≃ Σ t : Fin p, Fin (l t)) (o : Fin p → ℕ)
    (ho : ∀ q : Fin n, (q : ℕ) = o (e q).1 + ((e q).2 : ℕ))
    (hstart : ∀ q : Fin n, (S q ↔ ∃ t : Fin p, o t = (q : ℕ))) :
    ∀ q : Fin n, (S q ↔ ((e q).2 : ℕ) = 0) := by
  intro q
  rw [hstart]
  constructor
  · rintro ⟨t, ht⟩
    have key : e.symm ⟨t, ⟨0, hpos t⟩⟩ = q := by
      apply Fin.ext
      have h1 := ho (e.symm ⟨t, ⟨0, hpos t⟩⟩)
      rw [Equiv.apply_symm_apply] at h1
      simp at h1
      omega
    have heq : e q = ⟨t, ⟨0, hpos t⟩⟩ := by
      rw [← key]; exact Equiv.apply_symm_apply e _
    exact heq ▸ rfl
  · intro h
    exact ⟨(e q).1, by have := ho q; omega⟩

end Problems.LinearAlgebra.jordan_normal_form
