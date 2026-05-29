import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_letter0_partial_equiv_laws
import Problems.Geometry.banach_tarski.proofs.L_b_letter_pieces_disjoint
import Problems.Geometry.banach_tarski.proofs.L_b_letter_split

namespace Problems.Geometry.banach_tarski

-- Origin-fixing refinement of b_letter_equidecomp (s11480): generator-1 piecewise map
-- (f = id on A=Wᵦ, g0•· on B=Wᵦ⁻¹, g0 = φ(of 1)) reconstructed inline from the proved
-- bricks (b_letter_split, b_letter_pieces_disjoint, letter0_partial_equiv_laws), now ALSO
-- exposing the realizing Finset Sb = {1, g0} and proving every element fixes 0 (1 0 = 0;
-- g0 0 = φ(of 1) 0 = 0 via hfix0).  No new sub-goals — leaf reconstruction.
theorem s11528
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (e : Equidecomp E (E ≃ᵢ E)) (Sb : Finset (E ≃ᵢ E)),
      e.source = {x | x ∈ M ∧
          ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
           (FreeGroup.toWord (wrd x)).head? = some (1, false))} ∧
      e.target = M ∧
      Equidecomp.IsDecompOn e.toFun e.source Sb ∧
      (∀ s ∈ Sb, s 0 = 0)  := by
  classical
  set g0 : E ≃ᵢ E := φ (FreeGroup.of 1) with hg0
  set A : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)} with hA
  set B : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)} with hB
  set Src : Set E :=
    {x | x ∈ M ∧ ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
        (FreeGroup.toWord (wrd x)).head? = some (1, false))} with hSrcdef
  set f : E → E := fun x => if x ∈ A then x else g0 • x with hfdef
  set g : E → E := fun y => if y ∈ A then y else g0⁻¹ • y with hgdef
  have hsplit : (fun x => g0 • x) '' B = M \ A :=
    b_letter_split φ M hinv wrd (fun x hxM w => (hcoh x hxM w).2)
  have hSrc : Src = A ∪ B := by
    ext x
    simp only [hSrcdef, hA, hB, Set.mem_setOf_eq, Set.mem_union]
    tauto
  have hAB : Disjoint A B := b_letter_pieces_disjoint M wrd
  have hAM : A ⊆ M := fun x hx => hx.1
  have hfA : ∀ x ∈ A, f x = x := by intro x hx; simp only [hfdef]; rw [if_pos hx]
  have hfnA : ∀ x, x ∉ A → f x = g0 • x := by intro x hx; simp only [hfdef]; rw [if_neg hx]
  have hgA : ∀ y ∈ A, g y = y := by intro y hy; simp only [hgdef]; rw [if_pos hy]
  have hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y := by intro y hy; simp only [hgdef]; rw [if_neg hy]
  have hlaws : (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y) :=
    letter0_partial_equiv_laws A B M g0 f g hAM hAB hsplit hfA hfnA hgA hgnA
  obtain ⟨hms0, hmt0, hli0, hri0⟩ := hlaws
  have hms : ∀ x ∈ Src, f x ∈ M := by intro x hx; rw [hSrc] at hx; exact hms0 x hx
  have hmt : ∀ y ∈ M, g y ∈ Src := by intro y hy; rw [hSrc]; exact hmt0 y hy
  have hli : ∀ x ∈ Src, g (f x) = x := by intro x hx; rw [hSrc] at hx; exact hli0 x hx
  have hri : ∀ y ∈ M, f (g y) = y := hri0
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  have hdecS : Equidecomp.IsDecompOn f Src {1, g0} := by
    rw [hSrc]
    intro a _
    by_cases hA' : a ∈ A
    · exact ⟨1, Finset.mem_insert_self 1 {g0}, by rw [hfA a hA']; simp⟩
    · exact ⟨g0, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)), hfnA a hA'⟩
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f Src S := ⟨{1, g0}, hdecS⟩
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g Src M hms hmt hli hri) hdec,
    {1, g0}, rfl, rfl, hdecS, ?_⟩
  intro s hs
  rw [Finset.mem_insert, Finset.mem_singleton] at hs
  rcases hs with rfl | rfl
  · rfl
  · exact hfix0 (FreeGroup.of 1)

end Problems.Geometry.banach_tarski
