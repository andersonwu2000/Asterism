<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- The full `main` goal closes via `linear_combination (315/512)*h₀ + (693/256)*h₁ + (3861/512)*h₂ + (6435/256)*h₃` after `intro x y z w h₀ h₁ h₂ h₃`; coefficients are α/β/γ/δ from Lagrange interpolation on the AIME polynomial identity and sum to 36.
