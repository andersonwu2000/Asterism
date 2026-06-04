import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- support_enum: the support {μ | 0 < n μ} is finite, witnessed by Fin m ≃ {μ | 0 < n μ},
-- using the injection μ ↦ ⟨μ, 0⟩ into the Fintype sigma to derive Fintype on the support.
theorem support_enum {K : Type*} (n : K → ℕ) [Fintype ((μ : K) × Fin (n μ))] :
    ∃ (m : ℕ), Nonempty (Fin m ≃ {μ : K // 0 < n μ}) := by
  haveI : Fintype {μ : K // 0 < n μ} :=
    Fintype.ofInjective
      (fun x : {μ : K // 0 < n μ} => (⟨x.1, ⟨0, x.2⟩⟩ : (μ : K) × Fin (n μ)))
      (fun ⟨_, _⟩ ⟨_, _⟩ h => by
        simp only [Sigma.mk.inj_iff] at h
        exact Subtype.ext h.1)
  exact ⟨Fintype.card {μ : K // 0 < n μ}, ⟨(Fintype.equivFin _).symm⟩⟩

end Problems.LinearAlgebra.jordan_normal_form
