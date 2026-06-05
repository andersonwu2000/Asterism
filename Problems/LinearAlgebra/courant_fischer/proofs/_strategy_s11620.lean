import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs.L_rayleigh_ge_neg_bound

namespace Problems.LinearAlgebra.courant_fischer

-- BddBelow of the Rayleigh set: exhibit -C as a lower bound, where C bounds the
-- operator norm of T (finite-dim ⇒ T is bounded, cited inline via toContinuousLinearMap).
-- Sole sub-goal `rayleigh_ge_neg_bound` drops the set/sInf layer: for any nonzero x,
-- Cauchy–Schwarz + the operator bound give ⟪Tx,x⟫/‖x‖² ≥ -C.
theorem s11620
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    (S : Submodule ℝ E) :
    BddBelow (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)  := by
  obtain ⟨C, hC⟩ : ∃ C : ℝ, ∀ x : E, ‖T x‖ ≤ C * ‖x‖ :=
    ⟨‖LinearMap.toContinuousLinearMap T‖, fun x => (LinearMap.toContinuousLinearMap T).le_opNorm x⟩
  refine ⟨-C, ?_⟩
  rintro q ⟨x, hxS, hx0, rfl⟩
  exact rayleigh_ge_neg_bound T C hC x hx0

end Problems.LinearAlgebra.courant_fischer
