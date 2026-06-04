import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_primary_form
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_recombine_invariant_factors

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Invariant factor decomposition = primary (prime-power) decomposition, then
-- recombination of the prime-power cyclic summands into a divisibility chain.
-- `primary_form` (SG1): the K[X]-module `AEval' T` splits as `⨁ K[X]/(p i ^ e i)`
--   with `p i` monic irreducible (mathlib structure theorem for f.g. torsion PID modules).
-- `recombine_invariant_factors` (SG2, abstract over T): regroup any such prime-power
--   direct sum into invariant factors `f 0 ∣ f 1 ∣ ... ` (monic, non-unit) via CRT.
-- Combinator: transport `AEval' T` across `equiv1.trans equiv2`; side conditions from SG2.
theorem s11563 : ∀ {K : Type*} [Field K]
  {V : Type*} [AddCommGroup V] [Module K V] [FiniteDimensional K V]
  (T : V →ₗ[K] V),
  ∃ (r : ℕ) (f : Fin r → Polynomial K),
    (∀ i, (f i).Monic) ∧
    (∀ i, ¬ IsUnit (f i)) ∧
    (∀ i j, i ≤ j → f i ∣ f j) ∧
    Nonempty (Module.AEval' T ≃ₗ[Polynomial K]
      DirectSum (Fin r)
        (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {f i}))  := by
  intro K _ V _ _ _ T
  obtain ⟨ι, _, p, hirr, hmon, e, ⟨equiv1⟩⟩ := primary_form T
  obtain ⟨r, f, hfmon, hfunit, hfdvd, ⟨equiv2⟩⟩ := recombine_invariant_factors p e hirr hmon
  exact ⟨r, f, hfmon, hfunit, hfdvd, ⟨equiv1.trans equiv2⟩⟩

end Problems.LinearAlgebra.invariant_factor_decomposition
