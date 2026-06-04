<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To enumerate divisors of a small number N, use `Nat.mem_divisors.mpr ⟨hn, by norm_num⟩` + `have : Nat.divisors N = {…} := by decide` + `simp … at hmem` + `omega`; this is far faster than `interval_cases n <;> omega` which times out over many cases.
- `Nat.modEq_iff_dvd' (h : a ≤ b)` expects `a ≡ b [MOD n]` (smaller ≡ larger); if your hypothesis has it reversed, apply `.symm` before `.mp`.
