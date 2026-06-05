# LinearAlgebra.sylvester_criterion — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
└─ via s11602  (succeeded)
   ├─ minors_pos_of_posdef  (proved)
   └─ posdef_of_minors_pos  (proved)
      └─ via s11603  (succeeded)
         ├─ posdef_empty  (proved)
         └─ posdef_succ_step  (proved, attempts=1)
            └─ via s11604  (succeeded)
               ├─ posdef_of_possemidef_det_ne_zero_2  (proved)
               ├─ posdef_succ_det_ne_zero  (proved)
               └─ posdef_succ_possemidef  (proved)
                  └─ via s11605  (succeeded)
                     ├─ block_conjtranspose  (proved)
                     ├─ leading_block_posdef  (proved)
                     │  └─ via s11607  (succeeded)
                     │     ├─ block_hermitian  (proved)
                     │     └─ block_minors_pos  (proved)
                     │        └─ via s11608  (succeeded)
                     └─ schur_complement_possemidef  (proved)
                        └─ via s11606  (succeeded)
                           ├─ possemidef_of_det_pos_fin_one  (proved)
                           └─ schur_det_pos  (proved, attempts=1)
                              ├─ via s11609  (dead — sub-goal shelved)
                              │  ├─ mdet_pos  (shelved)
                              │  └─ schur_det_factor  (dead, attempts=1)
                              │     └─ via s11610  (dead)
                              └─ via s11611  (succeeded)
                                 ├─ mdet_pos_2  (proved)
                                 └─ schur_det_factor_2  (proved)
                                    └─ via s11612  (succeeded)
                                       └─ block_conjtranspose_factor  (proved)
```

## Forward

```
posdef_of_possemidef_det_ne_zero  (proved)
└─ via s11601  (succeeded)
```

**Counters:** 19 proved / 1 shelved
