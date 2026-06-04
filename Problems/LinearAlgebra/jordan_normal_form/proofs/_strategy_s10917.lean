import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_fin_base_equiv_of_enum
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_support_enum

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10917 {K : Type*} (n : K → ℕ) [Fintype ((μ : K) × Fin (n μ))] :
    ∃ (m : ℕ) (ν : Fin m → ℕ)
      (φ : ((i : Fin m) × Fin (ν i)) ≃ ((μ : K) × Fin (n μ))),
      (∀ x, ((φ x).2 : ℕ) = (x.2 : ℕ)) ∧ (∀ x y, (φ x).1 = (φ y).1 ↔ x.1 = y.1)  := by
  have h_support : ∃ (m : ℕ), Nonempty (Fin m ≃ {μ : K // 0 < n μ}) := by sorry
  obtain ⟨m, ⟨e⟩⟩ := h_support
  have h_build : ∃ (ν : Fin m → ℕ)
      (φ : ((i : Fin m) × Fin (ν i)) ≃ ((μ : K) × Fin (n μ))),
      (∀ x, ((φ x).2 : ℕ) = (x.2 : ℕ)) ∧ (∀ x y, (φ x).1 = (φ y).1 ↔ x.1 = y.1) := by sorry
  obtain ⟨ν, φ, hφ⟩ := h_build
  exact ⟨m, ν, φ, hφ⟩

end Problems.LinearAlgebra.jordan_normal_form
