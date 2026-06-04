-- CRT for K[X]-modules: ⨁ᵢ K[X]/(gᵢ) ≅ K[X]/(∏ᵢ gᵢ) for pairwise-coprime g.
-- Decomposition into two strictly-simpler sub-goals + a mathlib-cited closer:
--   • inf_span_eq_span_prod (h_inf): collapses span{∏ gᵢ} to ⨅ᵢ span{gᵢ} — pure
--     ideal arithmetic from pairwise coprimality.
--   • crt_quot_inf_pi (h_crt): the genuine K[X]-linear Chinese Remainder iso
--     K[X]/(⨅ span{gᵢ}) ≃ₗ ∏ᵢ K[X]/(gᵢ) — the crux (linear upgrade of mathlib's
--     ring-equiv CRT).
-- Closer: chain DirectSum.linearEquivFunOnFintype (⨁ ≃ ∏) with crt.symm and
-- Submodule.quotEquivOfEq h_inf — both cited from mathlib.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11568

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def crt_directsum_prod_quot := @Problems.LinearAlgebra.invariant_factor_decomposition.s11568

end Problems.LinearAlgebra.invariant_factor_decomposition
