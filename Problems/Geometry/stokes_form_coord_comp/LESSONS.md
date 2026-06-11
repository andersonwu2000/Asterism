<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Pre-seeded patch.lean skeletons in this problem fail to parse (`expected token` at the `IsManifold I ∞ M` binder) until you add `open scoped Manifold Bundle ContDiff` after the namespace line — the `∞` notation lives in scoped `ContDiff` and Defs.lean's opens don't propagate.
