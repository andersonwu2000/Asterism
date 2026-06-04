-- Schur's argument for IMO 1987 P6 sub-goal: if r prime, r ∣ f(i), r² ≤ f(i),
-- find k < i (k ≤ p-2) with r ∣ f(k); base/IH gives f(k) prime; size yields ⊥.
-- Sub-goals: (1) `exists_small_witness` — the modular Schur trick (find k < i, k ≤ p-2
-- with r ∣ k²+k+p); (2) `size_contradiction` — given r ∣ f(k) and Nat.Prime f(k),
-- conclude ⊥ from r² ≤ f(i) and f(k) ≥ p (so r = f(k) ≥ p, but r² ≤ (p-2)²+(p-2)+p
-- < p², so r < p). Combinator dispatches base vs IH on whether k ≤ ⌊√(p/3)⌋.
import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs._strategy_s9769

namespace Problems.Minif2f.imo_1987_p6

def no_small_prime_factor := @Problems.Minif2f.imo_1987_p6.s9769

end Problems.Minif2f.imo_1987_p6
