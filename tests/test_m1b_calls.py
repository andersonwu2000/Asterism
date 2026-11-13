"""Acceptance check: every authenticated request on the remote face (ChatGPT connector) is written down.

Why: twice in one day an agent reported that a tool "failed" and the server's log could not say whether the call
had arrived at all. One line per JSON-RPC request answers that. Names only: never arguments, texts or tokens.

    python -m pytest tests/test_m1b_calls.py -x -q
"""
import json

from test_m1b import SLUG, connector_token, remote_tool, rpc, w  # noqa: F401  (w is the shared world fixture)


def calls(srv) -> list[dict]:
    lines = (srv.data / "log.jsonl").read_text(encoding="utf-8").splitlines()
    return [e for e in map(json.loads, filter(str.strip, lines)) if e.get("event") == "mcp_call"]


def test_requests_on_the_remote_face_are_written_down(w):
    token = connector_token(w.srv, w.alice)
    n = len(calls(w.srv))
    assert rpc(w.srv, "tools/list", token=token, session="conv-log").status_code == 200
    who, bad = remote_tool(w.srv, "whoami", token, "conv-log")
    assert not bad
    msg, bad = remote_tool(w.srv, "register", token, "conv-log", name="alice")      # a person's name: refused
    assert bad
    assert not remote_tool(w.srv, "register", token, "conv-log", name="dot-log")[1]
    assert not remote_tool(w.srv, "whoami", token, "conv-log")[1]
    r = rpc(w.srv, "tools/call", {"name": "inbox-of-the-old-server", "arguments": {"secret-argument": "zebra-9917"}},
            token, "conv-log")
    assert "error" in r.json()
    r = rpc(w.srv, "tools/call", {"name": "x" * 300 + "\n{\"event\":\"forged\"}", "arguments": {}}, token, "conv-log")
    assert "error" in r.json()

    new = calls(w.srv)[n:]
    assert [(c["method"], c.get("tool"), c["outcome"]) for c in new[:6]] == [
        ("tools/list", None, "ok"),
        ("tools/call", "whoami", "ok"),
        ("tools/call", "register", "refused"),
        ("tools/call", "register", "ok"),
        ("tools/call", "whoami", "ok"),
        ("tools/call", "inbox-of-the-old-server", "unknown_tool"),
    ], new
    assert all(c["project"] == SLUG and isinstance(c["person"], int) for c in new), "the person's id, as other lines have it"
    assert len({c["person"] for c in new}) == 1
    assert new[1]["agent"] is None and new[4]["agent"] == "dot-log", "the agent the conversation is registered as, if any"
    assert new[6]["outcome"] == "unknown_tool" and len(new[6]["tool"]) <= 40 and "\n" not in new[6]["tool"]
    log = (w.srv.data / "log.jsonl").read_text(encoding="utf-8")
    assert "zebra-9917" not in log and token not in log and "forged" not in log
