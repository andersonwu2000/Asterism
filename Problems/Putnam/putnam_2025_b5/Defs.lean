import Mathlib

set_option linter.style.longLine false

open Finset BigOperators

namespace Problems.Putnam.putnam_2025_b5

def modInv (p : ℕ) (k : ℕ) : ℕ := ZMod.val ((k : ZMod p)⁻¹)

def descentCount (p : ℕ) : ℕ :=
  #{k ∈ Finset.Icc 1 (p - 2) | modInv p (k + 1) < modInv p k}

end Problems.Putnam.putnam_2025_b5
