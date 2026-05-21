import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Forward rationale: Base case (`T = ∅`) of the Finset-induction route the
-- Strategist proposed for `cycle_decomposition_into_loops`. When `T` is empty
-- the integral identity collapses to `∫_γ f = 0` for `f` analytic on the
-- whole simply-connected `U` with `γ` a C¹ closed path in `U`. Mathlib only
-- offers the disk case (`Mathlib.Analysis.Complex.HasPrimitives`) and
-- explicitly carries the open TODO for the simply-connected extension, so a
-- new Forward bridge is required. Generic: once supplied, the inductive
-- step peels one pole at a time and re-applies this lemma on `U` minus a
-- small disk, so it is reusable beyond the immediate decomposition target.
-- entry_kind: Backward
theorem cauchy_on_simply_connected_closed
    {U : Set ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hSC : SimplyConnectedSpace U)
    (hf : AnalyticOn ℂ f U)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U)
    (hγcl : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 0 := by
  sorry

end Problems.residue_thm
