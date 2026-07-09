import Mathlib.Analysis.SpecialFunctions.Trigonometric.Complex
import Mathlib.Data.Real.StarOrdered
import Library.Geometry.BanachTarski.Defs
import Library.Geometry.BanachTarski.OrthogonalMatrices
import Library.Geometry.BanachTarski.RotationMatrices

/-!
# Collision angles for rotations in the Banach–Tarski construction

This file establishes countability results for sets of rotation angles that cause
"collisions" (two distinct group elements mapping the same point to the same image).
These bounds are a key ingredient in the free-group argument underlying the
Banach–Tarski paradox.

## Main statements

- `cos_level_set_countable`: a cosine level set $\{t \mid \cos t = c\}$ is countable.
- `cos_sin_combo_zero_countable`: the zero set of a nonzero linear combination
  $\cos\varphi \cdot a - \sin\varphi \cdot b$ is countable.
- `x_rotation_collision_countable`: for an x-axis rotation family, the collision angles
  for any nonzero point form a countable set.
- `zrotation_offaxis_collision_family`: there exists a z-axis rotation family such that
  for every off-axis point, every target's collision set is countable.

## Implementation notes

The amplitude-phase decomposition (`amplitude_phase_exists`) uses `Complex.arg` to
produce a phase witness $\psi$ with $a = r\cos\psi$, $b = r\sin\psi$ where
$r = \sqrt{a^2 + b^2}$.  This converts a general trig zero set into a shifted cosine
zero set, which is then handled by `cos_level_set_countable`.
-/

open Library.Geometry.BanachTarski.Defs
open Library.Geometry.BanachTarski.OrthogonalMatrices
open Library.Geometry.BanachTarski.RotationMatrices

namespace Library.Geometry.BanachTarski.CollisionAngles


/-- A cosine level set $\{t \mid \cos t = c\}$ is countable.

Case-splits on whether $c$ is in the range of cosine.  If not, the set is empty.
Otherwise `Real.cos_eq_cos_iff` shows every solution equals $2k\pi \pm t_0$ for
some $k : \mathbb{Z}$, so the set sits inside the union of two $\mathbb{Z}$-indexed
ranges and `Set.Countable.mono` transports countability. -/
theorem cos_level_set_countable (c : ℝ) :
    {t : ℝ | Real.cos t = c}.Countable := by
  by_cases h : ∃ t₀ : ℝ, Real.cos t₀ = c
  · obtain ⟨t₀, ht₀⟩ := h
    have hcount :
        ((Set.range (fun k : ℤ => 2 * (k : ℝ) * Real.pi + t₀)) ∪
          (Set.range (fun k : ℤ => 2 * (k : ℝ) * Real.pi - t₀))).Countable :=
      (Set.countable_range _).union (Set.countable_range _)
    apply hcount.mono
    intro t ht
    simp only [Set.mem_setOf_eq] at ht
    have hcc : Real.cos t₀ = Real.cos t := by rw [ht₀, ht]
    rw [Real.cos_eq_cos_iff] at hcc
    obtain ⟨k, hk | hk⟩ := hcc
    · exact Or.inl ⟨k, hk.symm⟩
    · exact Or.inr ⟨k, hk.symm⟩
  · simp only [not_exists] at h
    have he : {t : ℝ | Real.cos t = c} = ∅ := by
      ext t
      simp only [Set.mem_setOf_eq, Set.mem_empty_iff_false, iff_false]
      exact h t
    rw [he]
    exact Set.countable_empty

/-- The zero level set $\{\theta \mid \cos\theta = 0\}$ is countable. -/
theorem cos_zero_set_countable : {θ : ℝ | Real.cos θ = 0}.Countable :=
    cos_level_set_countable 0

/-- **Amplitude-phase decomposition**: given $(a, b) \neq (0, 0)$, there exists $\psi : \mathbb{R}$
such that $a = \sqrt{a^2 + b^2}\cos\psi$ and $b = \sqrt{a^2 + b^2}\sin\psi$.

