import Mathlib

/-!
# Chinese Remainder Theorem for polynomial quotients

This file establishes linear equivalences arising from the Chinese Remainder Theorem in the
polynomial ring `K[X]` over a field `K`. The key results decompose the quotient of `K[X]` by a
product of pairwise-coprime polynomials into a direct sum of individual quotients, as needed for
the invariant factor decomposition of a module over a PID.
-/

namespace Library.LinearAlgebra.InvariantFactor.PolynomialCRT

variable {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]

/-- Chinese Remainder Theorem for pairwise-coprime polynomials: the quotient of `K[X]` by the
intersection of the principal ideals `(g i)` is linearly equivalent, as a `K[X]`-module, to the
product of the individual quotients `K[X] / (g i)`, provided the `g i` are pairwise coprime. -/
theorem crt_quot_inf_pi
    (g : ι → Polynomial K) (hg : ∀ i j, i ≠ j → IsCoprime (g i) (g j)) :
    Nonempty (
      (Polynomial K ⧸ ⨅ i, Submodule.span (Polynomial K) {g i})
        ≃ₗ[Polynomial K]
      (∀ i, Polynomial K ⧸ Submodule.span (Polynomial K) {g i}))  := by
  classical
  refine ⟨{ Ideal.quotientInfRingEquivPiQuotient
      (fun i => Submodule.span (Polynomial K) {g i})
      (fun i j hij => (Ideal.isCoprime_span_singleton_iff _ _).mpr (hg i j hij)) with
    map_smul' := ?_ }⟩
  intro r x
  obtain ⟨a, rfl⟩ := Ideal.Quotient.mk_surjective x
  ext i
  rfl

/-- Associated elements of a commutative ring generate isomorphic quotient modules: if `a` and `b`
are associated in `R`, then `R ⧸ (a) ≃ₗ[R] R ⧸ (b)`. -/
theorem assoc_quot_lequiv {R : Type*} [CommRing R] {a b : R} (h : Associated a b) :
    Nonempty ((R ⧸ Submodule.span R {a}) ≃ₗ[R] (R ⧸ Submodule.span R {b})) := by
  exact ⟨Submodule.quotEquivOfEq _ _ (le_antisymm
    (Ideal.span_singleton_le_span_singleton.mpr h.dvd')
    (Ideal.span_singleton_le_span_singleton.mpr h.dvd))⟩

/-- The direct sum of the quotients `K[X] / (g i)` over pairwise-coprime polynomials `g i` is
linearly equivalent to the single quotient `K[X] / (∏ i, g i)`. This is the module-theoretic form
of the Chinese Remainder Theorem used in the invariant factor decomposition. -/
theorem crt_directsum_prod_quot
    (g : ι → Polynomial K) (hg : ∀ i j, i ≠ j → IsCoprime (g i) (g j)) :
    Nonempty (
      (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {g i}))
        ≃ₗ[Polynomial K]
      (Polynomial K ⧸ Submodule.span (Polynomial K) {∏ i, g i}))  := by
  have h_inf : (⨅ i, Submodule.span (Polynomial K) {g i})
      = Submodule.span (Polynomial K) {∏ i, g i} := (Ideal.iInf_span_singleton hg)

  have h_crt : Nonempty (
      (Polynomial K ⧸ ⨅ i, Submodule.span (Polynomial K) {g i})
        ≃ₗ[Polynomial K]
      (∀ i, Polynomial K ⧸ Submodule.span (Polynomial K) {g i})) := crt_quot_inf_pi g hg
  obtain ⟨crt⟩ := h_crt
  exact ⟨(DirectSum.linearEquivFunOnFintype (Polynomial K) ι
      (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {g i})).trans
    (crt.symm.trans (Submodule.quotEquivOfEq _ _ h_inf))⟩

end Library.LinearAlgebra.InvariantFactor.PolynomialCRT
