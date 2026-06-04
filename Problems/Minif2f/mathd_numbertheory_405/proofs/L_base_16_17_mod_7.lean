import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs

namespace Problems.Minif2f.mathd_numbertheory_405

-- base_16_17_mod_7: unroll Fibonacci recurrence t(2)..t(17) via hrec, close with omega
theorem base_16_17_mod_7 :
    ∀ (t : ℕ → ℕ),
      t 0 = 0 →
      t 1 = 1 →
      (∀ n > 1, t n = t (n - 2) + t (n - 1)) →
      t 16 % 7 = 0 ∧ t 17 % 7 = 1 := by
  intro t h0 h1 hrec
  have h2 : t 2 = t 0 + t 1 := by have := hrec 2 (by norm_num); simp at this; exact this
  have h3 : t 3 = t 1 + t 2 := by have := hrec 3 (by norm_num); simp at this; exact this
  have h4 : t 4 = t 2 + t 3 := by have := hrec 4 (by norm_num); simp at this; exact this
  have h5 : t 5 = t 3 + t 4 := by have := hrec 5 (by norm_num); simp at this; exact this
  have h6 : t 6 = t 4 + t 5 := by have := hrec 6 (by norm_num); simp at this; exact this
  have h7 : t 7 = t 5 + t 6 := by have := hrec 7 (by norm_num); simp at this; exact this
  have h8 : t 8 = t 6 + t 7 := by have := hrec 8 (by norm_num); simp at this; exact this
  have h9 : t 9 = t 7 + t 8 := by have := hrec 9 (by norm_num); simp at this; exact this
  have h10 : t 10 = t 8 + t 9 := by have := hrec 10 (by norm_num); simp at this; exact this
  have h11 : t 11 = t 9 + t 10 := by have := hrec 11 (by norm_num); simp at this; exact this
  have h12 : t 12 = t 10 + t 11 := by have := hrec 12 (by norm_num); simp at this; exact this
  have h13 : t 13 = t 11 + t 12 := by have := hrec 13 (by norm_num); simp at this; exact this
  have h14 : t 14 = t 12 + t 13 := by have := hrec 14 (by norm_num); simp at this; exact this
  have h15 : t 15 = t 13 + t 14 := by have := hrec 15 (by norm_num); simp at this; exact this
  have h16 : t 16 = t 14 + t 15 := by have := hrec 16 (by norm_num); simp at this; exact this
  have h17 : t 17 = t 15 + t 16 := by have := hrec 17 (by norm_num); simp at this; exact this
  omega

end Problems.Minif2f.mathd_numbertheory_405
