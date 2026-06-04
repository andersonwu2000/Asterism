<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For the recurrence x(n) = x(n-1)-x(n-2)+x(n-3)-x(n-4), prove anti-period-5 (x(n+5) = -x(n) via 2 unfoldings of h₆ at n+5 and n+4) rather than period-10 directly (10 unfoldings); period-10 follows by chaining anti-period twice, then x(5+10k)=x(5) by induction on k.
