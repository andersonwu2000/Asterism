-- Reduce the path integral to a chord polygon, then telescope via the homotopy grid.
-- (1) `gamma_int_eq_chord_polygon` — each γ-segment over [j/N, (j+1)/N] lies in
--     ball (c 0 j) (r 0 j) ⊆ U (bottom row of the grid); on a ball g has a primitive,
--     so the segment integral equals the chord integral with endpoints γ(j/N), γ((j+1)/N).
--     Summing over j rewrites ∫₀¹ g(γ)·γ' as the chord-polygon integral.
-- (2) `chord_polygon_int_zero` — the chord polygon over (γ(j/N))_{j=0..N} is null-homotopic
--     via the grid: define row-polygons R_i with vertices V(i,j) := H(i/N, j/N); each cell
--     (i,j) loop integrates to 0 by Cauchy on ball (c i j) (r i j); the four-edge cancellation
--     gives R_i = R_{i+1} (using hHleft, hHright as zero left/right τ-chords); induction on i
--     from i=0 (= chord polygon of γ via hH0) up to i=N (constant, zero via hH1).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10596

namespace Problems.residue_thm

def path_int_zero_given_homotopy_grid := @Problems.residue_thm.s10596

end Problems.residue_thm