The witness is $\psi = \arg(a + bi)$ via `Complex.arg`. -/
theorem amplitude_phase_exists (a b : ℝ) (h : a ≠ 0 ∨ b ≠ 0) :
    ∃ ψ : ℝ, a = Real.sqrt (a ^ 2 + b ^ 2) * Real.cos ψ ∧
      b = Real.sqrt (a ^ 2 + b ^ 2) * Real.sin ψ := by
  have hz0 : (⟨a, b⟩ : ℂ) ≠ 0 := by
    simp only [ne_eq, Complex.ext_iff, Complex.zero_re, Complex.zero_im, not_and]
    rcases h with ha | hb <;> intro <;> simp_all
  have hnorm : ‖(⟨a, b⟩ : ℂ)‖ = Real.sqrt (a ^ 2 + b ^ 2) := by
    rw [Complex.norm_def, Complex.normSq_mk]; ring_nf
  refine ⟨Complex.arg ⟨a, b⟩, ?_, ?_⟩
  · rw [Complex.cos_arg hz0, hnorm]
    have : (⟨a, b⟩ : ℂ).re = a := rfl
    rw [this, mul_div_cancel₀]
    rw [ne_eq, ← hnorm]
    simpa using hz0
  · rw [Complex.sin_arg, hnorm]
    have : (⟨a, b⟩ : ℂ).im = b := rfl
    rw [this, mul_div_cancel₀]
    rw [ne_eq, ← hnorm]
    simpa using hz0

/-- Given the amplitude-phase data $a = r\cos\psi$, $b = r\sin\psi$ with $(a,b) \neq 0$,
the zero set $\{\varphi \mid \cos\varphi \cdot a - \sin\varphi \cdot b = 0\}$ equals the
shifted cosine zero set $\{\varphi \mid \cos(\varphi + \psi) = 0\}$. -/
theorem combo_zero_set_eq_cos_shift (a b ψ : ℝ) (h : a ≠ 0 ∨ b ≠ 0)
    (ha : a = Real.sqrt (a ^ 2 + b ^ 2) * Real.cos ψ)
    (hb : b = Real.sqrt (a ^ 2 + b ^ 2) * Real.sin ψ) :
    {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0}
      = {φ : ℝ | Real.cos (φ + ψ) = 0} := by
  have hsqrt : Real.sqrt (a ^ 2 + b ^ 2) ≠ 0 := by
    intro h0
    have hle : a ^ 2 + b ^ 2 ≤ 0 := Real.sqrt_eq_zero'.mp h0
    rcases h with ha | hb
    · exact ha (by nlinarith [sq_nonneg a, sq_nonneg b])
    · exact hb (by nlinarith [sq_nonneg a, sq_nonneg b])
  have hkey : ∀ φ : ℝ, Real.cos φ * a - Real.sin φ * b =
      Real.sqrt (a ^ 2 + b ^ 2) * Real.cos (φ + ψ) := fun φ => by
    rw [Real.cos_add]; linear_combination Real.cos φ * ha - Real.sin φ * hb
  ext φ; simp [hkey, mul_eq_zero, hsqrt]

/-- The shifted cosine zero set $\{\varphi \mid \cos(\varphi + \psi) = 0\}$ equals the image of
$\{\theta \mid \cos\theta = 0\}$ under the translation $\theta \mapsto \theta - \psi$. -/
theorem cos_shift_set_eq_image (ψ : ℝ) :
    {φ : ℝ | Real.cos (φ + ψ) = 0}
      = (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0} := by aesop

