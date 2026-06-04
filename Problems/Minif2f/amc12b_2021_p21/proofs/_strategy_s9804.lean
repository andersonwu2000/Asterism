import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_g_strict_anti_on_one_sqrt2

namespace Problems.Minif2f.amc12b_2021_p21

-- Bridge `2^√2 · log y < 2^y · log √2` on [1, √2) to a single monotonicity claim.
-- Set g(t) := 2^t · log √2 − 2^√2 · log t.  Then g(√2) = 0 (algebraic cancellation),
-- and g is strictly antitone on [1, √2] (g'(t) = 2^t · (log 2)(log √2) − 2^√2/t
-- stays negative throughout the interval, since the −2^√2/t term dominates).  For
-- y < √2 in [1, √2): StrictAntiOn gives g(√2) < g(y); after expanding the lambda,
-- the LHS is `2^√2 · log √2 − 2^√2 · log √2 = 0`, so linarith closes against the
-- parent inequality.
theorem s9804 :
    ∀ y : ℝ, 0 < y → y < Real.sqrt 2 → 1 ≤ y →
      (2:ℝ) ^ Real.sqrt 2 * Real.log y <
        (2:ℝ) ^ y * Real.log (Real.sqrt 2)  := by
  intro y _hy_pos hy_hi hy_lo
  have h_anti := g_strict_anti_on_one_sqrt2
  have h_one_le_sqrt2 : (1:ℝ) ≤ Real.sqrt 2 :=
    le_of_lt (lt_of_le_of_lt hy_lo hy_hi)
  have h_y_in : y ∈ Set.Icc (1:ℝ) (Real.sqrt 2) := ⟨hy_lo, le_of_lt hy_hi⟩
  have h_sqrt2_in : Real.sqrt 2 ∈ Set.Icc (1:ℝ) (Real.sqrt 2) :=
    ⟨h_one_le_sqrt2, le_refl _⟩
  have h_lt := h_anti h_y_in h_sqrt2_in hy_hi
  simp only at h_lt
  linarith

end Problems.Minif2f.amc12b_2021_p21
