<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For coefficient-extraction goals from a polynomial identity `h₁ : ∀ x, P x = Q x`, specialize at `x = 0, 1, -1`, apply `ring_nf` on the resulting hypotheses, then close with `nlinarith` — this avoids any direct coefficient-comparison API.
