import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_three_lte_upper_base
import Problems.Minif2f.imo_1990_p3.proofs.L_three_lte_upper_step

namespace Problems.Minif2f.imo_1990_p3

-- Induction on k for the LTE-3 upper bound.
-- Base (k=0): ¬ 9 ∣ 2^m + 1 — finite case analysis mod 9.
-- Step: lift ¬ 3^(k+2) ∣ a+1 to ¬ 3^(k+3) ∣ a^3+1 with a = 2^(3^k·m), then
-- rewrite a^3 = 2^(3^(k+1)·m).  Each sub-goal drops universal scope or adds an
-- inductive hypothesis, so both are strictly simpler than the parent.
theorem s9786 :
    ∀ (k m : ℕ), Odd m → ¬ (3 ∣ m) → ¬ 3 ^ (k + 2) ∣ 2 ^ (3 ^ k * m) + 1  := by
  intro k m hm hnot
  induction k with
  | zero => exact three_lte_upper_base m hm hnot
  | succ k ih => exact three_lte_upper_step k m hm hnot ih

end Problems.Minif2f.imo_1990_p3
