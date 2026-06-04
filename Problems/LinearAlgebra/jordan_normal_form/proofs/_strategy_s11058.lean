import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct construction, no sub-goals (leaf-bypass): inline the proved-sibling logic
-- since the framework's sub-goal import inserter only fires on `new_*.lean` stubs.
-- Step 1: derive `Fintype {μ // 0 < n μ}` from the ambient sigma Fintype via the
-- injection `μ ↦ ⟨μ, 0⟩`; take `m := Fintype.card …`, `e := (Fintype.equivFin …).symm`.
-- Step 2: build `φ` as `sigmaCongrLeft e ≫ sigmaSubtypeEquivOfSubset` — both equivs
-- leave the fiber index alone (so `.2`-preservation is `rfl`), and fiber equality
-- reduces to `e`-injectivity via `Subtype.coe_inj` + `EmbeddingLike.apply_eq_iff_eq`.
theorem s11058 {K : Type*} (n : K → ℕ) [Fintype ((μ : K) × Fin (n μ))] :
    ∃ (m : ℕ) (ν : Fin m → ℕ)
      (φ : ((i : Fin m) × Fin (ν i)) ≃ ((μ : K) × Fin (n μ))),
      (∀ x, ((φ x).2 : ℕ) = (x.2 : ℕ)) ∧ (∀ x y, (φ x).1 = (φ y).1 ↔ x.1 = y.1)   := by
  haveI : Fintype {μ : K // 0 < n μ} :=
    Fintype.ofInjective
      (fun x : {μ : K // 0 < n μ} => (⟨x.1, ⟨0, x.2⟩⟩ : (μ : K) × Fin (n μ)))
      (fun ⟨_, _⟩ ⟨_, _⟩ h => by
        simp only [Sigma.mk.inj_iff] at h
        exact Subtype.ext h.1)
  refine ⟨Fintype.card {μ : K // 0 < n μ},
    fun i => n ((Fintype.equivFin {μ : K // 0 < n μ}).symm i).val,
    (Equiv.sigmaCongrLeft (Fintype.equivFin {μ : K // 0 < n μ}).symm).trans
      (Equiv.sigmaSubtypeEquivOfSubset (fun μ => Fin (n μ)) (fun μ => 0 < n μ)
        (fun _ x => x.pos)), ?_, ?_⟩
  · rintro ⟨i, j⟩
    rfl
  · rintro ⟨i, j⟩ ⟨i', j'⟩
    change (↑((Fintype.equivFin _).symm i) : K) = ↑((Fintype.equivFin _).symm i') ↔ i = i'
    rw [Subtype.coe_inj, EmbeddingLike.apply_eq_iff_eq]

end Problems.LinearAlgebra.jordan_normal_form

