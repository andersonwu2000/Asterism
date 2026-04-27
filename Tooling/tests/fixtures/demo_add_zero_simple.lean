-- Demo theorem: add_zero_simple
-- Used by AC#0 / AC#6 / AC#9 in test_phase1_acceptance.py.
-- Requires Mathlib. With real lake: lake env lean --json <this_file>
-- In CI: mocked via LAKE_MOCK=proved (see docs/dev/test_hooks.md).
import Mathlib
theorem add_zero_simple (n : Nat) : n + 0 = n := by simp
