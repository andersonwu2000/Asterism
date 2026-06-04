import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_assoc_quot_lequiv
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_directsum_prod_uncurry
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_reindex_drop_subsingleton
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_subsingleton_quot_span_one

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Reindex the prime-power direct sum onto the invariant-factor grid in four moves.
-- `reindex_drop_subsingleton` (applied twice) bijects a direct sum onto an injective
--   sub-index, discarding summands outside the image (here the e i = 0 / padded c = 0
--   cells, which are trivial K[X]/(unit) quotients).  `assoc_quot_lequiv` matches each
--   surviving summand via `hassoc`; `directsum_prod_uncurry` flattens the Fin r × Fin s
--   grid.  Each sub-goal is witness-independent and strictly smaller than the bundle.
theorem s11578 {K : Type*} [Field K] {ι : Type*} [Fintype ι]
    (p : ι → Polynomial K) (e : ι → ℕ)
    (r s : ℕ) (q : Fin s → Polynomial K) (c : Fin r → Fin s → ℕ)
    (idx : {i : ι // 0 < e i} → Fin r × Fin s)
    (hinj : Function.Injective idx)
    (hassoc : ∀ i, Associated (p i.val ^ e i.val) (q (idx i).2 ^ c (idx i).1 (idx i).2))
    (hpad : ∀ k t, (∀ i, idx i ≠ (k, t)) → c k t = 0) :
    Nonempty (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
      ≃ₗ[Polynomial K]
      DirectSum (Fin r) (fun k => DirectSum (Fin s)
        (fun t => Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t})))  := by
  classical
  obtain ⟨eLHS⟩ := reindex_drop_subsingleton (R := Polynomial K)
      (M := fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i})
      (Subtype.val : {i // 0 < e i} → ι) Subtype.val_injective
      (fun i hi => by
        have he : e i = 0 := by
          rcases Nat.eq_zero_or_pos (e i) with h | h
          · exact h
          · exact absurd rfl (hi ⟨i, h⟩)
        dsimp only
        rw [he, pow_zero]
        exact subsingleton_quot_span_one)
  have eMid :
      DirectSum {i // 0 < e i}
          (fun j => Polynomial K ⧸ Submodule.span (Polynomial K) {p j.val ^ e j.val})
        ≃ₗ[Polynomial K]
      DirectSum {i // 0 < e i}
          (fun j => Polynomial K ⧸ Submodule.span (Polynomial K)
            {q (idx j).2 ^ c (idx j).1 (idx j).2}) :=
    DirectSum.congrLinearEquiv (fun j => (assoc_quot_lequiv (hassoc j)).some)
  obtain ⟨eUncurry⟩ := directsum_prod_uncurry (R := Polynomial K)
      (fun (k : Fin r) (t : Fin s) =>
        Polynomial K ⧸ Submodule.span (Polynomial K) {q t ^ c k t})
  obtain ⟨eRHS⟩ := reindex_drop_subsingleton (R := Polynomial K)
      (M := fun kt : Fin r × Fin s =>
        Polynomial K ⧸ Submodule.span (Polynomial K) {q kt.2 ^ c kt.1 kt.2})
      idx hinj
      (fun kt hkt => by
        have hc : c kt.1 kt.2 = 0 := hpad kt.1 kt.2 hkt
        dsimp only
        rw [hc, pow_zero]
        exact subsingleton_quot_span_one)
  exact ⟨eLHS.trans (eMid.trans (eRHS.symm.trans eUncurry.symm))⟩


end Problems.LinearAlgebra.invariant_factor_decomposition
