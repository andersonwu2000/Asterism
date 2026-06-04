<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To split off the last factor of `∏ k ∈ Finset.Icc 1 (n+1), f k` in an inductive step, there is no named `prod_Icc_succ_top` lemma — instead prove `Finset.Icc 1 (n+1) = insert (n+1) (Finset.Icc 1 n)` via `ext x; simp only [Finset.mem_insert, Finset.mem_Icc]; omega`, then use `Finset.prod_insert` (after showing `n+1 ∉ Finset.Icc 1 n` by `omega`).
- When an abstract product lemma gives `(∏…) = (n:ℝ)+1` and the parent wants `(∏…) = <numeric literal>`, close with `have h := lemma n_lit; linarith [h]` — linarith treats the `∏` term as opaque and resolves the linear arithmetic `(n_lit:ℝ)+1 = literal`; bare `simpa using h` does NOT normalize `501+1` to `502`.
- After specializing an abstract product lemma at n=501, do NOT close with `norm_num at h` — it distributes `Finset.prod` over division (turns `∏ (a/b)` into `(∏ a)/(∏ b)`) and breaks the match against the parent goal; use `simpa using h` or `convert h using 1` instead.
