import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_fin_sigma_offset_decomp
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_start_offset_zero_fin_sigma

namespace Problems.LinearAlgebra.jordan_normal_form

-- Recast `Fin n ≅ Fin (∑ l)` via `subst hsum`, then take `e := finSigmaFinEquiv.symm`
-- (position ↦ block × within-block offset) with `o t := ∑_{j<t} l j` (prefix sums of
-- block lengths). Split into two strictly simpler claims:
--   `fin_sigma_offset_decomp` — pure `finSigmaFinEquiv_apply` rewrite (no S, no hstart).
--   `start_offset_zero_fin_sigma` — start-iff-offset-zero at the concrete equiv (re-uses the
--     prefix-sum uniqueness lemma proved at sibling level).
theorem s11059 {n p : ℕ} (S : Fin n → Prop) (l : Fin p → ℕ)
    (hpos : ∀ t : Fin p, 0 < l t) (hsum : ∑ t, l t = n)
    (hstart : ∀ q : Fin n, (S q ↔ ∃ t : Fin p,
        (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (q : ℕ))) :
    ∃ (e : Fin n ≃ Σ t : Fin p, Fin (l t)) (o : Fin p → ℕ),
      (∀ q : Fin n, (q : ℕ) = o (e q).1 + ((e q).2 : ℕ)) ∧
      (∀ q : Fin n, (S q ↔ ((e q).2 : ℕ) = 0))   := by
  subst hsum
  have h_offset_decomp : ∀ q : Fin (∑ t, l t), (q : ℕ) =
      (∑ j : Fin ↑(finSigmaFinEquiv.symm q).1,
        l (Fin.castLE (finSigmaFinEquiv.symm q).1.isLt.le j))
      + ((finSigmaFinEquiv.symm q).2 : ℕ) := fin_sigma_offset_decomp l
  have h_start_iff : ∀ q : Fin (∑ t, l t),
      (S q ↔ ((finSigmaFinEquiv.symm q).2 : ℕ) = 0) :=
    start_offset_zero_fin_sigma l hpos S hstart
  exact ⟨finSigmaFinEquiv.symm,
    fun t => ∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j),
    h_offset_decomp, h_start_iff⟩

end Problems.LinearAlgebra.jordan_normal_form
