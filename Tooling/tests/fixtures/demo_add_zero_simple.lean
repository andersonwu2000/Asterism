-- Demo theorem: add_zero_simple
-- Used by acceptance #0 demo bash and test fixtures.
-- Requires Mathlib. With real lake: lake env lean --json <this_file>
-- In CI: mocked via LAKE_MOCK_PROVED=1.
import Mathlib
theorem add_zero_simple (n : Nat) : n + 0 = n := by simp
