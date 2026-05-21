import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_int_h_split_at_half
import Problems.residue_thm.proofs.L_int_left_half_h_eq_alpha
import Problems.residue_thm.proofs.L_int_right_half_h_eq_beta

namespace Problems.residue_thm

-- Decompose ∫_0^1 Q(h)·h' into ∫_0^(1/2) + ∫_(1/2)^1, then substitute each half:
-- u = 2t on [0,1/2] turns h into α', u = 2t-1 on [1/2,1] turns h into β'.
-- Each substitution is a purely measure-theoretic change of variables (chain rule
-- a.e. on the Ioo interior); the split is justified by ContDiffOn h on Icc 0 1.
theorem s10561
    {Q : ℂ → ℂ} {α' β' h : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1/2), h t = α' (2*t))
    (hh_right : ∀ t ∈ Set.Icc (1/2 : ℝ) 1, h t = β' (2*t - 1)) :
    (∫ t in (0 : ℝ)..1, Q (h t) * deriv h t) =
      (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) +
      (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t)  := by
  have h1 := int_h_split_at_half (Q := Q) hh
  have h2 := int_left_half_h_eq_alpha (Q := Q) hα' hh hh_left
  have h3 := int_right_half_h_eq_beta (Q := Q) hβ' hh hh_right
  rw [h1, h2, h3]

end Problems.residue_thm
