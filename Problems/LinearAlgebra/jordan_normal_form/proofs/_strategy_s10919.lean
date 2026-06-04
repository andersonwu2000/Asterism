import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct construction: ν i := n (e i).val, and φ relabels the base `K` via `e`.
-- φ = (sigmaCongrLeft e) ≫ (sigmaSubtypeEquivOfSubset ...): the first equiv pulls the
-- base from {μ // 0 < n μ} back to `Fin m` along `e` (fibers untouched), the second
-- embeds the support subtype back into all of `K` (fibers over n μ = 0 are empty, so
-- `Fin.pos` discharges the subset side-condition). Both equivs leave the fiber index
-- alone, so value preservation is `rfl`; fiber correspondence is `e` injectivity.
theorem s10919 {K : Type*} (n : K → ℕ)
    [Fintype ((μ : K) × Fin (n μ))]
    (m : ℕ) (e : Fin m ≃ {μ : K // 0 < n μ}) :
    ∃ (ν : Fin m → ℕ)
      (φ : ((i : Fin m) × Fin (ν i)) ≃ ((μ : K) × Fin (n μ))),
      (∀ x, ((φ x).2 : ℕ) = (x.2 : ℕ)) ∧ (∀ x y, (φ x).1 = (φ y).1 ↔ x.1 = y.1)  := by
  refine ⟨fun i => n (e i).val,
    (Equiv.sigmaCongrLeft e).trans
      (Equiv.sigmaSubtypeEquivOfSubset (fun μ => Fin (n μ)) (fun μ => 0 < n μ)
        (fun μ x => x.pos)), ?_, ?_⟩
  · rintro ⟨i, j⟩
    rfl
  · rintro ⟨i, j⟩ ⟨i', j'⟩
    change (↑(e i) : K) = ↑(e i') ↔ i = i'
    rw [Subtype.coe_inj, EmbeddingLike.apply_eq_iff_eq]

end Problems.LinearAlgebra.jordan_normal_form
