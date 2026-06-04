import Mathlib

namespace Library.LinearAlgebra.InvariantFactor.PrimeFactorData

-- entry_kind: Builder
-- coprime_distinct_monic_irred: distinct monic irreducibles over a field are coprime
-- Uses Irreducible.coprime_iff_not_dvd (PID) + associated_of_dvd + eq_of_monic_of_associated.
theorem coprime_distinct_monic_irred {K : Type*} [Field K] (a b : Polynomial K)
    (ha : a.Monic) (hb : b.Monic) (hai : Irreducible a) (hbi : Irreducible b)
    (hne : a ≠ b) : IsCoprime a b := by
  rw [hai.coprime_iff_not_dvd]
  intro hab
  exact hne (Polynomial.eq_of_monic_of_associated ha hb (hai.associated_of_dvd hbi hab))

-- Direct finiteness plumbing: enumerate the image `Finset.univ.image f` via its
-- `Finset.equivFin : ↥S ≃ Fin S.card`. q = the symm-image coercion (injective by
-- subtype/equiv injectivity), key a = equivFin ⟨f a, _⟩ (f a = q (key a) by symm_apply_apply),
-- surjectivity from each enumerated value lying in the image Finset.
theorem enum_finite_image {α : Type*} [Finite α] {β : Type*} (f : α → β) :
    ∃ (s : ℕ) (q : Fin s → β) (key : α → Fin s),
      Function.Injective q ∧ (∀ a, f a = q (key a)) ∧ (∀ t, ∃ a, f a = q t)  := by
  classical
  haveI := Fintype.ofFinite α
  set S := Finset.univ.image f with hS
  refine ⟨S.card, fun i => (S.equivFin.symm i : β), fun a => S.equivFin ⟨f a, ?_⟩, ?_, ?_, ?_⟩
  · simp [hS]
  · intro i j hij
    exact S.equivFin.symm.injective (Subtype.ext hij)
  · intro a
    simp
  · intro t
    have ht := (S.equivFin.symm t).2
    simp only [hS, Finset.mem_image, Finset.mem_univ, true_and] at ht
    obtain ⟨a, ha⟩ := ht
    exact ⟨a, ha⟩

-- Deduplicate the finite family {p i.val : 0 < e i} into distinct monic irreducible primes.
-- `enum_finite_image`: enumerate the finite image of any f : α → β as an injective q : Fin s → β
--   plus a key α → Fin s and surjectivity-onto-image — pure finiteness plumbing, no field theory.
-- `coprime_distinct_monic_irred`: two distinct monic irreducibles are coprime — leaf UFD fact.
-- Closer: q from the enumeration is monic/irreducible (each value is some p a.val) and pairwise
--   coprime (distinct ⇒ q t ≠ q t' by injectivity ⇒ leaf); p i.val = q (key i) is the key eq.
theorem distinct_primes {K : Type*} [Field K] {ι : Type*} [Fintype ι]
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

end Library.LinearAlgebra.InvariantFactor.PrimeFactorData
