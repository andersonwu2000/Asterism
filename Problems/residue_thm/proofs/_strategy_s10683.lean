import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_ftc_const_add_right_half
import Problems.residue_thm.proofs.L_right_integrand_cont_on_icc

namespace Problems.residue_thm

-- Two-step FTC: (1) `right_integrand_cont_on_icc` — `2 · derivWithin β' (Icc 0 1) (2·s-1)`
-- is continuous on `Icc (1/2) 1` from `ContDiffOn ℝ 1 β'`.
-- (2) `ftc_const_add_right_half` — abstract FTC: for any continuous `g` on `Icc (1/2) 1`
-- and any constant `C`, `fun u => C + ∫ s in (1/2)..u, g s` has derivative `g(t)` at
-- every `t ∈ Ioo (1/2) 1`. Specialise to `g := 2 · derivWithin β' (Icc 0 1) (2·s-1)`
-- and `C := α' 0 + ∫ s in 0..(1/2), 2 · derivWithin α' (Icc 0 1) (2·s)`.
theorem s10683
    {α' β' : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1)) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      HasDerivAt
        (fun u : ℝ => (α' 0 + ∫ s in (0:ℝ)..((1:ℝ)/2),
                  2 * derivWithin α' (Set.Icc 0 1) (2*s)) +
          ∫ s in ((1:ℝ)/2)..u, 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
        (2 * derivWithin β' (Set.Icc 0 1) (2*t - 1)) t  := by
  intro t ht
  have h_cont := right_integrand_cont_on_icc hβ'
  exact ftc_const_add_right_half h_cont
    (α' 0 + ∫ s in (0:ℝ)..((1:ℝ)/2), 2 * derivWithin α' (Set.Icc 0 1) (2*s))
    t ht

end Problems.residue_thm
