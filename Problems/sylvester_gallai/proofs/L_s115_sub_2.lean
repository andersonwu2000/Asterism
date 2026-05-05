import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s115_sub_2 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 ≤
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      ∀ (μ : ℝ),
      s.1 - q.1 = μ * (p.1 - q.1) →
      s.2 - q.2 = μ * (p.2 - q.2) →
      (q.1 - r.1)^2 + (q.2 - r.2)^2 > 0 →
      2 * μ * ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) ≤ 0 := by
  intro P _ _ p _ q _ r _ hpq _ s _ _ _ _ hsign hsq μ hμ1 hμ2 _
  -- B := |q-p|² > 0 from p ≠ q
  have hB_pos : 0 < (q.1 - p.1)^2 + (q.2 - p.2)^2 := by
    by_contra h
    push_neg at h
    have h0 : (q.1 - p.1)^2 + (q.2 - p.2)^2 = 0 :=
      le_antisymm h (by positivity)
    have hx2 : (q.1 - p.1)^2 = 0 := by
      nlinarith [sq_nonneg (q.1 - p.1), sq_nonneg (q.2 - p.2)]
    have hy2 : (q.2 - p.2)^2 = 0 := by
      nlinarith [sq_nonneg (q.1 - p.1), sq_nonneg (q.2 - p.2)]
    have hx : q.1 - p.1 = 0 := sq_eq_zero_iff.mp hx2
    have hy : q.2 - p.2 = 0 := sq_eq_zero_iff.mp hy2
    apply hpq
    exact Prod.ext (by linarith) (by linarith)
  -- Key substitution: (s-r)·(q-p) = A - μ*B
  have key : (s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)
       = ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))
         - μ * ((q.1 - p.1)^2 + (q.2 - p.2)^2) := by
    have e1 : s.1 - r.1 = (q.1 - r.1) - μ * (q.1 - p.1) := by
      linear_combination hμ1
    have e2 : s.2 - r.2 = (q.2 - r.2) - μ * (q.2 - p.2) := by
      linear_combination hμ2
    rw [e1, e2]; ring
  rw [key] at hsign hsq
  set A := (q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)
  set B := (q.1 - p.1)^2 + (q.2 - p.2)^2
  -- hsign : A * (A - μ*B) ≥ 0
  -- hsq   : A^2 ≤ (A - μ*B)^2
  by_contra hgoal
  push_neg at hgoal
  have hμA_pos : 0 < μ * A := by
    have e2μ : 2 * μ * A = 2 * (μ * A) := by ring
    linarith [hgoal, e2μ]
  have hμAB_pos : 0 < μ * A * B := mul_pos hμA_pos hB_pos
  have hU : 0 ≤ A^2 - μ*A*B := by
    have e : A^2 - μ*A*B = A * (A - μ * B) := by ring
    linarith [hsign, e]
  have hV : 0 ≤ μ^2*B^2 - 2*μ*A*B := by
    have e : (A - μ * B)^2 - A^2 = μ^2*B^2 - 2*μ*A*B := by ring
    linarith [hsq, e]
  have hP1 : 0 ≤ (A^2 - μ*A*B) * (μ^2*B^2 - 2*μ*A*B) := mul_nonneg hU hV
  have hP2 : 0 ≤ (μ*A*B) * (A^2 - μ*A*B) := mul_nonneg hμAB_pos.le hU
  have hP3 : 0 ≤ (μ*A*B) * (μ^2*B^2 - 2*μ*A*B) := mul_nonneg hμAB_pos.le hV
  have hcer :
      (A^2 - μ*A*B) * (μ^2*B^2 - 2*μ*A*B)
        + 2 * ((μ*A*B) * (A^2 - μ*A*B))
        + (μ*A*B) * (μ^2*B^2 - 2*μ*A*B)
      = -(μ*A*B)^2 := by ring
  have hWsq : 0 < (μ*A*B)^2 := pow_pos hμAB_pos 2
  linarith

end Problems.sylvester_gallai
