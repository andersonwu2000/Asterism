import Mathlib

/-!
# Prime factor data for the invariant factor decomposition

This file provides lemmas for packaging the prime factors appearing in an
invariant factor decomposition over a field.  The main result, `distinct_primes`,
converts an arbitrary indexed family of monic irreducible polynomials into a
deduplicated enumeration whose members are pairwise coprime.
-/

namespace Library.LinearAlgebra.InvariantFactor.PrimeFactorData

variable {K : Type*} [Field K]

/-- Two distinct monic irreducible polynomials over a field are coprime. -/
theorem coprime_distinct_monic_irred (a b : Polynomial K)
    (ha : a.Monic) (hb : b.Monic) (hai : Irreducible a) (hbi : Irreducible b)
    (hne : a ≠ b) : IsCoprime a b := by
  rw [hai.coprime_iff_not_dvd]
  intro hab
  exact hne (Polynomial.eq_of_monic_of_associated ha hb (hai.associated_of_dvd hbi hab))

/-- Given a function `f : α → β` from a finite type, there exist a natural number `s`, an
injective enumeration `q : Fin s → β` of the image of `f`, and a mapping `key : α → Fin s`
satisfying `f a = q (key a)` for all `a` and surjectivity of `q` onto the image. -/
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

/-- Given a finite family of monic irreducible polynomials `p : ι → Polynomial K` with
exponents `e : ι → ℕ`, there exists a deduplicated enumeration `q : Fin s → Polynomial K`
of the prime factors with positive exponent, such that each `q t` is monic and irreducible,
distinct members `q t` and `q t'` are coprime, and `p i = q (key i)` for every active index `i`. -/
theorem distinct_primes {ι : Type*} [Fintype ι]
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
