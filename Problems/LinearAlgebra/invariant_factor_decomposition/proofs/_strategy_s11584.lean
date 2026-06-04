import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Direct finiteness plumbing: enumerate the image `Finset.univ.image f` via its
-- `Finset.equivFin : ↥S ≃ Fin S.card`. q = the symm-image coercion (injective by
-- subtype/equiv injectivity), key a = equivFin ⟨f a, _⟩ (f a = q (key a) by symm_apply_apply),
-- surjectivity from each enumerated value lying in the image Finset.
theorem s11584 {α : Type*} [Finite α] {β : Type*} (f : α → β) :
    ∃ (s : ℕ) (q : Fin s → β) (key : α → Fin s),
      Function.Injective q ∧ (∀ a, f a = q (key a)) ∧ (∀ t, ∃ a, f a = q t)  := by
  classical
  haveI := Fintype.ofFinite α
  set S := Finset.univ.image f with hS
  refine ⟨S.card, fun i => (S.equivFin.symm i : β), fun a => S.equivFin ⟨f a, ?_⟩, ?_, ?_, ?_⟩
  · simp [hS]
  · intro i j hij
    exact S.equivFin.symm.injective (Subtype.ext hij)
  · intro a
    simp
  · intro t
    have ht := (S.equivFin.symm t).2
    simp only [hS, Finset.mem_image, Finset.mem_univ, true_and] at ht
    obtain ⟨a, ha⟩ := ht
    exact ⟨a, ha⟩

end Problems.LinearAlgebra.invariant_factor_decomposition
