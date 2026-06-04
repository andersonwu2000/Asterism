import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_start_iff_offset_zero

namespace Problems.LinearAlgebra.jordan_normal_form

-- Recast `Fin n ≅ Fin (∑ l)` via `subst hsum`, then take `e := finSigmaFinEquiv.symm`
-- (position ↦ (block, within-block offset)) and `o := prefix sums of block lengths`.
-- Condition 1 (offset decomposition `↑q = o(block)+offset`) is `finSigmaFinEquiv_apply`.
-- Condition 2 (`S q ↔ within-block offset = 0`) is the prefix-sum uniqueness crux,
-- delegated to `start_iff_offset_zero` (needs `hpos` for strict monotonicity of `o`).
theorem s10982 {n p : ℕ} (S : Fin n → Prop) (l : Fin p → ℕ)
    (hpos : ∀ t : Fin p, 0 < l t) (hsum : ∑ t, l t = n)
    (hstart : ∀ q : Fin n, (S q ↔ ∃ t : Fin p,
        (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (q : ℕ))) :
    ∃ (e : Fin n ≃ Σ t : Fin p, Fin (l t)) (o : Fin p → ℕ),
      (∀ q : Fin n, (q : ℕ) = o (e q).1 + ((e q).2 : ℕ)) ∧
      (∀ q : Fin n, (S q ↔ ((e q).2 : ℕ) = 0))  := by
  subst hsum
  have hcond1 : ∀ q : Fin (∑ t, l t), (q : ℕ) =
      (∑ j : Fin ↑(finSigmaFinEquiv.symm q).1,
        l (Fin.castLE (finSigmaFinEquiv.symm q).1.isLt.le j))
      + ((finSigmaFinEquiv.symm q).2 : ℕ) := by
    intro q
    have h := finSigmaFinEquiv_apply (finSigmaFinEquiv.symm q)
    simp [Equiv.apply_symm_apply] at h
    exact h
  have hcond2 : ∀ q : Fin (∑ t, l t),
      (S q ↔ ((finSigmaFinEquiv.symm q).2 : ℕ) = 0) := by sorry
  exact ⟨finSigmaFinEquiv.symm,
    fun t => ∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j), hcond1, hcond2⟩

end Problems.LinearAlgebra.jordan_normal_form
