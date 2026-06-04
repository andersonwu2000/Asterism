<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `IsLeast { x : ℕ | <decidable P x> } k` closes directly with `refine ⟨?_, ?_⟩; · decide; · intro x hx; by_contra h; rw [not_le] at h; interval_cases x <;> revert hx <;> decide` — no manual residue arithmetic needed.
