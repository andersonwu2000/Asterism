<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `push_neg` is deprecated in this Mathlib version; use `push Not` instead to avoid warnings (e.g. `push Not at h` after `by_contra h`).
- patch.lean for minif2f problems must use `namespace Problems.Minif2f.amc12a_2002_p12` (not the shorter `Problems.amc12a_2002_p12`); the axiom probe checks the fully-qualified name and silently fails if the namespace is wrong.