/-- Combining `combo_zero_set_eq_cos_shift` and `cos_shift_set_eq_image`: given the
amplitude-phase data, $\{\varphi \mid \cos\varphi \cdot a - \sin\varphi \cdot b = 0\}$
equals $(\cdot - \psi)'' \{\theta \mid \cos\theta = 0\}$. -/
theorem combo_zero_set_eq (a b ψ : ℝ) (h : a ≠ 0 ∨ b ≠ 0)
    (ha : a = Real.sqrt (a ^ 2 + b ^ 2) * Real.cos ψ)
    (hb : b = Real.sqrt (a ^ 2 + b ^ 2) * Real.sin ψ) :
    {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0} =
      (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0} := by
  have h1 : {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0}
      = {φ : ℝ | Real.cos (φ + ψ) = 0} :=
    combo_zero_set_eq_cos_shift a b ψ h ha hb
  have h2 : {φ : ℝ | Real.cos (φ + ψ) = 0}
      = (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0} :=
    cos_shift_set_eq_image ψ
  exact h1.trans h2

/-- **Amplitude-phase reduction**: for $(a, b) \neq (0, 0)$, there exists $\psi$ such that
the zero set $\{\varphi \mid \cos\varphi \cdot a - \sin\varphi \cdot b = 0\}$ equals
$(\cdot - \psi)'' \{\theta \mid \cos\theta = 0\}$.

Uses `amplitude_phase_exists` to obtain the phase witness via `Complex.arg`, then
`combo_zero_set_eq` to establish the set equality. -/
theorem combo_zero_eq_cos_zero_shift (a b : ℝ) (h : a ≠ 0 ∨ b ≠ 0) :
    ∃ ψ : ℝ, {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0} =
      (fun θ => θ - ψ) '' {θ : ℝ | Real.cos θ = 0} := by
  obtain ⟨ψ, ha, hb⟩ := amplitude_phase_exists a b h
  exact ⟨ψ, combo_zero_set_eq a b ψ h ha hb⟩

/-- For $(a, b) \neq (0, 0)$, the zero set $\{\varphi \mid \cos\varphi \cdot a -
\sin\varphi \cdot b = 0\}$ is countable. -/
theorem cos_sin_combo_zero_countable (a b : ℝ) (h : a ≠ 0 ∨ b ≠ 0) :
    {φ : ℝ | Real.cos φ * a - Real.sin φ * b = 0}.Countable := by
  have hcos := cos_zero_set_countable
  obtain ⟨ψ, hψ⟩ := combo_zero_eq_cos_zero_shift a b h
  rw [hψ]
  exact hcos.image _

/-- For a family `Q φ` of isometries realizing x-axis block rotation, the collision set
$\{\varphi \mid (Q_\varphi p)_0 = 0 \wedge (Q_\varphi p)_1 = 0\}$ is countable for every
nonzero $p \in E$.

The proof case-splits on whether $p_0 = 0$.  If $p_0 \neq 0$ then the first-coordinate
condition already fails for all $\varphi$ and the set is empty.  If $p_0 = 0$ then
$(p_1, p_2) \neq (0, 0)$ (since $p \neq 0$) and the second-coordinate condition reduces
to the zero set of a nonzero $\cos/\sin$ combination, which is countable by
`cos_sin_combo_zero_countable`. -/
theorem x_rotation_collision_countable
    (Q : ℝ → (E ≃ᵢ E))
    (hQ : ∀ (φ : ℝ) (x : E),
      Q φ x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x) :
    ∀ p : E, p ≠ 0 →
      {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0}.Countable := by
  intro p hp
  have hc0 : ∀ (φ : ℝ), (Q φ p) 0 = p 0 := x_rot_fixes_first_coord Q hQ p
  have hc1 : ∀ (φ : ℝ), (Q φ p) 1 = Real.cos φ * p 1 - Real.sin φ * p 2 :=
    x_rot_second_coord Q hQ p
  by_cases h0 : p 0 = 0
  · have hne : p 1 ≠ 0 ∨ p 2 ≠ 0 := by
      by_contra h
      rw [not_or, not_not, not_not] at h
      apply hp
      ext i
      fin_cases i
      · exact h0
      · exact h.1
      · exact h.2
    have hsub : {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0}
        ⊆ {φ : ℝ | Real.cos φ * p 1 - Real.sin φ * p 2 = 0} := by
      intro φ hφ
      simp only [Set.mem_setOf_eq] at hφ ⊢
      rw [← hc1 φ]; exact hφ.2
    have hcount : {φ : ℝ | Real.cos φ * p 1 - Real.sin φ * p 2 = 0}.Countable :=
      cos_sin_combo_zero_countable (p 1) (p 2) hne
    exact hcount.mono hsub
  · have hempty : {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0} = ∅ := by
      ext φ
      simp only [Set.mem_setOf_eq, Set.mem_empty_iff_false, iff_false, not_and]
      intro hcc _
      apply h0
      rw [← hc0 φ]; exact hcc
    rw [hempty]; exact Set.countable_empty

