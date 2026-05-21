import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c2_loop_ball_cover_concordance
import Problems.residue_thm.proofs.L_path_int_eq_from_ball_cover_concordance

namespace Problems.residue_thm

-- Ball-cover concordance (LESSONS line 34 alternative b): cover γ([0,1])
-- by finitely many balls B_i ⊆ U via compactness of γ image + openness of U,
-- build a C² closed η in U matching γ at subdivision points (t_i) and lying
-- in the same balls per piece. Per-piece FTC via a local primitive on each
-- ball makes the two integrals match exactly.
-- Sub-goals:
--   (1) c2_loop_ball_cover_concordance — produce η plus a partition + ball
--       cover witness such that γ and η agree at subdivision points and both
--       lie in the same balls per piece.
--   (2) path_int_eq_from_ball_cover_concordance — given the witness, per-piece
--       FTC with a local primitive on each ball makes the two integrals agree.
theorem s10486
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    ∃ (η : ℝ → ℂ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      Set.MapsTo η (Set.Icc (0:ℝ) 1) U ∧
      η 0 = η 1 ∧
      η 0 = γ 0 ∧
      (∫ t in (0:ℝ)..1, g (η t) * deriv η t)
        = (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t)  := by
  have h_concord := c2_loop_ball_cover_concordance hU hγ hmaps hclosed
  have h_int_eq := path_int_eq_from_ball_cover_concordance hU hg hγ hmaps hclosed
  obtain ⟨η, n, t, centers, radii,
          hη_c2, hη_maps, hη_closed, hη_start,
          ht0, htn, ht_mono, hr_pos, hball_sub, hγ_in, hη_in, hagree⟩ := h_concord
  refine ⟨η, hη_c2, hη_maps, hη_closed, hη_start, ?_⟩
  have hη_c1 : ContDiffOn ℝ 1 η (Set.Icc (0:ℝ) 1) := hη_c2.of_le (by norm_num)
  exact h_int_eq η n t centers radii hη_c1 hη_maps ht0 htn ht_mono hr_pos hball_sub hγ_in hη_in hagree


end Problems.residue_thm
