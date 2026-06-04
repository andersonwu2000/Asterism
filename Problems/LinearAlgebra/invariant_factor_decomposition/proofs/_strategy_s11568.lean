import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_crt_quot_inf_pi
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_inf_span_eq_span_prod

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- CRT for K[X]-modules: ⨁ᵢ K[X]/(gᵢ) ≅ K[X]/(∏ᵢ gᵢ) for pairwise-coprime g.
-- Decomposition into two strictly-simpler sub-goals + a mathlib-cited closer:
--   • inf_span_eq_span_prod (h_inf): collapses span{∏ gᵢ} to ⨅ᵢ span{gᵢ} — pure
--     ideal arithmetic from pairwise coprimality.
--   • crt_quot_inf_pi (h_crt): the genuine K[X]-linear Chinese Remainder iso
--     K[X]/(⨅ span{gᵢ}) ≃ₗ ∏ᵢ K[X]/(gᵢ) — the crux (linear upgrade of mathlib's
--     ring-equiv CRT).
-- Closer: chain DirectSum.linearEquivFunOnFintype (⨁ ≃ ∏) with crt.symm and
-- Submodule.quotEquivOfEq h_inf — both cited from mathlib.
theorem s11568
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

end Problems.LinearAlgebra.invariant_factor_decomposition