/-- There exists a family of isometries `Q φ` (x-axis block rotations) such that `Q φ 0 = 0`
and for every nonzero `p` the set $\{\varphi \mid (Q_\varphi p)_0 = 0 \wedge (Q_\varphi p)_1 = 0\}$
is countable. -/
theorem zaxis_collision_angles_per_point_countable :
    ∃ Q : ℝ → (E ≃ᵢ E),
      (∀ φ : ℝ, Q φ 0 = 0) ∧
      (∀ p : E, p ≠ 0 →
        {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0}.Countable) := by
  have hreal : ∀ φ : ℝ, ∃ e : E ≃ᵢ E, ∀ x : E,
      e x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x :=
    fun φ => orthogonal_matrix_isometry_equiv _ (x_rotation_block_orthogonal φ)
  choose Q hQ using hreal
  exact ⟨Q, fun φ => by rw [hQ φ 0]; simp, x_rotation_collision_countable Q hQ⟩

/-- If a rotation with matrix $\bigl(\begin{smallmatrix}c & -s \\ s & c\end{smallmatrix}\bigr)$
maps $(p_0, p_1)$ to $(q_0, q_1)$ and $(p_0, p_1) \neq (0, 0)$, then
$c = (p_0 q_0 + p_1 q_1) / (p_0^2 + p_1^2)$. -/
theorem cos_pinned_by_components (c s p0 p1 q0 q1 : ℝ)
    (h0 : q0 = c * p0 - s * p1) (h1 : q1 = s * p0 + c * p1)
    (hp : ¬ (p0 = 0 ∧ p1 = 0)) :
    c = (p0 * q0 + p1 * q1) / (p0 ^ 2 + p1 ^ 2) := by
  have hne : p0 ^ 2 + p1 ^ 2 ≠ 0 := by
    intro h
    apply hp
    constructor
    · nlinarith [sq_nonneg p0, sq_nonneg p1]
    · nlinarith [sq_nonneg p0, sq_nonneg p1]
  rw [eq_div_iff hne, h0, h1]
  ring

/-- Component formulas for a z-axis rotation `R0 t`: the first two coordinates of `R0 t x`
are $\cos t \cdot x_0 - \sin t \cdot x_1$ and $\sin t \cdot x_0 + \cos t \cdot x_1$. -/
theorem r0_components
    (R0 : ℝ → (E ≃ᵢ E))
    (hreal : ∀ (t : ℝ) (x : E),
      R0 t x =
        Matrix.toEuclideanLin
          (!![Real.cos t, -Real.sin t, 0;
              Real.sin t, Real.cos t, 0;
              0, 0, 1] : Matrix (Fin 3) (Fin 3) ℝ) x)
    (t : ℝ) (x : E) :
    (R0 t x) 0 = Real.cos t * x 0 - Real.sin t * x 1 ∧
    (R0 t x) 1 = Real.sin t * x 0 + Real.cos t * x 1 := by aesop

