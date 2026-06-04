<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For ℕ divisibility goals of the form `7 ∣ p - 1` where `p = 2^n`, avoid `Nat.dvd_sub'` (absent); instead `set p := 2^n`, `have : 0 < p := by positivity`, `obtain ⟨q, hq⟩ := h`, then `exact ⟨q - p, by omega⟩` — omega closes the witness arithmetic automatically.
- The framework axiom probe checks for the goal-slug name (e.g. `period`) but L_*.lean stubs use an `h_` prefix (`h_period`); add `alias period := h_period` after the theorem to satisfy both the strategy call-site and the probe without renaming the stub.
