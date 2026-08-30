"""`Tooling.experiments.replay_judge` — re-judge a historical proposal in
a rewound scratch workspace (experiment 3, 2026-08-30)."""
from __future__ import annotations

import json

from Tooling.experiments import replay_judge as rj
from Tooling.pipeline.strategist.model import parse_decisions


def test_reconstructed_decisions_parse_with_the_inject_prose_under_proof():
    """The DB keeps an Inject's prose in `brief`; the parser reads it
    from `proof`. A reconstruction that used the column name would hand
    the judge an Inject with no argument — and judge that."""
    rows = [
        {"decision_kind": "ConfirmShelve", "target_id": 9061, "brief": None,
         "reason": "parked", "payload": "{}"},
        {"decision_kind": "Inject", "target_id": None,
         "brief": "### Brick `x`\n\nMint exactly one theorem…", "reason": None,
         "payload": json.dumps({"pipeline": "Formalizer", "step_index": 0, "batch_size": 1})},
    ]
    objs = rj.reconstruct_decisions(rows)
    decisions, err = parse_decisions(json.dumps(objs))
    assert not err and decisions is not None
    shelve, inject = decisions
    assert shelve.kind == "ConfirmShelve" and shelve.target_id == 9061
    assert inject.kind == "Inject" and inject.brief.startswith("### Brick `x`")
    assert inject.payload.get("pipeline") == "Formalizer"
    assert "step_index" not in inject.payload and "batch_size" not in inject.payload, \
        "framework-stamped batch bookkeeping is not author input"
