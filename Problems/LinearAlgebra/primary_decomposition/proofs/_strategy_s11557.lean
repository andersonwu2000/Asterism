import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs
import Problems.LinearAlgebra.primary_decomposition.proofs.L_nf_mem_count_pos
import Problems.LinearAlgebra.primary_decomposition.proofs.L_nf_mem_irreducible
import Problems.LinearAlgebra.primary_decomposition.proofs.L_nf_mem_monic
import Problems.LinearAlgebra.primary_decomposition.proofs.L_nf_mem_pairwise_coprime
import Problems.LinearAlgebra.primary_decomposition.proofs.L_nf_prod_pow_count

namespace Problems.LinearAlgebra.primary_decomposition

-- Witness the Finset as `(normalizedFactors f).toFinset` and exponents as multiset
-- `count`. The five conjuncts split into independent UFD facts about membership of
-- `normalizedFactors`: each member is irreducible / monic (FieldDivision's
-- `mem_normalizedFactors_iff`), its count is positive (toFinset membership), distinct
-- members are coprime (distinct monic irreducibles), and the finset-power product
-- recovers `f` (monic ⇒ leading coeff 1, so the normalized-factor product is exactly f).
-- `classical` supplies `DecidableEq K`, giving the `NormalizationMonoid`/`toFinset`
-- instances the locked `[Field K]` signature lacks. Each sub-goal re-derives it via `[DecidableEq K]`.
theorem s11557 {K : Type*} [Field K] (f : Polynomial K)
    (hf : f.Monic) (hf0 : f ≠ 0) :
    ∃ (s : Finset (Polynomial K)) (e : Polynomial K → ℕ),
      (∀ p ∈ s, Irreducible p) ∧ (∀ p ∈ s, p.Monic) ∧ (∀ p ∈ s, 0 < e p) ∧
      (∀ p ∈ s, ∀ q ∈ s, p ≠ q → IsCoprime p q) ∧
      f = ∏ p ∈ s, p ^ (e p)  := by
  classical
  refine ⟨(UniqueFactorizationMonoid.normalizedFactors f).toFinset,
      fun p => (UniqueFactorizationMonoid.normalizedFactors f).count p, ?_, ?_, ?_, ?_, ?_⟩
  · have h1 : ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, Irreducible p :=
      nf_mem_irreducible f hf hf0
    exact h1
  · have h2 : ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, p.Monic :=
      nf_mem_monic f hf hf0
    exact h2
  · have h3 : ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
        0 < (UniqueFactorizationMonoid.normalizedFactors f).count p :=
      nf_mem_count_pos f hf hf0
    exact h3
  · have h4 : ∀ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
        ∀ q ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset, p ≠ q → IsCoprime p q :=
      nf_mem_pairwise_coprime f hf hf0
    exact h4
  · have h5 : f = ∏ p ∈ (UniqueFactorizationMonoid.normalizedFactors f).toFinset,
        p ^ (UniqueFactorizationMonoid.normalizedFactors f).count p :=
      nf_prod_pow_count f hf hf0
    exact h5

end Problems.LinearAlgebra.primary_decomposition
