import Mathlib
import Problems.Minif2f.imo_1964_p1_1.Defs

namespace Problems.Minif2f.imo_1964_p1_1

-- period_iter: 7 ∣ 2^(m+3k)-1 → 7 ∣ 2^m-1, by induction on k; step uses 8≡1 mod 7
theorem period_iter : ∀ (m k : ℕ), 7 ∣ 2 ^ (m + 3 * k) - 1 → 7 ∣ 2 ^ m - 1 := by
  intro m k
  induction k with
  | zero => simp
  | succ k ih =>
    intro h
    apply ih
    have heq : 2 ^ (m + 3 * (k + 1)) = 8 * 2 ^ (m + 3 * k) := by ring
    rw [heq] at h
    set p := 2 ^ (m + 3 * k) with hp_def
    have hpow_pos : 0 < p := by positivity
    obtain ⟨q, hq⟩ := h
    exact ⟨q - p, by omega⟩

end Problems.Minif2f.imo_1964_p1_1
