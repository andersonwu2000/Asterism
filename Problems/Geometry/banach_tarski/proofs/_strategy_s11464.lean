import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_build_letter0_equidecomp
import Problems.Geometry.banach_tarski.proofs.L_build_non_letter0_equidecomp
import Problems.Geometry.banach_tarski.proofs.L_orbit_address_of_free_action

namespace Problems.Geometry.banach_tarski

-- Lift the F₂ 2-paradoxical split through the free, fixed-point-free, M-invariant
-- action φ.  First take an orbit address (rep, wrd): every x∈M is x = φ(wrd x)•rep x
-- with the cocycle rep/wrd transform under the action (orbit_address_of_free_action).
-- The partition of F₂ by "first letter is generator 0?" pulls back to a partition of M:
--   f.source = words starting with letter 0 (a / a⁻¹), reconstructs M by id on a-words
--              and φ(of 0) on a⁻¹-words  (build_letter0_equidecomp);
--   g.source = the complement (empty word + b / b⁻¹ words), reconstructs M by id on
--              {1}∪b-words and φ(of 1) on b⁻¹-words  (build_non_letter0_equidecomp).
-- Combinator: obtain the address, build each piece, then disjointness/cover are the
-- trivial set algebra of {x∈M | P} ⊔ {x∈M | ¬P} = M.  Each sub-goal is strictly simpler:
-- the address drops all Equidecomp structure; each builder handles ONE generator only.
theorem s11464
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = M ∧
      f.target = M ∧
      g.target = M  := by
  obtain ⟨rep, wrd, hx, hcoh⟩ := orbit_address_of_free_action φ M hinv hfree
  obtain ⟨f, hfs, hft⟩ := build_letter0_equidecomp φ hφ M hinv hfree rep wrd hx hcoh
  obtain ⟨g, hgs, hgt⟩ := build_non_letter0_equidecomp φ hφ M hinv hfree rep wrd hx hcoh
  refine ⟨f, g, ?_, ?_, hft, hgt⟩
  · rw [hfs, hgs, Set.disjoint_left]
    rintro x ⟨_, hp⟩ ⟨_, hnp⟩
    exact hnp hp
  · rw [hfs, hgs]
    ext x
    simp only [Set.mem_union, Set.mem_setOf_eq]
    constructor
    · rintro (⟨hxM, _⟩ | ⟨hxM, _⟩) <;> exact hxM
    · intro hxM
      by_cases hp : (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0
      · exact Or.inl ⟨hxM, hp⟩
      · exact Or.inr ⟨hxM, hp⟩

end Problems.Geometry.banach_tarski
