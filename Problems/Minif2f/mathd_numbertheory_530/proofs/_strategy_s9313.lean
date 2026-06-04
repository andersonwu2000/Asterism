import Mathlib
import Problems.Minif2f.mathd_numbertheory_530.Defs
import Problems.Minif2f.mathd_numbertheory_530.proofs.L_lcm_div_gcd_eq_div_mul_div
import Problems.Minif2f.mathd_numbertheory_530.proofs.L_mul_lower_bound_22

namespace Problems.Minif2f.mathd_numbertheory_530

-- Decompose into (1) pure ℕ arithmetic bound `5b < a → a < 6b → 22 ≤ a*b`
-- and (2) algebraic identity `lcm m l / gcd m l = (m/gcd) * (l/gcd)`.
-- Parent body: cast ℝ inequalities `n/k < 6`, `5 < n/k` to `n < 6k`, `5k < n`;
-- set d=gcd, a=n/d, b=k/d; derive `5b < a` and `a < 6b` via `Nat.lt_of_mul_lt_mul_right`;
-- rewrite lcm/gcd by (2) and close by (1).
theorem s9313 : ∀ (n k : ℕ) (h₀ : 0 < n ∧ 0 < k) (h₀ : (n : ℝ) / k < 6) (h₁ : (5 : ℝ) < n / k), 22 ≤ Nat.lcm n k / Nat.gcd n k  := by
  intro n k hpos hlt h5lt
  have h_arith := mul_lower_bound_22
  have h_lcm := lcm_div_gcd_eq_div_mul_div
  obtain ⟨hn, hk⟩ := hpos
  have hk_real_pos : (0 : ℝ) < (k : ℝ) := by exact_mod_cast hk
  have hn_lt_6k : n < 6 * k := by
    have := (div_lt_iff₀ hk_real_pos).mp hlt
    exact_mod_cast this
  have h5k_lt_n : 5 * k < n := by
    have := (lt_div_iff₀ hk_real_pos).mp h5lt
    exact_mod_cast this
  set d := Nat.gcd n k with hd_def
  have hd_pos : 0 < d := Nat.gcd_pos_of_pos_left k hn
  have hdvd_n : d ∣ n := Nat.gcd_dvd_left n k
  have hdvd_k : d ∣ k := Nat.gcd_dvd_right n k
  set a := n / d with ha_def
  set b := k / d with hb_def
  have hn_eq : a * d = n := Nat.div_mul_cancel hdvd_n
  have hk_eq : b * d = k := Nat.div_mul_cancel hdvd_k
  have h5b_lt_a : 5 * b < a := by
    have h1 : 5 * b * d < a * d := by
      have : 5 * (b * d) < a * d := by rw [hn_eq, hk_eq]; linarith
      linarith
    exact Nat.lt_of_mul_lt_mul_right h1
  have ha_lt_6b : a < 6 * b := by
    have h1 : a * d < 6 * b * d := by
      have : a * d < 6 * (b * d) := by rw [hn_eq, hk_eq]; linarith
      linarith
    exact Nat.lt_of_mul_lt_mul_right h1
  rw [h_lcm n k]
  exact h_arith a b h5b_lt_a ha_lt_6b

end Problems.Minif2f.mathd_numbertheory_530
