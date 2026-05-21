import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- smooth_reparam_hermite_monotone_exists: Hermite cubic φ(t)=3t²−2t³ witnesses the
-- C¹ monotone reparametrization: φ(0)=0, φ(1)=1, deriv φ 0=0, deriv φ 1=0,
-- φ maps [0,1] into [0,1], and deriv φ t = 6t(1-t) ≥ 0 on [0,1].
theorem smooth_reparam_hermite_monotone_exists :
    ∃ φ : ℝ → ℝ,
      ContDiff ℝ 1 φ ∧
      φ 0 = 0 ∧
      φ 1 = 1 ∧
      deriv φ 0 = 0 ∧
      deriv φ 1 = 0 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, 0 ≤ deriv φ t) := by
  -- φ t = 3t² - 2t³ (Hermite cubic), deriv φ t = 6t(1-t) ≥ 0 on [0,1]
  refine ⟨fun t => 3 * t ^ 2 - 2 * t ^ 3, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · fun_prop
  · norm_num
  · norm_num
  · -- deriv φ 0 = 0
    have hd : HasDerivAt (fun t : ℝ => 3 * t ^ 2 - 2 * t ^ 3) (6 * 0 - 6 * 0 ^ 2) 0 := by
      have h1 : HasDerivAt (fun x : ℝ => x ^ 2) (2 * 0 ^ 1) 0 := by
        simpa using hasDerivAt_pow 2 (0 : ℝ)
      have h2 : HasDerivAt (fun x : ℝ => x ^ 3) (3 * 0 ^ 2) 0 := by
        simpa using hasDerivAt_pow 3 (0 : ℝ)
      have h3 : HasDerivAt (fun x : ℝ => 3 * x ^ 2) (3 * (2 * 0 ^ 1)) 0 :=
        h1.const_mul (3 : ℝ)
      have h4 : HasDerivAt (fun x : ℝ => 2 * x ^ 3) (2 * (3 * 0 ^ 2)) 0 :=
        h2.const_mul (2 : ℝ)
      have h5 := h3.sub h4
      convert h5 using 1
      ring
    simp at hd; rw [hd.deriv]
  · -- deriv φ 1 = 0
    have hd : HasDerivAt (fun t : ℝ => 3 * t ^ 2 - 2 * t ^ 3) (6 * 1 - 6 * 1 ^ 2) 1 := by
      have h1 : HasDerivAt (fun x : ℝ => x ^ 2) (2 * 1 ^ 1) 1 := by
        simpa using hasDerivAt_pow 2 (1 : ℝ)
      have h2 : HasDerivAt (fun x : ℝ => x ^ 3) (3 * 1 ^ 2) 1 := by
        simpa using hasDerivAt_pow 3 (1 : ℝ)
      have h3 : HasDerivAt (fun x : ℝ => 3 * x ^ 2) (3 * (2 * 1 ^ 1)) 1 :=
        h1.const_mul (3 : ℝ)
      have h4 : HasDerivAt (fun x : ℝ => 2 * x ^ 3) (2 * (3 * 1 ^ 2)) 1 :=
        h2.const_mul (2 : ℝ)
      have h5 := h3.sub h4
      convert h5 using 1; ring
    norm_num at hd; rw [hd.deriv]
  · -- range in Icc 0 1
    intro t ht
    constructor
    · nlinarith [ht.1, ht.2, sq_nonneg t]
    · nlinarith [ht.1, ht.2, sq_nonneg t, sq_nonneg (1 - t)]
  · -- deriv ≥ 0
    intro t ht
    have hd : HasDerivAt (fun x : ℝ => 3 * x ^ 2 - 2 * x ^ 3) (6 * t - 6 * t ^ 2) t := by
      have h1 : HasDerivAt (fun x : ℝ => x ^ 2) (2 * t ^ 1) t := by
        simpa using hasDerivAt_pow 2 t
      have h2 : HasDerivAt (fun x : ℝ => x ^ 3) (3 * t ^ 2) t := by
        simpa using hasDerivAt_pow 3 t
      have h3 : HasDerivAt (fun x : ℝ => 3 * x ^ 2) (3 * (2 * t ^ 1)) t :=
        h1.const_mul (3 : ℝ)
      have h4 : HasDerivAt (fun x : ℝ => 2 * x ^ 3) (2 * (3 * t ^ 2)) t :=
        h2.const_mul (2 : ℝ)
      have h5 := h3.sub h4
      convert h5 using 1; ring
    rw [hd.deriv]
    nlinarith [ht.1, ht.2, sq_nonneg t]

end Problems.residue_thm