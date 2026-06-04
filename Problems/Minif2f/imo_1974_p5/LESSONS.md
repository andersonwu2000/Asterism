<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For fraction ordering goals `a/denom1 < b/denom2`, use `div_lt_div_iff₀` (not `div_lt_div_iff` — that name is absent/deprecated); after rewriting, `nlinarith` closes the resulting polynomial inequality from positivity hypotheses.
