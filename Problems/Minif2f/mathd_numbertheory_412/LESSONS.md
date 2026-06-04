<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For power-congruence subgoals (`(x+c)^n % 19 = s`), `Int.ModEq.pow n` lifts `x+c ≡ k [ZMOD 19]` (proved by `simp [Int.ModEq]; omega`) to the power, then `simp [Int.ModEq] at h; omega` closes — cleaner than substitution when base congruence is easy.
- For `x % 19 = r → f(x) % 19 = s` goals with polynomial f, use `obtain ⟨k, rfl⟩ : ∃ k, x = 19 * k + r := ⟨x / 19, by omega⟩` then `norm_num [Int.add_mul_emod_self_left, Int.mul_emod, Int.add_emod]`; omega/decide both fail on powers.
