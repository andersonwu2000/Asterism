import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_coprime_distinct_monic_irred
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_enum_finite_image

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Deduplicate the finite family {p i.val : 0 < e i} into distinct monic irreducible primes.
-- `enum_finite_image`: enumerate the finite image of any f : α → β as an injective q : Fin s → β
--   plus a key α → Fin s and surjectivity-onto-image — pure finiteness plumbing, no field theory.
-- `coprime_distinct_monic_irred`: two distinct monic irreducibles are coprime — leaf UFD fact.
-- Closer: q from the enumeration is monic/irreducible (each value is some p a.val) and pairwise
--   coprime (distinct ⇒ q t ≠ q t' by injectivity ⇒ leaf); p i.val = q (key i) is the key eq.
theorem s11580 {K : Type*} [Field K] {ι : Type*} [Fintype ι]
    (p : ι → Polynomial K) (e : ι → ℕ) (hirr : ∀ i, Irreducible (p i))
    (hmon : ∀ i, (p i).Monic) :
    ∃ (s : ℕ) (q : Fin s → Polynomial K) (key : {i : ι // 0 < e i} → Fin s),
      (∀ t, (q t).Monic) ∧
      (∀ t, Irreducible (q t)) ∧
      (∀ t t', t ≠ t' → IsCoprime (q t) (q t')) ∧
      (∀ i, p i.val = q (key i))  := by
  classical
  have henum : ∃ (s : ℕ) (q : Fin s → Polynomial K) (key : {i : ι // 0 < e i} → Fin s),
      Function.Injective q ∧ (∀ a : {i : ι // 0 < e i}, p a.val = q (key a)) ∧
      (∀ t, ∃ a : {i : ι // 0 < e i}, p a.val = q t) :=
    enum_finite_image (fun i : {i : ι // 0 < e i} => p i.val)
  have hcop : ∀ (a b : Polynomial K), a.Monic → b.Monic → Irreducible a → Irreducible b →
      a ≠ b → IsCoprime a b := coprime_distinct_monic_irred
  obtain ⟨s, q, key, hinj, hkey, hsurj⟩ := henum
  refine ⟨s, q, key, ?_, ?_, ?_, ?_⟩
  · intro t
    obtain ⟨a, ha⟩ := hsurj t
    rw [← ha]; exact hmon a.val
  · intro t
    obtain ⟨a, ha⟩ := hsurj t
    rw [← ha]; exact hirr a.val
  · intro t t' htt'
    obtain ⟨a, ha⟩ := hsurj t
    obtain ⟨a', ha'⟩ := hsurj t'
    rw [← ha, ← ha']
    refine hcop (p a.val) (p a'.val) (hmon a.val) (hmon a'.val) (hirr a.val) (hirr a'.val) ?_
    intro hpe
    apply htt'
    apply hinj
    rw [← ha, ← ha']; exact hpe
  · intro i
    exact hkey i

end Problems.LinearAlgebra.invariant_factor_decomposition
