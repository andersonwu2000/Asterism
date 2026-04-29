"""Strategist subsystem (P7 C49).

Modules:
  - inventory: SQL aggregation feeding the Strategist agent prompt
                (impl §6.4 per-Goal / per-subtree / top-N).
  - demux:      C50 (decision -> queue/UPDATE).
  - round_robin: C51 (multi-Problem rotation).
"""
