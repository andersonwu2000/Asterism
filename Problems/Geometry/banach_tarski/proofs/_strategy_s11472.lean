import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_letter0_is_decomp
import Problems.Geometry.banach_tarski.proofs.L_letter0_partial_equiv_laws
import Problems.Geometry.banach_tarski.proofs.L_letter0_pieces_disjoint
import Problems.Geometry.banach_tarski.proofs.L_letter0_source_eq_union
import Problems.Geometry.banach_tarski.proofs.L_letter0_split

namespace Problems.Geometry.banach_tarski

-- Build the "first letter is generator 0" Equidecomp piece of M.
-- Split S₀ = {x∈M | word head sits at generator 0} into a-words A and a⁻¹-words B
-- (letter0_source_eq_union, letter0_pieces_disjoint). The piecewise map f = id on A,
-- φ(of 0)•· on B realizes the F₂ identity Wₐ ⊔ a·Wₐ⁻¹ = F₂, so its image is all of M;
-- the only genuine-math brick is the set identity g0•B = M\A (letter0_split).
-- The four PartialEquiv laws (letter0_partial_equiv_laws) and the finite-piece
-- decomposition (letter0_is_decomp) are abstract over f,g,A,B,g0.
theorem s11472
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ f : Equidecomp E (E ≃ᵢ E),
      f.source = {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      f.target = M  := by
  classical
  set g0 : E ≃ᵢ E := φ (FreeGroup.of 0) with hg0
  set A : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, true)} with hA
  set B : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (0, false)} with hB
  set S₀ : Set E :=
    {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} with hS₀def
  set f : E → E := fun x => if x ∈ A then x else g0 • x with hfdef
  set g : E → E := fun y => if y ∈ A then y else g0⁻¹ • y with hgdef
  have hwrd : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2), wrd (φ w • x) = w * wrd x :=
    fun x hx w => (hcoh x hx w).2
  have hsplit : (fun x => g0 • x) '' B = M \ A := letter0_split φ M hinv wrd hwrd
  have hS₀ : S₀ = A ∪ B := letter0_source_eq_union M wrd
  have hAB : Disjoint A B := letter0_pieces_disjoint M wrd
  have hAM : A ⊆ M := fun x hx => hx.1
  have hfA : ∀ x ∈ A, f x = x := by intro x hx; simp only [hfdef]; rw [if_pos hx]
  have hfnA : ∀ x, x ∉ A → f x = g0 • x := by intro x hx; simp only [hfdef]; rw [if_neg hx]
  have hgA : ∀ y ∈ A, g y = y := by intro y hy; simp only [hgdef]; rw [if_pos hy]
  have hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y := by intro y hy; simp only [hgdef]; rw [if_neg hy]
  have hlaws : (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y) :=
    letter0_partial_equiv_laws A B M g0 f g hAM hAB hsplit hfA hfnA hgA hgnA
  obtain ⟨hms0, hmt0, hli0, hri0⟩ := hlaws
  have hms : ∀ x ∈ S₀, f x ∈ M := by intro x hx; rw [hS₀] at hx; exact hms0 x hx
  have hmt : ∀ y ∈ M, g y ∈ S₀ := by intro y hy; rw [hS₀]; exact hmt0 y hy
  have hli : ∀ x ∈ S₀, g (f x) = x := by intro x hx; rw [hS₀] at hx; exact hli0 x hx
  have hri : ∀ y ∈ M, f (g y) = y := hri0
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f S₀ S := by
    rw [hS₀]; exact letter0_is_decomp A B g0 f hAB hfA hfnA
  exact ⟨Equidecomp.mk (PartialEquiv.mk f g S₀ M hms hmt hli hri) hdec, rfl, rfl⟩

end Problems.Geometry.banach_tarski
