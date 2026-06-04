import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reduce to the concrete lexicographic enumeration `finSigmaFinEquiv` (offset depends
-- only on the block index). `e` transports `finSigmaFinEquiv.symm` across the cardinality
-- bridge `card = ∑ ν`. The consecutiveness iff for same-block elements is the sub-goal
-- `sigma_enum_consecutive`; `finCongr` is value-preserving so the flat index threads through.
theorem s10916 {m : ℕ} (ν : Fin m → ℕ) :
    ∃ e : Fin (Fintype.card ((i : Fin m) × Fin (ν i))) ≃ ((i : Fin m) × Fin (ν i)),
      ∀ p q : Fin (Fintype.card ((i : Fin m) × Fin (ν i))), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ)))  := by
  have hcard : Fintype.card ((i : Fin m) × Fin (ν i)) = ∑ i, ν i := by
    simp [Fintype.card_sigma]
  have h_sigma_enum_consecutive : ∀ (x y : (i : Fin m) × Fin (ν i)), x.1 = y.1 →
      ((finSigmaFinEquiv x : ℕ) + 1 = (finSigmaFinEquiv y : ℕ) ↔
        ((x.2 : ℕ) + 1 = (y.2 : ℕ))) := by
    rintro ⟨xi, xj⟩ ⟨yi, yj⟩ h
    simp only at h
    subst h
    rw [finSigmaFinEquiv_apply, finSigmaFinEquiv_apply]
    simp only
    omega
  refine ⟨(finCongr hcard).trans finSigmaFinEquiv.symm, ?_⟩
  intro p q hpq
  have hco : ∀ r : Fin (Fintype.card ((i : Fin m) × Fin (ν i))),
      (finSigmaFinEquiv (((finCongr hcard).trans finSigmaFinEquiv.symm) r) : ℕ) = (r : ℕ) := by
    intro r
    simp [Equiv.trans_apply, Equiv.apply_symm_apply, finCongr_apply]
  have key := h_sigma_enum_consecutive
    (((finCongr hcard).trans finSigmaFinEquiv.symm) p)
    (((finCongr hcard).trans finSigmaFinEquiv.symm) q) hpq
  rw [hco p, hco q] at key
  exact key.symm

end Problems.LinearAlgebra.jordan_normal_form
