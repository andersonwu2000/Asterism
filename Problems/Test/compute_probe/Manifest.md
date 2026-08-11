---
problem: Test.compute_probe
---

# Test.compute_probe

This problem exists to exercise ONE framework surface — the `compute`
tool — and is deliberately trivial to prove. Treat the tool call as the
deliverable's precondition, not as a chore to skip.

## What to do, in order

1. Run exactly this with `compute`, and read what it prints:

       print(sum(n for n in range(1, 10**6) if n % 7 == 0 and n % 11 == 3))

   Do not evaluate it in your head and do not approximate it. If the
   tool answers, put the number it printed in the leading comment of
   your patch, on a line of the form `-- compute said: <number>`.

2. If the tool does NOT answer — any error, any "unavailable" — then
   say so instead, in a line of the form `-- compute failed: <the
   tool's own message, verbatim>`, and continue to step 3 anyway. A
   failure here is a real result for this problem, not a reason to
   stop; do not work around it and do not attempt the arithmetic
   yourself.

3. Prove the claim. It is `True`, and `trivial` closes it.

## The claim to settle

    theorem compute_probe : True

Nothing else is in scope. Do not generalize it, do not decompose it,
and do not add hypotheses — a one-line proof plus the comment from
step 1 or step 2 is the whole expected deliverable.
