import Library.Analysis.ResidueTheorem.PathConcatSum
import Library.Analysis.ResidueTheorem.PathReverse

/-!
# Path connectors for the residue theorem

This file constructs, for a function `Q : ℂ → ℂ` analytic on `ℂ \ {a}`, a uniform C¹ path
selector in `ℂ \ {a}` and a connector lemma showing that path integrals of `Q` along C¹
paths with the same endpoints agree up to the closed-loop integral. As a corollary, if every
closed C¹ loop in `ℂ \ {a}` integrates to zero, then `Q` admits a primitive on `ℂ \ {a}`.

## Main statements

- `polar_path_modulus_pos`: the polar interpolation weight $1 - t + t\|w\|$ is positive for
  $t \in [0,1]$ when $w \neq 0$.
- `polar_path_smooth`: the polar interpolation path $t \mapsto (1-t+t\|w\|) e^{it\arg w}$ is
  $C^1$ on $[0,1]$.
- `c1_path_in_punctured_plane_from_one`: `ℂ \ {0}` is C¹-path-connected from `1`.
- `path_to_basepoint_avoiding`: every point of `ℂ \ {a}` can be reached from `a + 1` by a
  C¹ path in `ℂ \ {a}`.
- `path_chooser_avoiding_singularity`: a uniform, classically chosen path selector from the
  basepoint `a + 1` to any point of `ℂ \ {a}`.
- `path_diff_eq_connector`: for C¹ paths `α`, `β`, `γ` in `ℂ \ {a}` with matching
  endpoints, the integral of `Q` along `β` minus the integral along `α` equals the integral
  along `γ`, assuming all closed loops integrate to zero.
- `path_primitive_exists_from_closed_loops`: if all closed C¹ loops in `ℂ \ {a}` integrate
  to zero for `Q`, then `Q` has a primitive on `ℂ \ {a}`.
-/

open Library.Analysis.ResidueTheorem.PathConcatSum
open Library.Analysis.ResidueTheorem.PathReverse

namespace Library.Analysis.ResidueTheorem.PathConnector

/-- The polar interpolation weight $1 - t + t\|w\|$ is positive for $t \in [0,1]$ when
`w ≠ 0`: both `1` and `‖w‖` are positive, so their convex combination remains positive. -/
theorem polar_path_modulus_pos (w : ℂ) (hw : w ≠ 0)
    (t : ℝ) (ht : t ∈ Set.Icc (0 : ℝ) 1) :
    (0:ℝ) < 1 - t + t * ‖w‖ := by
  nlinarith [norm_pos_iff.mpr hw, ht.1, ht.2,
             mul_nonneg ht.1 (norm_nonneg w)]

/-- The polar interpolation path $t \mapsto (1-t+t\|w\|) \cdot e^{it \arg w}$ is $C^1$ on
$[0,1]$ for any `w : ℂ`. -/
theorem polar_path_smooth (w : ℂ) (_hw : w ≠ 0) :
    ContDiffOn ℝ 1 (fun t : ℝ =>
        (((1 - t + t * ‖w‖ : ℝ) : ℂ)) *
          Complex.exp (((t * Complex.arg w : ℝ) : ℂ) * Complex.I))
      (Set.Icc 0 1) := by
  apply ContDiffOn.mul
  · have h1 : ContDiffOn ℝ 1 (fun t : ℝ => (1 - t + t * ‖w‖ : ℝ)) (Set.Icc 0 1) := by fun_prop
    have h2 : ContDiffOn ℝ 1 (Complex.ofReal : ℝ → ℂ) Set.univ :=
      Complex.ofRealCLM.contDiff.contDiffOn
    exact h2.comp h1 (fun _ _ => Set.mem_univ _)
  · apply ContDiffOn.cexp
    apply ContDiffOn.mul
    · have h1 : ContDiffOn ℝ 1 (fun t : ℝ => (t * Complex.arg w : ℝ)) (Set.Icc 0 1) := by
        fun_prop
      have h2 : ContDiffOn ℝ 1 (Complex.ofReal : ℝ → ℂ) Set.univ :=
        Complex.ofRealCLM.contDiff.contDiffOn
      exact h2.comp h1 (fun _ _ => Set.mem_univ _)
    · exact contDiffOn_const

