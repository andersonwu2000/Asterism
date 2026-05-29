import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_orbit_address_of_free_action
import Problems.Geometry.banach_tarski.proofs.L_build_letter0_equidecomp_origin_fixing
import Problems.Geometry.banach_tarski.proofs.L_build_non_letter0_equidecomp_origin_fixing

namespace Problems.Geometry.banach_tarski

-- Origin-fixing mirror of s11464: lift the F₂ 2-paradoxical split through φ, now ALSO

-- exposing the realizing Finsets Sf,Sg with every element fixing 0.  Orbit address
-- (rep,wrd) is cited inline from the proved orbit_address_of_free_action; the partition
-- of M by "first letter = generator 0?" pulls back to f.source/g.source.  Two new
-- origin-fixing builders reconstruct each piece together with its origin-fixing Finset
-- (letter-0 piece: Sf={1,φ(of 0)}; complement: Hilbert-hotel φ(of 1)-tower).
-- Combinator: disjointness + cover are the same {x∈M|P} ⊔ {x∈M|¬P} = M set algebra as
-- s11464; the IsDecompOn + origin-fixing fields thread straight through from the builders.
theorem s11515
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0) :
    ∃ (f g : Equidecomp E (E ≃ᵢ E)) (Sf Sg : Finset (E ≃ᵢ E)),
      Disjoint f.source g.source ∧
      f.source ∪ g.source = M ∧
      f.target = M ∧
      g.target = M ∧
      Equidecomp.IsDecompOn f.toFun f.source Sf ∧
      Equidecomp.IsDecompOn g.toFun g.source Sg ∧
      (∀ s ∈ Sf, s 0 = 0) ∧ (∀ s ∈ Sg, s 0 = 0)  := by
  obtain ⟨rep, wrd, hx, hcoh⟩ := orbit_address_of_free_action φ M hinv hfree
  obtain ⟨f, Sf, hfs, hft, hfdec, hf0⟩ :=
    build_letter0_equidecomp_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  obtain ⟨g, Sg, hgs, hgt, hgdec, hg0⟩ :=
    build_non_letter0_equidecomp_origin_fixing φ hφ M hinv hfree hfix0 rep wrd hx hcoh
  refine ⟨f, g, Sf, Sg, ?_, ?_, hft, hgt, hfdec, hgdec, hf0, hg0⟩
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
