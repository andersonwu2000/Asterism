import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct proof: `S q ↔ within-block offset 0`, no prefix-sum uniqueness needed.
-- Rewrite `hstart` to `∃ t, ∑_{j<t} l j = ↑q`. (⇐) if offset = 0 then `hcond1` gives
-- `o (e q).1 = ↑q`, witness `t := (e q).1` after `← ho`. (⇒) given a start `t`, the
-- element `e.symm ⟨t, 0⟩` has the same `Fin.val` as `q` (both equal `o t` via `hcond1`/
-- `ho`), so `e q = ⟨t, 0⟩` by injectivity of `Fin.val`, forcing the offset to `0`.
theorem s10988 {p : ℕ} (l : Fin p → ℕ)
    (hpos : ∀ t : Fin p, 0 < l t)
    (S : Fin (∑ t, l t) → Prop)
    (hstart : ∀ q : Fin (∑ t, l t), (S q ↔ ∃ t : Fin p,
        (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (q : ℕ)))
    (e : Fin (∑ t, l t) ≃ Σ t : Fin p, Fin (l t)) (o : Fin p → ℕ)
    (ho : ∀ t : Fin p, o t = ∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j))
    (hcond1 : ∀ q : Fin (∑ t, l t), (q : ℕ) = o (e q).1 + ((e q).2 : ℕ)) :
    ∀ q : Fin (∑ t, l t), (S q ↔ ((e q).2 : ℕ) = 0)  := by
  intro q
  rw [hstart q]
  constructor
  · rintro ⟨t, ht⟩
    have key : e.symm ⟨t, ⟨0, hpos t⟩⟩ = q := by
      apply Fin.ext
      have h1 := hcond1 (e.symm ⟨t, ⟨0, hpos t⟩⟩)
      rw [Equiv.apply_symm_apply] at h1
      simp at h1
      rw [← ho t] at ht
      omega
    have heq : e q = ⟨t, ⟨0, hpos t⟩⟩ := by
      rw [← key]; exact Equiv.apply_symm_apply e _
    exact heq ▸ rfl
  · intro h
    refine ⟨(e q).1, ?_⟩
    rw [← ho]
    have h2 := hcond1 q
    omega

end Problems.LinearAlgebra.jordan_normal_form
