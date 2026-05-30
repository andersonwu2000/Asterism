"""Librarian — turn a proved Problem into a mathlib-shaped Library.

See docs/internal/librarian_plan.md for the full design. This package
is the post-proof refactor pipeline (Step 0 inventory → Step 1 dedup
→ Step 2 organize → Step 3 write), gated by import-closure + root
re-derivation + axiom_probe + linter.

M1 ships Step 0 only: a mechanical inventory of a problem's proved
declarations, reusing the same DB read-path as the TREE renderer.
"""
