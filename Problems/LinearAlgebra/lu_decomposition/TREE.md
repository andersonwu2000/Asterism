# LinearAlgebra.lu_decomposition — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
└─ via s11322  (succeeded)
   ├─ lu_base  (proved)
   └─ lu_step  (proved)
      └─ via s11323  (succeeded)
         ├─ lu_step_assembly  (proved, attempts=2)
         │  └─ via s11333  (dead)
         └─ schur_complement_minors  (proved)
            └─ via s11324  (succeeded)
               ├─ a11_ne_zero  (proved)
               └─ schur_minor_factor  (proved)
                  └─ via s11326  (succeeded)
                     └─ schur_det_one_succ  (proved)
                        └─ via s11329  (succeeded)
```

**Counters:** 8 proved
