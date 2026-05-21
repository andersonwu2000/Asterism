import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_smooth_blend_segment_single_piece

namespace Problems.residue_thm

-- Build ψ pointwise: each i with i < n needs a single C² blend piece
-- from p i to p (i + 1) on [t i, t (i + 1)], with derivWithin and its second
-- iterate vanishing at both endpoints. The single-piece existence
-- smooth_blend_segment_single_piece (parametric in a ≤ b and u, v) lets us
-- Classical.choose a witness per index and stitch the family by `dif_pos hi`.
theorem s10576
    (σ : ℝ → ℝ) (hσC2 : ContDiff ℝ 2 σ) (hσ0 : σ 0 = 0) (hσ1 : σ 1 = 1)
    (hσrange : ∀ τ, τ ∈ Set.Icc (0:ℝ) 1 → σ τ ∈ Set.Icc (0:ℝ) 1)
    (hσd0 : deriv σ 0 = 0) (hσd1 : deriv σ 1 = 0)
    (hσdd0 : deriv (deriv σ) 0 = 0) (hσdd1 : deriv (deriv σ) 1 = 0)
    {n : ℕ} (t : ℕ → ℝ) (p : ℕ → ℂ)
    (htmono : ∀ i, i < n → t i ≤ t (i + 1)) :
    ∃ ψ : ℕ → ℝ → ℂ,
      ∀ i, i < n →
        ContDiffOn ℝ 2 (ψ i) (Set.Icc (t i) (t (i + 1))) ∧
        ψ i (t i) = p i ∧
        ψ i (t (i + 1)) = p (i + 1) ∧
        Set.MapsTo (ψ i) (Set.Icc (t i) (t (i + 1))) (segment ℝ (p i) (p (i + 1))) ∧
        derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))) (t i) = 0 ∧
        derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))) (t (i + 1)) = 0 ∧
        derivWithin (derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))))
            (Set.Icc (t i) (t (i + 1))) (t i) = 0 ∧
        derivWithin (derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))))
            (Set.Icc (t i) (t (i + 1))) (t (i + 1)) = 0  := by
  classical
  have h_piece : ∀ (a b : ℝ) (u v : ℂ), a ≤ b → ∃ f : ℝ → ℂ,
      ContDiffOn ℝ 2 f (Set.Icc a b) ∧
      f a = u ∧
      f b = v ∧
      Set.MapsTo f (Set.Icc a b) (segment ℝ u v) ∧
      derivWithin f (Set.Icc a b) a = 0 ∧
      derivWithin f (Set.Icc a b) b = 0 ∧
      derivWithin (derivWithin f (Set.Icc a b)) (Set.Icc a b) a = 0 ∧
      derivWithin (derivWithin f (Set.Icc a b)) (Set.Icc a b) b = 0 :=
    smooth_blend_segment_single_piece σ hσC2 hσ0 hσ1 hσrange hσd0 hσd1 hσdd0 hσdd1
  refine ⟨fun i => if hi : i < n then
    Classical.choose (h_piece (t i) (t (i + 1)) (p i) (p (i + 1)) (htmono i hi))
    else 0, ?_⟩
  intro i hi
  have hspec := Classical.choose_spec
    (h_piece (t i) (t (i + 1)) (p i) (p (i + 1)) (htmono i hi))
  simp only [dif_pos hi]
  exact hspec

end Problems.residue_thm
