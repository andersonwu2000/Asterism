import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c2_loop_approx_same_path_int
import Problems.residue_thm.proofs.L_c2_loop_null_homotopy_simply_connected

namespace Problems.residue_thm

-- Bypass the C¹/C² obstruction (LESSONS line 34): the disproved sibling
-- `homotopy_to_constant_simply_connected_open` showed `H 0 = γ` pointwise forces γ
-- to be C² (which it isn't). Replace γ with a C² loop η of equal contour integral.
-- Sub-goals:
--   (1) `c2_loop_approx_same_path_int` (Backward) — produce a C² closed loop η in U
--       with η 0 = γ 0 whose ∫ g(η)·η' matches ∫ g(γ)·γ' (ball-cover concordance).
--   (2) `c2_loop_null_homotopy_simply_connected` (Backward) — for a C² loop in
--       simply-connected open U, build the C² null-homotopy to a constant (the
--       C¹ case was disproved, but the C² hypothesis defeats the lesson-34 trap).
-- Combinator: take H from (2) applied to η; H 0 = η so integrals match via (1),
-- and H 1 = const η 0 = const γ 0 via η 0 = γ 0.
theorem s10481
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    ∃ (H : ℝ → ℝ → ℂ),
      ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) ∧
      H 1 = (fun _ => γ 0) ∧
      (∫ t in (0:ℝ)..1, g (H 0 t) * deriv (H 0) t)
        = (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t)  := by
  obtain ⟨η, hηC2, hηMaps, hηclosed, hηstart, hIntEq⟩ :=
    c2_loop_approx_same_path_int hU hg hγ hmaps hclosed
  obtain ⟨H, hHC2, hHMaps, hHfix0, hHfix1, hH0eq, hH1eq⟩ :=
    c2_loop_null_homotopy_simply_connected hU hSC hηC2 hηMaps hηclosed
  refine ⟨H, hHC2, hHMaps, hHfix0, hHfix1, ?_, ?_⟩
  · rw [hH1eq, hηstart]
  · rw [hH0eq]; exact hIntEq

end Problems.residue_thm