/-- `ℂ \ {0}` is C¹-path-connected from `1`: for every nonzero `w : ℂ` there exists a C¹
path `γ : ℝ → ℂ` on `[0,1]` with `γ 0 = 1`, `γ 1 = w`, and `γ t ≠ 0` for all
`t ∈ [0,1]`. The witness is the polar interpolation $t \mapsto (1-t+t\|w\|) e^{it\arg w}$;
non-vanishing follows from `polar_path_modulus_pos` and `Complex.exp_ne_zero`. -/
theorem c1_path_in_punctured_plane_from_one :
    ∀ w : ℂ, w ≠ 0 → ∃ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) ∧
      γ 0 = 1 ∧ γ 1 = w ∧ (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ 0) := by
  intro w hw
  refine ⟨fun t : ℝ =>
    (((1 - t + t * ‖w‖ : ℝ) : ℂ)) *
      Complex.exp (((t * Complex.arg w : ℝ) : ℂ) * Complex.I), ?_, ?_, ?_, ?_⟩
  · exact polar_path_smooth w hw
  · change ((1 - 0 + 0 * ‖w‖ : ℝ) : ℂ) *
        Complex.exp (((0 * Complex.arg w : ℝ) : ℂ) * Complex.I) = 1
    simp
  · change ((1 - 1 + 1 * ‖w‖ : ℝ) : ℂ) *
        Complex.exp (((1 * Complex.arg w : ℝ) : ℂ) * Complex.I) = w
    have h1 : ((1 - 1 + 1 * ‖w‖ : ℝ) : ℂ) = (‖w‖ : ℂ) := by push_cast; ring
    have h2 : ((1 * Complex.arg w : ℝ) : ℂ) = (Complex.arg w : ℂ) := by push_cast; ring
    rw [h1, h2]
    exact Complex.norm_mul_exp_arg_mul_I w
  · intro t ht
    have hpos : (0:ℝ) < 1 - t + t * ‖w‖ := polar_path_modulus_pos w hw t ht
    have hreal_ne : ((1 - t + t * ‖w‖ : ℝ) : ℂ) ≠ 0 := by exact_mod_cast hpos.ne'
    exact mul_ne_zero hreal_ne (Complex.exp_ne_zero _)

/-- Every point `z ≠ a` can be reached from `a + 1` by a C¹ path in `ℂ \ {a}`. The proof
reduces to C¹-path-connectedness of `ℂ \ {0}` from `1` via the translation `z ↦ z - a`,
then shifts the resulting path by `a`. -/
theorem path_to_basepoint_avoiding
    {Q : ℂ → ℂ} {a : ℂ}
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (_h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0) :
    ∀ z : ℂ, z ≠ a →
      ∃ φ : ℝ → ℂ, ContDiffOn ℝ 1 φ (Set.Icc 0 1) ∧
        φ 0 = a + 1 ∧ φ 1 = z ∧
        (∀ t ∈ Set.Icc (0:ℝ) 1, φ t ≠ a) := by
  intro z hz
  have h_core := c1_path_in_punctured_plane_from_one
  obtain ⟨γ, hC1, h0, h1, havoid⟩ := h_core (z - a) (sub_ne_zero.mpr hz)
  refine ⟨fun t => a + γ t, ?_, ?_, ?_, ?_⟩
  · exact contDiffOn_const.add hC1
  · change a + γ 0 = a + 1
    rw [h0]
  · change a + γ 1 = z
    rw [h1]; ring
  · intro t ht hcontra
    have hcontra' : a + γ t = a := hcontra
    have hgt : γ t = 0 := by linear_combination hcontra'
    exact havoid t ht hgt

/-- Using `path_to_basepoint_avoiding`, classically choose a uniform path selector `ψ` from
the basepoint `z₀ = a + 1` to every point of `ℂ \ {a}`. The selector satisfies
`ψ z 0 = z₀`, `ψ z 1 = z`, and `ψ z t ≠ a` for all `t ∈ [0,1]`. -/
theorem path_chooser_avoiding_singularity
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0) :
    ∃ z₀ : ℂ, ∃ ψ : ℂ → (ℝ → ℂ),
      z₀ ≠ a ∧ ∀ z : ℂ, z ≠ a →
        ContDiffOn ℝ 1 (ψ z) (Set.Icc 0 1) ∧
        ψ z 0 = z₀ ∧ ψ z 1 = z ∧
        (∀ t ∈ Set.Icc (0:ℝ) 1, ψ z t ≠ a) := by
  have h_path := path_to_basepoint_avoiding hQ_an h_loops
  refine ⟨a + 1, fun z => if h : z ≠ a then Classical.choose (h_path z h) else fun _ => a + 1,
    ?_, ?_⟩
  · intro h
    have h1 : (1 : ℂ) = 0 := by linear_combination h
    exact one_ne_zero h1
  · intro z hz
    have hspec := Classical.choose_spec (h_path z hz)
    simp only [dif_pos hz]
    exact hspec

