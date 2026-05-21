import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- smoothstep_c2_with_zero_endpoint_derivs: smootherstep σ(t)=6t⁵-15t⁴+10t³ is C² with
-- σ(0)=0, σ(1)=1, σ([0,1])⊆[0,1], and first/second derivs zero at both endpoints.
theorem smoothstep_c2_with_zero_endpoint_derivs :
    ∃ σ : ℝ → ℝ,
      ContDiff ℝ 2 σ ∧
      σ 0 = 0 ∧ σ 1 = 1 ∧
      (∀ τ, τ ∈ Set.Icc (0:ℝ) 1 → σ τ ∈ Set.Icc (0:ℝ) 1) ∧
      deriv σ 0 = 0 ∧ deriv σ 1 = 0 ∧
      deriv (deriv σ) 0 = 0 ∧ deriv (deriv σ) 1 = 0 := by
  -- smootherstep: σ t = 6t⁵-15t⁴+10t³, σ'(t)=30t²(t-1)²≥0, σ''(t)=120t³-180t²+60t
  refine ⟨fun t => 6*t^5 - 15*t^4 + 10*t^3, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · fun_prop
  · norm_num
  · norm_num
  · intro τ ⟨h0, h1⟩
    have hfact1 : 6*τ^5 - 15*τ^4 + 10*τ^3 = τ^3 * (6*τ^2 - 15*τ + 10) := by ring
    have hfact2 : 1 - (6*τ^5 - 15*τ^4 + 10*τ^3) = (1 - τ)^3 * (6*τ^2 + 3*τ + 1) := by ring
    have hq1 : 6*τ^2 - 15*τ + 10 ≥ 0 := by nlinarith [sq_nonneg (τ - 5/4)]
    have hq2 : 6*τ^2 + 3*τ + 1 ≥ 0 := by nlinarith [sq_nonneg τ]
    have ht3 : τ^3 ≥ 0 := by positivity
    have h1t3 : (1 - τ)^3 ≥ 0 := by nlinarith [sq_nonneg (1 - τ)]
    refine ⟨?_, ?_⟩
    · nlinarith [mul_nonneg ht3 hq1]
    · nlinarith [mul_nonneg h1t3 hq2]
  · -- deriv σ 0 = 0
    have hd : ∀ x : ℝ, HasDerivAt (fun t : ℝ => 6*t^5 - 15*t^4 + 10*t^3)
        (30*x^4 - 60*x^3 + 30*x^2) x := fun x => by
      have h5 := (hasDerivAt_pow 5 x).const_mul (6:ℝ)
      have h4 := (hasDerivAt_pow 4 x).const_mul (15:ℝ)
      have h3 := (hasDerivAt_pow 3 x).const_mul (10:ℝ)
      have key := h5.sub (h4.sub h3)
      simp only [Nat.cast_ofNat, Nat.reduceSub] at key
      convert key using 1
      · funext t; simp only [Pi.sub_apply]; ring
      · ring
    rw [(hd 0).deriv]; norm_num
  · -- deriv σ 1 = 0
    have hd : ∀ x : ℝ, HasDerivAt (fun t : ℝ => 6*t^5 - 15*t^4 + 10*t^3)
        (30*x^4 - 60*x^3 + 30*x^2) x := fun x => by
      have h5 := (hasDerivAt_pow 5 x).const_mul (6:ℝ)
      have h4 := (hasDerivAt_pow 4 x).const_mul (15:ℝ)
      have h3 := (hasDerivAt_pow 3 x).const_mul (10:ℝ)
      have key := h5.sub (h4.sub h3)
      simp only [Nat.cast_ofNat, Nat.reduceSub] at key
      convert key using 1
      · funext t; simp only [Pi.sub_apply]; ring
      · ring
    rw [(hd 1).deriv]; norm_num
  · -- deriv (deriv σ) 0 = 0
    have hd : ∀ x : ℝ, HasDerivAt (fun t : ℝ => 6*t^5 - 15*t^4 + 10*t^3)
        (30*x^4 - 60*x^3 + 30*x^2) x := fun x => by
      have h5 := (hasDerivAt_pow 5 x).const_mul (6:ℝ)
      have h4 := (hasDerivAt_pow 4 x).const_mul (15:ℝ)
      have h3 := (hasDerivAt_pow 3 x).const_mul (10:ℝ)
      have key := h5.sub (h4.sub h3)
      simp only [Nat.cast_ofNat, Nat.reduceSub] at key
      convert key using 1
      · funext t; simp only [Pi.sub_apply]; ring
      · ring
    have hd' : ∀ x : ℝ, HasDerivAt (fun t : ℝ => 30*t^4 - 60*t^3 + 30*t^2)
        (120*x^3 - 180*x^2 + 60*x) x := fun x => by
      have h4 := (hasDerivAt_pow 4 x).const_mul (30:ℝ)
      have h3 := (hasDerivAt_pow 3 x).const_mul (60:ℝ)
      have h2 := (hasDerivAt_pow 2 x).const_mul (30:ℝ)
      have key := h4.sub (h3.sub h2)
      simp only [Nat.cast_ofNat, Nat.reduceSub] at key
      convert key using 1
      · funext t; simp only [Pi.sub_apply]; ring
      · ring
    have heq : deriv (fun t : ℝ => 6*t^5 - 15*t^4 + 10*t^3) =
        fun t => 30*t^4 - 60*t^3 + 30*t^2 := funext fun x => (hd x).deriv
    rw [heq, (hd' 0).deriv]; norm_num
  · -- deriv (deriv σ) 1 = 0
    have hd : ∀ x : ℝ, HasDerivAt (fun t : ℝ => 6*t^5 - 15*t^4 + 10*t^3)
        (30*x^4 - 60*x^3 + 30*x^2) x := fun x => by
      have h5 := (hasDerivAt_pow 5 x).const_mul (6:ℝ)
      have h4 := (hasDerivAt_pow 4 x).const_mul (15:ℝ)
      have h3 := (hasDerivAt_pow 3 x).const_mul (10:ℝ)
      have key := h5.sub (h4.sub h3)
      simp only [Nat.cast_ofNat, Nat.reduceSub] at key
      convert key using 1
      · funext t; simp only [Pi.sub_apply]; ring
      · ring
    have hd' : ∀ x : ℝ, HasDerivAt (fun t : ℝ => 30*t^4 - 60*t^3 + 30*t^2)
        (120*x^3 - 180*x^2 + 60*x) x := fun x => by
      have h4 := (hasDerivAt_pow 4 x).const_mul (30:ℝ)
      have h3 := (hasDerivAt_pow 3 x).const_mul (60:ℝ)
      have h2 := (hasDerivAt_pow 2 x).const_mul (30:ℝ)
      have key := h4.sub (h3.sub h2)
      simp only [Nat.cast_ofNat, Nat.reduceSub] at key
      convert key using 1
      · funext t; simp only [Pi.sub_apply]; ring
      · ring
    have heq : deriv (fun t : ℝ => 6*t^5 - 15*t^4 + 10*t^3) =
        fun t => 30*t^4 - 60*t^3 + 30*t^2 := funext fun x => (hd x).deriv
    rw [heq, (hd' 1).deriv]; norm_num

end Problems.residue_thm
