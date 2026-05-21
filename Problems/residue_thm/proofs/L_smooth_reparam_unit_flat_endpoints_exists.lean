import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- smooth_reparam_unit_flat_endpoints_exists: Hermite cubic φ(t)=3t²-2t³ is C¹, fixes endpoints,
-- has flat derivative at 0 and 1, and maps [0,1] into [0,1].
theorem smooth_reparam_unit_flat_endpoints_exists :
    ∃ φ : ℝ → ℝ,
      ContDiff ℝ 1 φ ∧
      φ 0 = 0 ∧
      φ 1 = 1 ∧
      deriv φ 0 = 0 ∧
      deriv φ 1 = 0 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) := by
  refine ⟨fun t => 3 * t ^ 2 - 2 * t ^ 3, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · -- ContDiff ℝ 1
    fun_prop
  · norm_num
  · norm_num
  · -- deriv φ 0 = 0
    have h : HasDerivAt (fun t : ℝ => 3 * t ^ 2 - 2 * t ^ 3) 0 0 := by
      have := (hasDerivAt_pow 2 (0 : ℝ)).const_mul (3 : ℝ)
      have hb := (hasDerivAt_pow 3 (0 : ℝ)).const_mul (2 : ℝ)
      have h := this.sub hb
      simp [mul_comm] at h ⊢
      convert h using 1
    exact h.deriv
  · -- deriv φ 1 = 0
    have h : HasDerivAt (fun t : ℝ => 3 * t ^ 2 - 2 * t ^ 3) 0 1 := by
      have ha := (hasDerivAt_pow 2 (1 : ℝ)).const_mul (3 : ℝ)
      have hb := (hasDerivAt_pow 3 (1 : ℝ)).const_mul (2 : ℝ)
      have h := ha.sub hb
      norm_num at h
      exact h
    exact h.deriv
  · -- range: φ t ∈ [0,1] for t ∈ [0,1]
    intro t ht
    obtain ⟨ht0, ht1⟩ := ht
    simp only [Set.mem_Icc]
    constructor
    · nlinarith [sq_nonneg t]
    · nlinarith [sq_nonneg (1 - t)]

end Problems.residue_thm