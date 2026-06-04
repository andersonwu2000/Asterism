import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_fin_base_block_enum
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_reduce_to_fin_base

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reduce to a `Fin m`-indexed base: `reduce_to_fin_base` enumerates the (finite) support
-- `{μ // 0 < n μ}` as `Fin m`, giving an equiv `φ` that preserves both fiber membership
-- (`(φ x).1 = (φ y).1 ↔ x.1 = y.1`) and the second-coordinate value (`(φ x).2 = x.2`).
-- `fin_base_block_enum` supplies the contiguous-block enumeration over the `Fin m` base
-- (provable from `finSigmaFinEquiv`, whose offset depends only on the block index).
-- The two combine: transport the `Fin m`-base enumeration across `φ`, then transfer the
-- consecutiveness iff through the value/fiber-preservation facts.
theorem s10912
    {K : Type*}
    {n : K → ℕ}
    [Fintype ((μ : K) × Fin (n μ))] :
    ∃ e : Fin (Fintype.card ((μ : K) × Fin (n μ))) ≃ ((μ : K) × Fin (n μ)),
      ∀ p q : Fin (Fintype.card ((μ : K) × Fin (n μ))), (e p).1 = (e q).1 →
        ((((e p).2 : ℕ) + 1 = ((e q).2 : ℕ)) ↔ ((p : ℕ) + 1 = (q : ℕ)))  := by
  have h_reduce := reduce_to_fin_base n
  obtain ⟨m, ν, φ, hφ2, hφ1⟩ := h_reduce
  have h_enum := fin_base_block_enum ν
  obtain ⟨e0, he0⟩ := h_enum
  have hcard : Fintype.card ((μ : K) × Fin (n μ)) = Fintype.card ((i : Fin m) × Fin (ν i)) :=
    (Fintype.card_congr φ).symm
  refine ⟨(finCongr hcard).trans (e0.trans φ), ?_⟩
  intro p q hpq
  simp only [Equiv.trans_apply, finCongr_apply] at hpq ⊢
  rw [hφ1] at hpq
  rw [hφ2, hφ2, he0 _ _ hpq]
  simp



end Problems.LinearAlgebra.jordan_normal_form
