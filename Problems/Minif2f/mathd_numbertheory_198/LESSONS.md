<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For `∀ n ≥ k, P n` goals, `obtain ⟨j, rfl⟩ := Nat.exists_eq_add_of_le h` then plain `induction j` is simpler than `Nat.le_induction` and avoids its dependent-motive syntax; the step then reduces via `pow_succ` + `Nat.mul_mod` + IH + `norm_num`.
- `native_decide` injects a `_native.native_decide.ax_*` axiom that leaf-bypass rejects as rogue — avoid it for closed-`Nat` closers; if plain `decide` overflows (exponentiation.threshold / maxRecDepth), decompose into a `∀ n ≥ k, ... = c` lemma proved by `Nat.le_induction` instead.
