<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- When `Real.sin_pi_div_four`/`Real.cos_pi_div_four` rewrites leave a goal of the form `X = √2*(√2/2*X - √2/2*Y)`, `linear_combination` fails because `ring` cannot reduce `√2^2` to `2`; instead prove `h1 : √2*(√2/2) = 1` via `Real.mul_self_sqrt` + `linarith`, use `calc` blocks (reassociate with `ring`, then `rw [h1]`) to establish `√2*(√2/2*cos x) = cos x` and similarly for `sin`, then close with `linarith [mul_sub ...]`.
- `Finset.sum_nbij` generates mixed membership forms: `hi` and `h` sub-goals expose finset membership (`n ∈ Finset.Icc …`, use `simp [Finset.mem_Icc]`), while `i_inj` and `i_surj` expose set-coercion membership (`∈ ↑(Finset.Icc …)`, use `rw [Finset.mem_coe, Finset.mem_Icc]`); a uniform simp call fails on at least two of the four cases.
- For degree-bound inequalities like `↑n * π / 180 < π` (given `↑n ≤ k` and `0 < π`), `linarith` fails because `↑n * π` is nonlinear — use `nlinarith` directly; similarly `Finset.sum_pos` + `Real.sin_pos_of_pos_of_lt_pi` is the idiomatic path for showing sums of sines of acute angles are positive.
- To avoid the auto-bound `{π : ℝ}` implicit in Builder theorems, prefix the theorem with `open Real in` (declaration-scoped); this binds `π` to `Real.pi` inside the theorem body and its `by` block, making `Real.pi_pos`, `Real.sin_pos_of_pos_of_lt_pi`, etc. directly usable without explicit `π` instantiation.
- `Defs.lean`'s `open Real` is file-scoped, so `π` is auto-bound as implicit `{π : ℝ}` in every downstream theorem here — when chaining sub-goal lemmas via `have h := sub_lemma`, Lean cannot synthesize that `π`; give the `have` an explicit type (`have h : ...π... := sub_lemma`) so unification fires.
- For `Int.floor` goals with `Real.sqrt`, use `Real.sqrt_sq` + `Real.sqrt_le_sqrt`/`Real.sqrt_lt_sqrt` to establish rational bounds (e.g. 141/100 ≤ √2 < 142/100 via norm_num on squares), then close with `Int.floor_eq_iff` + `linarith`.
