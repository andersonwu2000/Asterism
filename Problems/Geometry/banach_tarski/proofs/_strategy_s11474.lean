import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_free_action_word_unique
import Problems.Geometry.banach_tarski.proofs.L_orbit_section_exists

namespace Problems.Geometry.banach_tarski

-- Build the orbit address from a general orbit section + freeness uniqueness.
-- `orbit_section_exists` gives a representative `rep` and word `wrd` with
-- `φ (wrd x) • rep x = x` and `rep` constant on each F₂-orbit (no freeness/M needed —
-- pure Quotient.out on the orbit relation). The cocycle word equation
-- `wrd (φ w • x) = w * wrd x` then follows from freeness uniqueness on M
-- (`free_action_word_unique`): both `φ (wrd (φ w•x)) • rep x` and `φ (w * wrd x) • rep x`
-- equal `φ w • x`, and `rep x ∈ M`, so the stabilizing words coincide. Each sub-goal is
-- strictly simpler: the section drops the cocycle equation and all M-hypotheses; the
-- uniqueness lemma is a single hfree application with no Equidecomp/orbit structure.
theorem s11474
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x) :
    ∃ (rep : E → E) (wrd : E → FreeGroup (Fin 2)),
      (∀ x ∈ M, x = φ (wrd x) • rep x) ∧
      (∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x)  := by
  obtain ⟨rep, wrd, haddr, hrep⟩ := orbit_section_exists φ
  have word_unique := free_action_word_unique φ M hfree
  refine ⟨rep, wrd, fun x _ => (haddr x).symm, fun x hx w => ⟨hrep x w, ?_⟩⟩
  have hr : (φ (wrd x))⁻¹ • x = rep x := by
    rw [inv_smul_eq_iff]; exact (haddr x).symm
  have hrepM : rep x ∈ M := by
    rw [← hr, ← map_inv]
    exact hinv _ _ hx
  have e1 : φ (wrd (φ w • x)) • rep x = φ w • x := by
    rw [← hrep x w]; exact haddr (φ w • x)
  have e2 : φ (w * wrd x) • rep x = φ w • x := by
    rw [map_mul, mul_smul, haddr x]
  exact word_unique (rep x) hrepM _ _ (e1.trans e2.symm)

end Problems.Geometry.banach_tarski
