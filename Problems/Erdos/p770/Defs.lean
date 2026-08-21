import Mathlib

set_option maxHeartbeats 400000

open Set ENat Filter

namespace Problems.Erdos.p770

noncomputable def h (n : ℕ) : ℕ∞ := sInf {m | 2 < m ∧
  ((Finset.Icc 2 m.toNat).image fun i => (i ^ n - 1)).gcd id = 1}

end Problems.Erdos.p770
