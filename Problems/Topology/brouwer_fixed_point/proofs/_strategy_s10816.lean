import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs
import Problems.Topology.brouwer_fixed_point.proofs.L_affine_span_eq_top_of_zero_mem

namespace Problems.Topology.brouwer_fixed_point

-- Decompose: pre-compose the Mathlib equivalence
-- `Convex.interior_nonempty_iff_affineSpan_eq_top` with the bridge from
-- `Submodule.span ℝ T = ⊤` (linear span) + `0 ∈ T` to `affineSpan ℝ T = ⊤`.
-- Sub_1 (affine_span_eq_top_of_zero_mem) is the pure affine-vs-linear-span
-- bridge — no convex / compact / interior content, just affine geometry.
theorem s10816
    {V : Type*} [NormedAddCommGroup V] [InnerProductSpace ℝ V]
    [FiniteDimensional ℝ V] {T : Set V}
    (hTne : T.Nonempty) (hTcomp : IsCompact T) (hTconv : Convex ℝ T)
    (h0 : (0 : V) ∈ T) (hspan : Submodule.span ℝ T = ⊤) :
    (interior T).Nonempty  := by
  have h_aff : affineSpan ℝ T = ⊤ :=
    affine_span_eq_top_of_zero_mem hTne hTcomp hTconv h0 hspan
  exact (Convex.interior_nonempty_iff_affineSpan_eq_top hTconv).mpr h_aff

end Problems.Topology.brouwer_fixed_point
