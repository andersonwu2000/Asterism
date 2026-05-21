import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- smoothstep_phi_exists: smoothstep φ(t)=3t²−2t³ witnesses the existence
theorem smoothstep_phi_exists :
    ∃ φ : ℝ → ℝ,
      ContDiffOn ℝ 1 φ (Set.Icc 0 1) ∧
      φ 0 = 0 ∧
      φ 1 = 1 ∧
      derivWithin φ (Set.Icc 0 1) 0 = 0 ∧
      derivWithin φ (Set.Icc 0 1) 1 = 0 ∧
      Set.MapsTo φ (Set.Icc 0 1) (Set.Icc 0 1) := by
  refine ⟨fun t => 3 * t ^ 2 - 2 * t ^ 3, ?_, by norm_num, by norm_num, ?_, ?_, ?_⟩
  · apply ContDiff.contDiffOn
    fun_prop
  · have hd : DifferentiableAt ℝ (fun t : ℝ => 3 * t ^ 2 - 2 * t ^ 3) 0 := by fun_prop
    have hu : UniqueDiffWithinAt ℝ (Set.Icc 0 1) (0 : ℝ) :=
      uniqueDiffOn_Icc_zero_one 0 (by norm_num)
    rw [hd.derivWithin hu]
    have h1 := (hasDerivAt_pow 2 (0 : ℝ)).const_smul (3 : ℝ)
    have h2 := (hasDerivAt_pow 3 (0 : ℝ)).const_smul (2 : ℝ)
    have h3 := h1.sub h2
    have heq : (fun t : ℝ => 3 * t ^ 2 - 2 * t ^ 3) =ᶠ[nhds (0 : ℝ)]
               ((3 : ℝ) • fun x : ℝ => x ^ 2) - (2 : ℝ) • fun x : ℝ => x ^ 3 :=
      Filter.Eventually.of_forall fun t => by simp [smul_eq_mul]
    exact (h3.congr_of_eventuallyEq heq).congr_deriv (by norm_num [smul_eq_mul]) |>.deriv
  · have hd : DifferentiableAt ℝ (fun t : ℝ => 3 * t ^ 2 - 2 * t ^ 3) 1 := by fun_prop
    have hu : UniqueDiffWithinAt ℝ (Set.Icc 0 1) (1 : ℝ) :=
      uniqueDiffOn_Icc_zero_one 1 (by norm_num)
    rw [hd.derivWithin hu]
    have h1 := (hasDerivAt_pow 2 (1 : ℝ)).const_smul (3 : ℝ)
    have h2 := (hasDerivAt_pow 3 (1 : ℝ)).const_smul (2 : ℝ)
    have h3 := h1.sub h2
    have heq : (fun t : ℝ => 3 * t ^ 2 - 2 * t ^ 3) =ᶠ[nhds (1 : ℝ)]
               ((3 : ℝ) • fun x : ℝ => x ^ 2) - (2 : ℝ) • fun x : ℝ => x ^ 3 :=
      Filter.Eventually.of_forall fun t => by simp [smul_eq_mul]
    exact (h3.congr_of_eventuallyEq heq).congr_deriv (by simp [smul_eq_mul]; ring) |>.deriv
  · intro t ht
    simp only [Set.mem_Icc] at ht ⊢
    constructor
    · nlinarith [sq_nonneg t, ht.1, ht.2]
    · nlinarith [sq_nonneg (1 - t), ht.1, ht.2]

end Problems.residue_thm

