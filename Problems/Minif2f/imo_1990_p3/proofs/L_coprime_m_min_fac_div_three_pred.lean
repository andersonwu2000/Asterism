-- Reduce to two sub-goals: (1) the kernel `¬ 3 ∣ (minFac(m/3) - 1)` (uses the full
-- orderOf/Fermat chain), and (2) a Builder-level case analysis showing that given
-- `¬ 3 ∣ q-1`, any prime r ∣ gcd(m, q-1) must satisfy r ≠ 3 hence r ∣ m/3 (Euclid),
-- forcing r ≥ minFac(m/3) = q while r ∣ q-1 ⇒ r ≤ q-1; contradiction.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9856

namespace Problems.Minif2f.imo_1990_p3

def coprime_m_min_fac_div_three_pred := @Problems.Minif2f.imo_1990_p3.s9856

end Problems.Minif2f.imo_1990_p3
