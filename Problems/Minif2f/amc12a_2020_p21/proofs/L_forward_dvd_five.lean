import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- entry_kind: Builder
theorem forward_dvd_five : ∀ n : ℕ, n ∈ ((Finset.Icc 3 8 ×ˢ Finset.Icc 1 4 ×ˢ Finset.Icc 0 1).image
      (fun p : ℕ × ℕ × ℕ => 2^p.1 * 3^p.2.1 * 5^3 * 7^p.2.2)) →
        5 ∣ n := by decide

end Problems.Minif2f.amc12a_2020_p21
