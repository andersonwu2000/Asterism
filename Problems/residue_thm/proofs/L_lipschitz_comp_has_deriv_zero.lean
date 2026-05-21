import Mathlib
import Problems.residue_thm.Defs

open scoped Topology

namespace Problems.residue_thm

-- entry_kind: Builder
-- lipschitz_comp_has_deriv_zero: Lipschitz + zero derivative implies zero derivative of composition
theorem lipschitz_comp_has_deriv_zero
    {f : ℝ → ℂ} {g : ℝ → ℝ} {s : Set ℝ} {K : NNReal} {t : ℝ}
    (hf : LipschitzOnWith K f s)
    (hg_in : ∀ᶠ x in 𝓝 t, g x ∈ s)
    (hg_deriv : HasDerivAt g 0 t) :
    HasDerivAt (f ∘ g) 0 t := by
  rw [hasDerivAt_iff_isLittleO]
  simp only [smul_zero, sub_zero]
  have hgt : g t ∈ s := hg_in.self_of_nhds
  rw [hasDerivAt_iff_isLittleO] at hg_deriv
  simp only [smul_zero, sub_zero] at hg_deriv
  have hbig : (fun x => f (g x) - f (g t)) =O[𝓝 t] (fun x => g x - g t) := by
    apply Asymptotics.isBigO_iff.mpr
    refine ⟨K, ?_⟩
    filter_upwards [hg_in] with x hx
    have h := hf.dist_le_mul (g x) hx (g t) hgt
    simp only [dist_eq_norm] at h
    exact_mod_cast h
  exact hbig.trans_isLittleO hg_deriv


end Problems.residue_thm
