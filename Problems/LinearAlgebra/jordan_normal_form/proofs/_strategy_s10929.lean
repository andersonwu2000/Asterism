import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_align_offset_zero
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_block_gaps_of_starts

namespace Problems.LinearAlgebra.jordan_normal_form

-- Build block sizes `l` from the start-predicate `S` (`block_gaps_of_starts`):
-- gaps between consecutive starts, positive, summing to `n`, with starts
-- characterised as the prefix-sum positions. Lay them out with the lexicographic
-- block enumeration `finSigmaFinEquiv.symm` (offsets = prefix sums), transported
-- along `∑ l = n`. The offset formula is the enumeration identity; the alignment
-- `S q ↔ (e q).2 = 0` is `align_offset_zero` applied to that offset data.
theorem s10929 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q) :
    ∃ (p : ℕ) (l : Fin p → ℕ) (e : Fin n ≃ Σ t : Fin p, Fin (l t)) (o : Fin p → ℕ),
      (∀ q : Fin n, (q : ℕ) = o (e q).1 + ((e q).2 : ℕ)) ∧
      (∀ q : Fin n, (S q ↔ ((e q).2 : ℕ) = 0))  := by
  obtain ⟨p, l, hpos, hsum, hstart⟩ := block_gaps_of_starts S h0
  refine ⟨p, l, (finCongr hsum).symm.trans finSigmaFinEquiv.symm,
      (fun t => ∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)), ?_, ?_⟩

  · intro q
    simp only [Equiv.trans_apply]
    have h := finSigmaFinEquiv_apply (finSigmaFinEquiv.symm ((finCongr hsum).symm q))
    simp only [Equiv.apply_symm_apply] at h
    have hv : ((finCongr hsum).symm q : ℕ) = (q : ℕ) := by simp
    rw [hv] at h
    exact h
  · refine align_offset_zero S l hpos _ _ ?_ hstart
    intro q
    simp only [Equiv.trans_apply]
    have h := finSigmaFinEquiv_apply (finSigmaFinEquiv.symm ((finCongr hsum).symm q))
    simp only [Equiv.apply_symm_apply] at h
    have hv : ((finCongr hsum).symm q : ℕ) = (q : ℕ) := by simp
    rw [hv] at h
    exact h

end Problems.LinearAlgebra.jordan_normal_form
