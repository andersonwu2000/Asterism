import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_absorb_empty_word
import Problems.Geometry.banach_tarski.proofs.L_b_letter_equidecomp
import Problems.Geometry.banach_tarski.proofs.L_equidecomp_trans_glue

namespace Problems.Geometry.banach_tarski

-- Two-piece partition of M by "first letter is generator 0?": this is the
-- NON-letter-0 piece = {empty word} ∪ Wᵦ ∪ Wᵦ⁻¹.  Unlike the letter-0 piece,
-- its source carries one extra orbit-point per orbit (the representative, whose
-- word is empty / head? = none), so the naive id/φ(of 1) split cannot biject it
-- onto M (Wᵦ ⊔ φ(of 1)•Wᵦ⁻¹ already = M).  Factor as a Hilbert-hotel absorption
-- `absorb_empty_word` (full source ≅ the plain b-block Sᵦ, swallowing the reps
-- along the φ(of 1)⁻¹ tower) composed with the clean single-generator block
-- `b_letter_equidecomp` (Sᵦ ≅ M, the exact analogue of the letter-0 builder for
-- generator 1).  `equidecomp_trans_glue` packages `Equidecomp.trans` when the
-- middle target/source agree.
theorem s11473
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ g : Equidecomp E (E ≃ᵢ E),
      g.source = {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      g.target = M  := by
  obtain ⟨e₂, he₂s, he₂t⟩ := b_letter_equidecomp φ hφ M hinv hfree rep wrd hx hcoh
  obtain ⟨e₁, he₁s, he₁t⟩ := absorb_empty_word φ hφ M hinv hfree rep wrd hx hcoh
  obtain ⟨e, hes, het⟩ := equidecomp_trans_glue e₁ e₂ (by rw [he₁t, he₂s])
  exact ⟨e, by rw [hes, he₁s], by rw [het, he₂t]⟩


end Problems.Geometry.banach_tarski
