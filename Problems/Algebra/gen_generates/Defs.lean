import Mathlib

/-!
Shared definitions for the gen_generates problem (exam IV.1).
G n is the multiplicative wrapping of ZMod n; gen n is the
distinguished generator (additive 1).
-/

namespace Problems.Algebra.gen_generates

abbrev G (n : ℕ) : Type := Multiplicative (ZMod n)

def gen (n : ℕ) : G n := Multiplicative.ofAdd (1 : ZMod n)

end Problems.Algebra.gen_generates