/-- If `R0 t p = q` (z-axis rotation), then `cos t` is pinned to the value
$(p_0 q_0 + p_1 q_1) / (p_0^2 + p_1^2)$ whenever $(p_0, p_1) \neq (0, 0)$.
In particular, $\{t \mid R_0(t)\,p = q\} \subseteq \{t \mid \cos t = c\}$ for a
fixed $c$. -/
theorem collision_forces_cos
    (R0 : ℝ → (E ≃ᵢ E))
    (hreal : ∀ (t : ℝ) (x : E),
      R0 t x =
        Matrix.toEuclideanLin
          (!![Real.cos t, -Real.sin t, 0;
              Real.sin t, Real.cos t, 0;
              0, 0, 1] : Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) (hp : ¬ (p 0 = 0 ∧ p 1 = 0)) (q : E) :
    {t : ℝ | R0 t p = q} ⊆
      {t : ℝ | Real.cos t = (p 0 * q 0 + p 1 * q 1) / (p 0 ^ 2 + p 1 ^ 2)} := by
  intro t ht
  simp only [Set.mem_setOf_eq] at ht ⊢
  obtain ⟨hc0, hc1⟩ := r0_components R0 hreal t p
  rw [ht] at hc0 hc1
  exact cos_pinned_by_components (Real.cos t) (Real.sin t) (p 0) (p 1) (q 0) (q 1) hc0 hc1 hp

/-- If `R0 t` is a z-axis rotation and `p` is off-axis (i.e., `p 0` and `p 1` are not both
zero), then for any target `q` the collision set $\{t \mid R_0(t)\,p = q\}$ is countable.
The key step is that `collision_forces_cos` pins `cos t` to a fixed value, so the set is
a subset of a cosine level set, which is countable by `cos_level_set_countable`. -/
theorem zrot_offaxis_collision_set_countable
    (R0 : ℝ → (E ≃ᵢ E))
    (hreal : ∀ (t : ℝ) (x : E),
      R0 t x =
        Matrix.toEuclideanLin
          (!![Real.cos t, -Real.sin t, 0;
              Real.sin t, Real.cos t, 0;
              0, 0, 1] : Matrix (Fin 3) (Fin 3) ℝ) x)
    (p : E) (hp : ¬ (p 0 = 0 ∧ p 1 = 0)) (q : E) :
    {t : ℝ | R0 t p = q}.Countable := by
  have key := collision_forces_cos R0 hreal p hp q
  have hcos := cos_level_set_countable ((p 0 * q 0 + p 1 * q 1) / (p 0 ^ 2 + p 1 ^ 2))
  exact hcos.mono key

/-- **z-axis rotation collision family**: there exists a family of isometries $R_0(t)$ of $E$
realizing z-axis rotation by angle $t$, fixing the origin, satisfying the power law
$(R_0(t))^n = R_0(nt)$, and such that for every off-axis point $p$ (i.e., $p_0$ and $p_1$ not
both zero) and every target $q$, the collision set $\{t \mid R_0(t)\,p = q\}$ is countable. -/
theorem zrotation_offaxis_collision_family :
    ∃ R0 : ℝ → (E ≃ᵢ E),
      (∀ t : ℝ, R0 t 0 = 0) ∧
      (∀ (t : ℝ) (n : ℕ), (R0 t) ^ n = R0 ((n : ℝ) * t)) ∧
      (∀ p : E, ¬ (p 0 = 0 ∧ p 1 = 0) → ∀ q : E, {t : ℝ | R0 t p = q}.Countable) := by
  obtain ⟨R0, h0, hpow, hreal⟩ := z_rotation_isometry_family_realizes_matrix
  refine ⟨R0, h0, hpow, fun p hp q => ?_⟩
  exact zrot_offaxis_collision_set_countable R0 hreal p hp q

end Library.Geometry.BanachTarski.CollisionAngles
