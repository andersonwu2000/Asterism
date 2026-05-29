import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_empty_word_head_eq_one
import Problems.Geometry.banach_tarski.proofs.L_tower_first_letter_ne_zero

namespace Problems.Geometry.banach_tarski

-- Tower ⊆ source: each tower element ((φ(of 1))⁻¹^n) y with y an empty-word rep
-- equals φ((of 1)⁻¹^n) • y, so it lands in M (hinv) and its representative word is
-- (of 1)⁻¹^n (hcoh + wrd y = 1 from h_empty), whose first letter is never (0,_).
-- Sub-goals: tower_first_letter_ne_zero (free-group combinatorics, head of (of 1)⁻¹^n)
-- and empty_word_head_eq_one (head?=none ⇒ word is 1). Both are parameter-free and
-- strictly simpler than the set-inclusion parent.
theorem s11492
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    (⋃ n : ℕ, ((φ (FreeGroup.of 1))⁻¹ ^ n) ''
        {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none})
      ⊆ {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0}  := by
  intro x hx
  simp only [Set.mem_iUnion, Set.mem_image] at hx
  obtain ⟨n, y, ⟨hyM, hyhead⟩, rfl⟩ := hx
  have h_tower := tower_first_letter_ne_zero
  have h_empty := empty_word_head_eq_one

  have hbridge : ((φ (FreeGroup.of 1))⁻¹ ^ n) y = φ ((FreeGroup.of 1)⁻¹ ^ n) • y := by
    rw [map_pow, map_inv]; rfl
  rw [Set.mem_setOf_eq, hbridge]
  refine ⟨hinv _ _ hyM, ?_⟩
  have hwrd : wrd (φ ((FreeGroup.of 1)⁻¹ ^ n) • y) = (FreeGroup.of 1)⁻¹ ^ n := by
    rw [(hcoh y hyM ((FreeGroup.of 1)⁻¹ ^ n)).2, h_empty (wrd y) hyhead, mul_one]
  rw [hwrd]
  exact h_tower n


end Problems.Geometry.banach_tarski
