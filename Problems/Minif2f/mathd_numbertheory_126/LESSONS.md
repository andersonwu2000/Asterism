<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Goal is unprovable as formalized: (x=37, a=1480) is a counterexample — gcd(1480,40)=40, lcm(1480,40)=1480=37·40, and h₃ minimizes b only for that x (40∣b ⟹ lcm(b,40)=b forces b=1480), so the x=37 branch survives alongside the intended (x=5, a=8); decline as `unprovable` rather than attempting a proof.