/-- Given three C¹ paths `α`, `β`, `γ` in `ℂ \ {a}` with `α 0 = β 0`, `α 1 = γ 0`, and
`β 1 = γ 1`, and assuming every closed C¹ loop in `ℂ \ {a}` integrates to zero for `Q`,
the path integral of `Q` along `β` minus the integral along `α` equals the integral along
`γ`. The proof forms the closed loop `α · γ · β⁻¹` and applies the vanishing hypothesis. -/
theorem path_diff_eq_connector
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0)
    {α β γ : ℝ → ℂ}
    (hα : ContDiffOn ℝ 1 α (Set.Icc 0 1))
    (hα_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, α t ≠ a)
    (hβ : ContDiffOn ℝ 1 β (Set.Icc 0 1))
    (hβ_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, β t ≠ a)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγ_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hα0β0 : α 0 = β 0)
    (hα1γ0 : α 1 = γ 0)
    (hβ1γ1 : β 1 = γ 1) :
    (∫ t in (0:ℝ)..1, Q (β t) * deriv β t) -
        (∫ t in (0:ℝ)..1, Q (α t) * deriv α t) =
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) := by
  obtain ⟨β_rev, hβ_rev, hβ_rev0, hβ_rev1, hβ_rev_avoid, hβ_rev_int⟩ :=
    exists_path_reverse (Q := Q) (a := a) hβ hβ_avoid
  obtain ⟨αγ, hαγ, hαγ0, hαγ1, hαγ_avoid, hαγ_int⟩ :=
    c1_path_concat_integral_sum_cont (Q := Q) (a := a) hQ_an hα hα_avoid hγ hγ_avoid hα1γ0
  have h_match : αγ 1 = β_rev 0 := by rw [hαγ1, hβ_rev0, hβ1γ1]
  obtain ⟨ψ, hψ, hψ0, hψ1, hψ_avoid, hψ_int⟩ :=
    c1_path_concat_integral_sum_cont (Q := Q) (a := a) hQ_an
      hαγ hαγ_avoid hβ_rev hβ_rev_avoid h_match
  have hψ_closed : ψ 0 = ψ 1 := by rw [hψ0, hψ1, hαγ0, hβ_rev1, hα0β0]
  have h_zero : (∫ t in (0:ℝ)..1, Q (ψ t) * deriv ψ t) = 0 :=
    h_loops ψ hψ hψ_avoid hψ_closed
  linear_combination hψ_int + hαγ_int + hβ_rev_int - h_zero

/-- If every closed C¹ loop in `ℂ \ {a}` integrates to zero for `Q`, then `Q` has a
primitive `F : ℂ → ℂ` on `ℂ \ {a}`, satisfying `F (γ 1) - F (γ 0)` equals the path
integral of `Q` along any C¹ path `γ` in `ℂ \ {a}`. -/
theorem path_primitive_exists_from_closed_loops
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (h_loops : ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
      (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0) :
    ∃ F : ℂ → ℂ, ∀ γ : ℝ → ℂ,
      ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
      (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) →
      F (γ 1) - F (γ 0) = ∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t := by
  have h_chooser := path_chooser_avoiding_singularity hQ_an h_loops
  have h_connector := @path_diff_eq_connector _ _ hQ_an h_loops
  obtain ⟨_z₀, ψ, _hz0_ne, hψ⟩ := h_chooser
  refine ⟨fun z => ∫ t in (0:ℝ)..1, Q (ψ z t) * deriv (ψ z) t, ?_⟩
  intro γ hγ hγ_avoid
  have hγ0_ne : γ 0 ≠ a := hγ_avoid 0 (Set.left_mem_Icc.mpr zero_le_one)
  have hγ1_ne : γ 1 ≠ a := hγ_avoid 1 (Set.right_mem_Icc.mpr zero_le_one)
  obtain ⟨hα_smooth, hα0, hα1, hα_avoid⟩ := hψ (γ 0) hγ0_ne
  obtain ⟨hβ_smooth, hβ0, hβ1, hβ_avoid⟩ := hψ (γ 1) hγ1_ne
  exact h_connector hα_smooth hα_avoid hβ_smooth hβ_avoid hγ hγ_avoid
    (hα0.trans hβ0.symm) hα1 hβ1

end Library.Analysis.ResidueTheorem.PathConnector
