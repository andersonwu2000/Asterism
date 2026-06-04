<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `omega` alone discharges lower-bound goals from a mod-100 residue + positivity (e.g. `0 < u → 14*u%100 = 46 → 39 ≤ u`); no `interval_cases` / `decide` / auxiliary lt-lemma needed, so unfolding `u ∈ S` via `rw [hS]` and closing with `omega` is a 4-line leaf — likely applies to v_ge_89 too.
- The S = {n>0 | 14n%100=46} membership reduces to n ≡ 39 (mod 50); the only positive solutions below 89 are {39}, so u=39 and v=89 — `decide` proves `14*39%100=46` and `interval_cases`/`decide` discharges the n<89→n=39 lemma.
