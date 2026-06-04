<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For positivity/lower-bound induction on this recurrence, prefer `Nat.strong_induction_on` over the `h₁`-rewrite trick: `Finset.mem_range.mp hk : k < n` matches the strong-IH bound exactly, so `Finset.prod_pos` closes via `intro k hk; exact ih k (Finset.mem_range.mp hk)`.
- For ℝ-valued `Finset.prod` positivity use `Finset.prod_pos (fun k _ => ...)` / `Finset.prod_nonneg`; `Finset.one_le_prod'` fails on ℝ (needs `MulLeftMono` which ℝ lacks since multiplication isn't globally monotone).
- For this recurrence, `h₁ m` rewritten gives `∏ k ∈ Finset.range (m+1), a k = a (m+1) - 4`, eliminating the product without induction; combine with `Finset.prod_range_succ` on `h₁ (m+1)` to unfold one more step.
