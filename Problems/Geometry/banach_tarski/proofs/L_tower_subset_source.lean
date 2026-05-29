-- Tower ⊆ source: each tower element ((φ(of 1))⁻¹^n) y with y an empty-word rep
-- equals φ((of 1)⁻¹^n) • y, so it lands in M (hinv) and its representative word is
-- (of 1)⁻¹^n (hcoh + wrd y = 1 from h_empty), whose first letter is never (0,_).
-- Sub-goals: tower_first_letter_ne_zero (free-group combinatorics, head of (of 1)⁻¹^n)
-- and empty_word_head_eq_one (head?=none ⇒ word is 1). Both are parameter-free and
-- strictly simpler than the set-inclusion parent.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11492

namespace Problems.Geometry.banach_tarski

def tower_subset_source := @Problems.Geometry.banach_tarski.s11492

end Problems.Geometry.banach_tarski
