import Mathlib

namespace Library.LinearAlgebra.InvariantFactor.PolynomialCRT

-- Direct leaf: pairwise-coprime principal ideals over the PID K[X] have
-- intersection = principal ideal of their product. Exactly mathlib's
-- `Ideal.iInf_span_singleton` (Submodule.span ≡ Ideal.span over a comm ring).
theorem inf_span_eq_span_prod
    {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]
    (g : ι → Polynomial K) (hg : ∀ i j, i ≠ j → IsCoprime (g i) (g j)) :
    (⨅ i, Submodule.span (Polynomial K) {g i})
      = Submodule.span (Polynomial K) {∏ i, g i}  :=
  Ideal.iInf_span_singleton hg

-- K[X]-linear Chinese Remainder iso, proved directly (leaf, no sub-goals).
-- Cite mathlib's ring-level CRT `Ideal.quotientInfRingEquivPiQuotient` (coprimality of
-- the principal ideals from `Ideal.isCoprime_span_singleton_iff` on `hg`), then upgrade
-- that `≃+*` to `≃ₗ[K[X]]` by supplying `map_smul'`: on a representative `mk a` both
-- sides reduce to `fun i => mk (r * a)`, so `rfl` after `ext i`.
theorem crt_quot_inf_pi
    {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]
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

-- assoc_quot_lequiv: Associated elements yield equal principal ideals, hence a quotient equiv.
-- Extracts unit witness from `Associated`, proves span equality, applies `Submodule.quotEquivOfEq`.
-- entry_kind: Builder
theorem assoc_quot_lequiv {R : Type*} [CommRing R] {a b : R} (h : Associated a b) :
    Nonempty ((R ⧸ Submodule.span R {a}) ≃ₗ[R] (R ⧸ Submodule.span R {b})) := by
  obtain ⟨u, hu⟩ := h
  have hspan : Submodule.span R {a} = Submodule.span R {b} := by
    apply le_antisymm
    · rw [Submodule.span_singleton_le_iff_mem]
      refine Submodule.mem_span_singleton.mpr ⟨↑u⁻¹, ?_⟩
      simp only [smul_eq_mul]
      rw [← hu]
      have hinv : (↑u⁻¹ : R) * ↑u = 1 := u.inv_mul
      calc (↑u⁻¹ : R) * (a * ↑u) = a * (↑u⁻¹ * ↑u) := by ring
        _ = a := by rw [hinv, mul_one]
    · rw [Submodule.span_singleton_le_iff_mem]
      refine Submodule.mem_span_singleton.mpr ⟨↑u, ?_⟩
      simp only [smul_eq_mul]
      rw [mul_comm, hu]
  exact ⟨Submodule.quotEquivOfEq _ _ hspan⟩

-- CRT for K[X]-modules: ⨁ᵢ K[X]/(gᵢ) ≅ K[X]/(∏ᵢ gᵢ) for pairwise-coprime g.
-- Decomposition into two strictly-simpler sub-goals + a mathlib-cited closer:
--   • inf_span_eq_span_prod (h_inf): collapses span{∏ gᵢ} to ⨅ᵢ span{gᵢ} — pure
--     ideal arithmetic from pairwise coprimality.
--   • crt_quot_inf_pi (h_crt): the genuine K[X]-linear Chinese Remainder iso
--     K[X]/(⨅ span{gᵢ}) ≃ₗ ∏ᵢ K[X]/(gᵢ) — the crux (linear upgrade of mathlib's
--     ring-equiv CRT).
-- Closer: chain DirectSum.linearEquivFunOnFintype (⨁ ≃ ∏) with crt.symm and
-- Submodule.quotEquivOfEq h_inf — both cited from mathlib.
theorem crt_directsum_prod_quot
    {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]
    (g : ι → Polynomial K) (hg : ∀ i j, i ≠ j → IsCoprime (g i) (g j)) :
    Nonempty (
      (DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {g i}))
        ≃ₗ[Polynomial K]
      (Polynomial K ⧸ Submodule.span (Polynomial K) {∏ i, g i}))  := by
  have h_inf : (⨅ i, Submodule.span (Polynomial K) {g i})
      = Submodule.span (Polynomial K) {∏ i, g i} := inf_span_eq_span_prod g hg

  have h_crt : Nonempty (
      (Polynomial K ⧸ ⨅ i, Submodule.span (Polynomial K) {g i})
        ≃ₗ[Polynomial K]
      (∀ i, Polynomial K ⧸ Submodule.span (Polynomial K) {g i})) := crt_quot_inf_pi g hg
  obtain ⟨crt⟩ := h_crt
  exact ⟨(DirectSum.linearEquivFunOnFintype (Polynomial K) ι
      (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {g i})).trans
    (crt.symm.trans (Submodule.quotEquivOfEq _ _ h_inf))⟩

-- entry_kind: Backward
theorem crt_row_collapse {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]
    (g : ι → Polynomial K) (hg : ∀ i j, i ≠ j → IsCoprime (g i) (g j)) :
    Nonempty ((DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {g i}))
      ≃ₗ[Polynomial K] (Polynomial K ⧸ Submodule.span (Polynomial K) {∏ i, g i})) := by apply crt_directsum_prod_quot <;> assumption

end Library.LinearAlgebra.InvariantFactor.PolynomialCRT
