import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- start_offset_zero_fin_sigma: block-start iff offset=0 via finSigmaFinEquiv.symm uniqueness
theorem start_offset_zero_fin_sigma {p : ℕ} (l : Fin p → ℕ)
    (hpos : ∀ t : Fin p, 0 < l t)
    (S : Fin (∑ t, l t) → Prop)
    (hstart : ∀ q : Fin (∑ t, l t), (S q ↔ ∃ t : Fin p,
        (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (q : ℕ))) :
    ∀ q : Fin (∑ t, l t),
      (S q ↔ ((finSigmaFinEquiv.symm q).2 : ℕ) = 0) := by
  intro q
  rw [hstart]
  set σ := finSigmaFinEquiv.symm q with hσ_def
  have hq_val : (q : ℕ) = ∑ i : Fin σ.1, l (Fin.castLE σ.1.2.le i) + σ.2 := by
    have happ := @finSigmaFinEquiv_apply p l σ
    have heq : finSigmaFinEquiv σ = q := finSigmaFinEquiv.apply_symm_apply q
    exact_mod_cast heq ▸ happ
  constructor
  · rintro ⟨t, ht⟩
    have hfwd : finSigmaFinEquiv ⟨t, ⟨0, hpos t⟩⟩ = q := by
      ext
      rw [finSigmaFinEquiv_apply]
      simp only [add_zero]
      exact_mod_cast ht
    have hσ_eq : (⟨t, ⟨0, hpos t⟩⟩ : Σ i : Fin p, Fin (l i)) = σ :=
      finSigmaFinEquiv.injective
        (hfwd.trans (finSigmaFinEquiv.apply_symm_apply q).symm)
    rw [← hσ_eq]
  · intro h
    exact ⟨σ.1, by omega⟩

end Problems.LinearAlgebra.jordan_normal_form
