import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Forward: a maximal fin-sat set cannot contain both φ and neg φ.
theorem s9_sub_1 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α) : PropForm.neg φ ∈ M → φ ∉ M := by
  intro h hφ
  have hSub : ({PropForm.neg φ, φ} : Set (PropForm α)) ⊆ M := by
    intro x hx
    simp only [Set.mem_insert_iff, Set.mem_singleton_iff] at hx
    rcases hx with rfl | rfl <;> assumption
  have hFin : ({PropForm.neg φ, φ} : Set (PropForm α)).Finite :=
    (Set.finite_singleton φ).insert (PropForm.neg φ)
  obtain ⟨v, hv⟩ := hFinSat _ hSub hFin
  have h1 : PropForm.eval v φ = true := hv φ (by simp)
  have h2 : PropForm.eval v (PropForm.neg φ) = true := hv (PropForm.neg φ) (by simp)
  simp [PropForm.eval, h1] at h2

end Problems.compactness
