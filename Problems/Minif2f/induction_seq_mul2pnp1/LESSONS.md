<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- After `induction n` + `rw [h₁ k, ih]`, `omega` needs both `2^(k+1+1) = 2 * 2^(k+1)` (via `ring`) and the bound `k+2 ≤ 2^(k+1)` (inner induction on k) supplied as hypotheses — ℕ-truncated subtraction otherwise blocks the closed-form identity.
