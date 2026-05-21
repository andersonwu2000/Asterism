import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- h_deriv_eq_two_beta_deriv_interior: chain rule via EventuallyEq + HasDerivAt.scomp
-- h = β'∘(2·-1) on nhds of t; scomp delivers the ℝ-scalar chain rule deriv = 2•deriv β'.
theorem h_deriv_eq_two_beta_deriv_interior
    {β' h : ℝ → ℂ}
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_right : ∀ t ∈ Set.Icc ((1 / 2) : ℝ) 1, h t = β' (2 * t - 1)) :
    ∀ t ∈ Set.Ioo ((1 : ℝ) / 2) 1, deriv h t = 2 * deriv β' (2 * t - 1) := by
  intro t ht
  have hneigh : Set.Ioo ((1/2 : ℝ)) 1 ∈ nhds t := isOpen_Ioo.mem_nhds ht
  have heq_f : h =ᶠ[nhds t] fun s => β' (2 * s - 1) := by
    filter_upwards [hneigh] with s hs
    exact hh_right s (Set.Ioo_subset_Icc_self hs)
  rw [heq_f.deriv_eq]
  have h2t : 2 * t - 1 ∈ Set.Ioo (0 : ℝ) 1 := by constructor <;> linarith [ht.1, ht.2]
  have hβ'_diff : DifferentiableAt ℝ β' (2 * t - 1) :=
    (hβ'.differentiableOn (by norm_num)).differentiableAt
      (Filter.mem_of_superset (isOpen_Ioo.mem_nhds h2t) Set.Ioo_subset_Icc_self)
  have hlin : HasDerivAt (fun s : ℝ => 2 * s - 1) 2 t := by
    have h1 := (hasDerivAt_id t).const_mul (2 : ℝ)
    have h2 := h1.sub (hasDerivAt_const t (1 : ℝ))
    simp only [mul_one, sub_zero] at h2
    exact h2
  have hchain : HasDerivAt (β' ∘ fun s => 2 * s - 1) ((2:ℝ) • deriv β' (2 * t - 1)) t :=
    hβ'_diff.hasDerivAt.scomp t hlin
  calc deriv (fun s => β' (2 * s - 1)) t
      = deriv (β' ∘ fun s => 2 * s - 1) t := by simp [Function.comp_def]
    _ = (2 : ℝ) • deriv β' (2 * t - 1) := hchain.deriv
    _ = 2 * deriv β' (2 * t - 1) := by
        rw [Complex.real_smul]; norm_cast

end Problems.residue_thm

