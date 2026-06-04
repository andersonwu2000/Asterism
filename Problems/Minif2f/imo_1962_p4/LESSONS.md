<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Parent statement is FALSE: x=0 lies in RHS via branch `x = π/6 + m·π/6` with m=-1, but cos²(0)+cos²(0)+cos²(0)=3≠1; the answer set's π/6-step should be π/3-step (cos(3x)=0 ⟹ x = π/6 + kπ/3), so any sub-goal asserting S ⊇ RHS or set-equality is unprovable — decline at root.
