import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_letter0_partial_equiv_laws
import Problems.Geometry.banach_tarski.proofs.L_letter0_is_decomp
import Problems.Geometry.banach_tarski.proofs.L_b_letter_pieces_disjoint
import Problems.Geometry.banach_tarski.proofs.L_b_letter_split

namespace Problems.Geometry.banach_tarski

-- Generator-1 analogue of `build_letter0_equidecomp`: the b-letter piece
-- `Wᵦ ∪ Wᵦ⁻¹` of M bijects onto M via id on `Wᵦ` ({head?=(1,true)}) and
-- φ(of 1) on `Wᵦ⁻¹` ({head?=(1,false)}).  Set A=Wᵦ (kept), B=Wᵦ⁻¹ (moved by
-- g0:=φ(of 1)); the piecewise self-map f (id/g0•·) with inverse g (id/g0⁻¹•·).
-- Sub-goals: `b_letter_pieces_disjoint` (A,B disjoint) and `b_letter_split`
-- (g0''B = M\A, the meaty image equality).  The generic PartialEquiv laws and
-- IsDecompOn witness are reused verbatim from the proved siblings
-- `letter0_partial_equiv_laws` / `letter0_is_decomp` (both abstract in A,B,g0,f,g).
theorem s11480
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)

    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ e : Equidecomp E (E ≃ᵢ E),
      e.source = {x | x ∈ M ∧
          ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
           (FreeGroup.toWord (wrd x)).head? = some (1, false))} ∧
      e.target = M  := by
  classical
  set A : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, true)} with hA_def
  set B : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = some (1, false)} with hB_def
  set g0 : E ≃ᵢ E := φ (FreeGroup.of 1) with hg0_def
  set f : E → E := fun x => if x ∈ A then x else g0 • x with hf_def
  set g : E → E := fun y => if y ∈ A then y else g0⁻¹ • y with hg_def
  have hAM : A ⊆ M := fun x hx => hx.1
  have hAB : Disjoint A B := b_letter_pieces_disjoint M wrd
  have hsplit : (fun x => g0 • x) '' B = M \ A :=
    b_letter_split φ M hinv wrd (fun x hxM w => (hcoh x hxM w).2)

  have hfA : ∀ x ∈ A, f x = x := by intro x hxA; simp only [hf_def]; rw [if_pos hxA]
  have hfnA : ∀ x, x ∉ A → f x = g0 • x := by intro x hxA; simp only [hf_def]; rw [if_neg hxA]
  have hgA : ∀ y ∈ A, g y = y := by intro y hyA; simp only [hg_def]; rw [if_pos hyA]
  have hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y := by intro y hyA; simp only [hg_def]; rw [if_neg hyA]
  have hlaws : (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y) :=
    letter0_partial_equiv_laws A B M g0 f g hAM hAB hsplit hfA hfnA hgA hgnA
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f (A ∪ B) S :=
    letter0_is_decomp A B g0 f hAB hfA hfnA

  obtain ⟨hms, hmt, hli, hri⟩ := hlaws
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g (A ∪ B) M hms hmt hli hri) hdec, ?_, rfl⟩
  ext x
  simp only [hA_def, hB_def, Set.mem_setOf_eq, Set.mem_union]
  tauto


end Problems.Geometry.banach_tarski
