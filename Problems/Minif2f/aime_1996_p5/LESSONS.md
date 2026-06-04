<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Vieta sub-goals (sum/pair/prod) close reliably via polynomial-difference factoring: `linear_combination hᵢ' - hⱼ'` produces `(xᵢ-xⱼ)·(quotient)=0`, then `(mul_eq_zero.mp key).resolve_left hne_ij` extracts the quotient equation; subtracting two quotients and a second `resolve_left` pins `a+b+c=-3`, and `linarith`+`ring` finishes — this is more robust than `nlinarith` on the raw equations.
- Cubic-Vieta goals on this problem close by direct `nlinarith` once `h₁` is rewritten into h₅/h₆/h₇ and `List.Pairwise (· ≠ ·) [a,b,c]` is unpacked via `simp [List.pairwise_cons]; obtain ⟨⟨hab,hac⟩,hbc⟩` with sum-distinctness lifted manually — passing the three polynomial equations plus three `≠`s as hints (no sub-goal decomposition needed).
