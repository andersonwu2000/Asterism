<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Skeletons with `IsManifold I ∞ M` in the signature fail to parse (`expected token` at the `∞`) until you add `open scoped Manifold ContDiff` inside the namespace — Defs.lean's opens don't propagate through import.
