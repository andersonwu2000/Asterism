# Playbook idiom extraction

A Lean strategy just proved successfully. The framework wants a
one-line summary that future agents working on this same problem can
recognize and reuse. Your job is to distill the key tactical insight.

# Goal that was proved

```
{{GOAL_STATEMENT}}
```

# Original decomposition proposal (PROPOSAL.md excerpt)

```
{{PROPOSAL}}
```

# Proof code that worked

```lean
{{PROOF}}
```

# Your task

Reply with EXACTLY one Markdown bullet in this shape:

```
- **<goal pattern>**: <idiom>
```

- `<goal pattern>` is a short noun phrase describing the kind of goal
  this proved (≤8 words). Examples: `ZMod val of natCast`,
  `Bridge from Nat % to ZMod.val`, `Wilson core via prod factorial`.
- `<idiom>` is the key tactical insight a future agent should know
  (≤2 lines, ≤200 chars). Mention the lemma family / tactic combo
  that broke through. Avoid full proofs — this is for retrieval, not
  re-execution.

Reply with the bullet only — no preamble, no explanation, no header.
If the proof is too trivial to merit a playbook entry (e.g. just
`omega` or `rfl`), reply with the literal text `SKIP` and nothing else.
