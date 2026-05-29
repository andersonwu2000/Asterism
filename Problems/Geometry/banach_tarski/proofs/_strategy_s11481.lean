import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- The four PartialEquiv laws for the letter-0 piece: f = id on A / g0•· off A,
-- g = id on A / g0⁻¹•· off A.
-- Direct case split on A vs B using only: hsplit (g0•B = M\A), Disjoint A B, A ⊆ M, and the
-- group-action laws inv_smul_smul / smul_inv_smul. No nontrivial sub-claim — ships as a leaf.
theorem s11481
    (A B M : Set E) (g0 : E ≃ᵢ E) (f g : E → E)
    (hAM : A ⊆ M)
    (hAB : Disjoint A B)
    (hsplit : (fun x => g0 • x) '' B = M \ A)
    (hfA : ∀ x ∈ A, f x = x)
    (hfnA : ∀ x, x ∉ A → f x = g0 • x)
    (hgA : ∀ y ∈ A, g y = y)
    (hgnA : ∀ y, y ∉ A → g y = g0⁻¹ • y) :
    (∀ x ∈ A ∪ B, f x ∈ M) ∧ (∀ y ∈ M, g y ∈ A ∪ B) ∧
      (∀ x ∈ A ∪ B, g (f x) = x) ∧ (∀ y ∈ M, f (g y) = y)  := by
  have hBnA : ∀ x ∈ B, x ∉ A := fun x hx => (Set.disjoint_right.mp hAB) hx
  refine ⟨?_, ?_, ?_, ?_⟩
  · intro x hx
    rcases hx with hx | hx
    · rw [hfA x hx]; exact hAM hx
    · rw [hfnA x (hBnA x hx)]
      have h : g0 • x ∈ M \ A := by rw [← hsplit]; exact ⟨x, hx, rfl⟩
      exact h.1
  · intro y hy
    by_cases hyA : y ∈ A
    · rw [hgA y hyA]; exact Or.inl hyA
    · rw [hgnA y hyA]
      have hyMA : y ∈ M \ A := ⟨hy, hyA⟩
      rw [← hsplit] at hyMA
      obtain ⟨b, hb, hbeq⟩ := hyMA
      refine Or.inr ?_
      have : g0⁻¹ • y = b := by rw [← hbeq]; simp
      rw [this]; exact hb
  · intro x hx
    rcases hx with hx | hx
    · rw [hfA x hx, hgA x hx]
    · rw [hfnA x (hBnA x hx)]
      have h : g0 • x ∈ M \ A := by rw [← hsplit]; exact ⟨x, hx, rfl⟩
      rw [hgnA (g0 • x) h.2]; simp
  · intro y hy
    by_cases hyA : y ∈ A
    · rw [hgA y hyA, hfA y hyA]
    · rw [hgnA y hyA]
      have hyMA : y ∈ M \ A := ⟨hy, hyA⟩
      rw [← hsplit] at hyMA
      obtain ⟨b, hb, hbeq⟩ := hyMA
      have hinv : g0⁻¹ • y = b := by rw [← hbeq]; simp
      rw [hinv, hfnA b (hBnA b hb)]
      exact hbeq

end Problems.Geometry.banach_tarski
