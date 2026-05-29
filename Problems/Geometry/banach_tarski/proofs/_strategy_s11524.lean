import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_absorb_empty_word_origin_fixing
import Problems.Geometry.banach_tarski.proofs.L_b_letter_equidecomp_origin_fixing
import Problems.Geometry.banach_tarski.proofs.L_equidecomp_trans_glue_origin_fixing

namespace Problems.Geometry.banach_tarski

-- Origin-fixing mirror of build_non_letter0_equidecomp (s11473): the non-letter-0 piece is
-- the trans-composition absorb_empty_word ∘ b_letter_equidecomp.  Each factor is refined to
-- ALSO expose its origin-fixing realizing Finset (absorb: {φ(of 1)⁻¹,1}; b-letter: {1,φ(of 1)},
-- all fixing 0 via hfix0), and a generic origin-fixing trans-glue composes them: the composite
-- Finset = S₂ * S₁ (products of the per-step shifts), each a product of origin-fixers ⇒ fixes 0.
-- Sub-goals: (1) absorb_empty_word_origin_fixing, (2) b_letter_equidecomp_origin_fixing,
-- (3) equidecomp_trans_glue_origin_fixing (abstract).  Combinator: obtain the two factors,
-- glue, thread source/target/IsDecompOn/origin-fixing straight through.
theorem s11524
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (g : Equidecomp E (E ≃ᵢ E)) (Sg : Finset (E ≃ᵢ E)),
      g.source = {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      g.target = M ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨e₂, Sb, he₂s, he₂t, hd₂, h0₂⟩ :=
    b_letter_equidecomp_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  obtain ⟨e₁, Sa, he₁s, he₁t, hd₁, h0₁⟩ :=
    absorb_empty_word_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  obtain ⟨e, S, hes, het, hd, h0⟩ :=
    equidecomp_trans_glue_origin_fixing e₁ e₂ (by rw [he₁t, he₂s]) Sa Sb hd₁ hd₂ h0₁ h0₂
  exact ⟨e, S, by rw [hes, he₁s], by rw [het, he₂t], by rw [hes, he₁s] at hd ⊢; exact hd, h0⟩


end Problems.Geometry.banach_tarski
