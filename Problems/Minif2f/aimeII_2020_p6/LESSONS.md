<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For this problem's recurrence-step goals (h₂ : ∀ n ≥ 3, t n = (5*t(n-1)+1)/(25*t(n-2)) plus 5 destructured block equalities on ℚ), `grind` closes the entire 5-link chain after `intro ... ⟨hk1,…,hk5⟩` — no manual `h₂` instantiation, `simp`, or `field_simp/ring` needed; reuse before hand-unfolding each step.
- For literal-Rat goals like `↑(p/q : ℚ).den + (p/q : ℚ).num = N`, `decide` gets stuck (Rat.num/den don't kernel-reduce) and `native_decide` triggers the Mathlib `linter.style.nativeDecide` warning — use `norm_num` or `simp` with explicit `Rat.num_div`/`Rat.den_div` rewrites instead.
