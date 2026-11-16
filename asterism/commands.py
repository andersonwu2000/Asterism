"""Commands to agents (1x): a person's message `@<agent> /<command> <arguments>` to one of their own agents.

The message is posted as any other (everyone who reads the place sees it), but the agent it names is not handed it as
a message: its program is, as a delivery of kind `command` on the computer's connection (computers.poll), and the
program answers with the outcome (`POST /{slug}/api/computer/command`). The server tells the outcome as a reply from
the system to the command, for people only: no agent is handed it, nor counts it as unread. Its text is the page
catalogue's (i18n `msg.cmd.*`): stored in English, drawn by the page in the reader's language from `outcome`.

Only the agent's own person commands it; an agent's message is never a command. A command that no program can take
(the agent is offline or not served by its computer's connection) is answered at once (`offline`); one whose program
never answered (older than 0.1.9) is answered by the background task (`no_answer`).
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from . import config, i18n, presence, projects, util
from .errors import ApiError, bad_request, not_found

COMMANDS = ("goal", "compact", "model")
COMMAND_RE = re.compile(r"@([A-Za-z0-9._-]+) /([A-Za-z]+)(?:\s+(.*))?", re.S)
MODEL_RE = re.compile(r"[A-Za-z0-9._:/-]{1,64}")
RESULTS = ("done", "failed", "unsupported")          # what a program answers
DETAIL_MAX = 300


@dataclass(frozen=True)
class Command:
    agent: sqlite3.Row
    command: str
    args: str


def parse(pj: Any, sender: Any, text: str) -> Command | None:
    """The command a person's message gives, or None for an ordinary message: the text is `@<agent> /<command>`, then
    its arguments, and nothing before. Another person's agent: refused (403); a known command with arguments it does
    not take: refused (400). A name that is not an agent, or a command that is not one of COMMANDS: an ordinary
    message."""
    m = COMMAND_RE.fullmatch(text)
    if m is None or m.group(2) not in COMMANDS:
        return None
    a = pj.db.execute("SELECT * FROM agents WHERE name = ?", (m.group(1),)).fetchone()
    if a is None:
        return None
    if sender.kind != "person":
        return None
    if a["person_id"] != sender.person_id:
        owner = projects.person_name(pj, a["person_id"])
        raise ApiError(403, "not_your_agent", f"Only {owner} can give commands to {a['name']}.")
    command, args = m.group(2), (m.group(3) or "").strip()
    if (command == "compact" and args) or (command == "goal" and not args) \
            or (command == "model" and not MODEL_RE.fullmatch(args)):
        raise bad_request("bad_command", "The commands are /goal <condition>, /goal clear, /compact and "
                                         "/model <name>.")
    return Command(a, command, args)


def label(command: str, args: str) -> str:
    """How an outcome names the command: /compact, /model <name>, /goal clear, /goal (a condition is not repeated)."""
    if command == "model" or (command == "goal" and args == "clear"):
        return f"/{command} {args}"
    return f"/{command}"


def record(pj: Any, mid: int, c: Command, t: float) -> bool:
    """Write the command of message `mid` and, when the agent's program can take it now (the agent is online through
    its computer's connection), its delivery (inside the caller's transaction). Returns whether it was delivered."""
    a = c.agent
    reachable = presence.is_online(pj.slug, a, pj.db) and presence.via_computer(pj.slug, a, pj.db)
    did = None
    if reachable:
        did = pj.db.execute("INSERT INTO deliveries (agent_id, kind, message_id, state, how, created) "
                            "VALUES (?, 'command', ?, 'pending', 'push', ?)", (a["id"], mid, t)).lastrowid
    pj.db.execute("INSERT INTO commands (message_id, agent_id, command, args, delivery_id) VALUES (?, ?, ?, ?, ?)",
                  (mid, a["id"], c.command, c.args, did))
    util.log("command_sent", project=pj.slug, id=mid, agent=a["name"], command=c.command, delivered=reachable)
    return reachable


def delivery_fields(pj: Any, d: sqlite3.Row) -> dict[str, Any]:
    """What a delivery of kind command carries for the program besides the message: the command and its arguments."""
    r = pj.db.execute("SELECT command, args FROM commands WHERE message_id = ?", (d["message_id"],)).fetchone()
    return {"command": r["command"], "args": r["args"]} if r else {"command": "", "args": ""}


def tell(pj: Any, mid: int, result: str, detail: str | None) -> None:
    """Keep the outcome of the command of message `mid` and tell it as a reply from the system, in the command's place:
    every person who may read the place gets it at level normal; no agent gets a level, a delivery or an unread count."""
    from . import messaging             # messaging builds on this module
    cmd = pj.db.execute("SELECT * FROM commands WHERE message_id = ?", (mid,)).fetchone()
    msg = pj.db.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
    if cmd is None or msg is None or cmd["result"] is not None:
        return
    a = pj.db.execute("SELECT name FROM agents WHERE id = ?", (cmd["agent_id"],)).fetchone()
    t = util.now()
    text = text_of(i18n.Translator("en"), a["name"] if a else "?", cmd["command"], cmd["args"], result, detail)
    place = msg["place"]
    if place.startswith("#"):
        people = [messaging.Member("person", r["person_id"], r["person_id"], r["name"])
                  for r in pj.db.execute("SELECT * FROM people ORDER BY person_id")]
        readers = [p for p in people if place[1:] in messaging.channel_names(pj, p)]
    else:
        readers = [p for p in (messaging._member_by_key(pj, k) for k in place[2:].split("|"))
                   if p is not None and p.kind == "person"]
    with pj.db:
        rid = pj.db.execute("INSERT INTO messages (place, sender_kind, sender_id, sender_person, sender_name, text, "
                            "reply_to, hop, mentions, sent) VALUES (?, 'system', NULL, NULL, 'system', ?, ?, 0, '[]', ?)",
                            (place, text, mid, t)).lastrowid
        pj.db.executemany("INSERT INTO levels (message_id, reader_kind, reader_id, level) VALUES (?, 'person', ?, 'normal')",
                          [(rid, p.id) for p in readers])
        pj.db.execute("UPDATE commands SET result = ?, detail = ?, answered = ?, reply_id = ? WHERE message_id = ?",
                      (result, detail, t, rid, mid))
    util.log("command_answered", project=pj.slug, id=mid, result=result)


def text_of(tr: i18n.Translator, agent: str, command: str, args: str, result: str, detail: str | None) -> str:
    key = f"msg.cmd.{result}" + ("_why" if detail and tr.has(f"msg.cmd.{result}_why") else "")
    return tr(key, agent=agent, command=label(command, args), detail=detail or "")


def outcomes(pj: Any, ids: list[int]) -> dict[int, dict[str, Any]]:
    """For the system's replies among the messages `ids`: the outcome of the command each tells, for the page to say
    it in the reader's language (people only)."""
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    out = {}
    for r in pj.db.execute(f"SELECT c.*, a.name AS agent FROM commands c LEFT JOIN agents a ON a.id = c.agent_id "
                           f"WHERE c.reply_id IN ({marks})", ids):
        o = {"agent": r["agent"] or "?", "command": label(r["command"], r["args"]), "result": r["result"]}
        if r["detail"]:
            o["detail"] = r["detail"]
        out[r["reply_id"]] = o
    return out


def answer(pj: Any, cred_id: int, delivery: Any, result: Any, detail: Any) -> dict[str, Any]:
    """The program's answer to a command it was handed: done, failed or unsupported, with an optional line. It counts
    as handing the delivery over. Answering again with the same outcome changes nothing; with another, it is refused."""
    if isinstance(delivery, bool) or not isinstance(delivery, int):
        raise bad_request("bad_request", "delivery must be the id of the command's delivery.")
    if result not in RESULTS:
        raise bad_request("bad_request", "result must be one of: " + ", ".join(RESULTS))
    if detail is not None and not isinstance(detail, str):
        raise bad_request("bad_request", "detail must be one line of text.")
    detail = " ".join(detail.split())[:DETAIL_MAX] or None if detail else None
    d = pj.db.execute("SELECT d.* FROM deliveries d JOIN agents a ON a.id = d.agent_id WHERE d.id = ? "
                      "AND d.kind = 'command' AND a.credential_id = ?", (delivery, cred_id)).fetchone()
    if d is None:
        raise not_found(f"There is no command delivery {delivery} for this computer.")
    cmd = pj.db.execute("SELECT * FROM commands WHERE message_id = ?", (d["message_id"],)).fetchone()
    if cmd is not None and cmd["result"] is not None:
        if (cmd["result"], cmd["detail"]) != (result, detail):
            raise ApiError(409, "conflict", f"The command was answered already ({cmd['result']}).")
        return {}
    with pj.db:
        pj.db.execute("UPDATE deliveries SET state = 'done', done = ? WHERE id = ?", (util.now(), d["id"]))
    tell(pj, d["message_id"], result, detail)
    return {}


def sweep(pj: Any, t: float) -> None:
    """Commands nobody will answer: one handed out twice and not answered a redelivery period later (a program older
    than 0.1.9 does not know them), `no_answer`; one never handed out while its agent can no longer be reached through
    its computer's connection, `offline`. Neither stays waiting."""
    s = config.get()
    late = pj.db.execute("SELECT * FROM deliveries WHERE kind = 'command' AND state = 'out' AND attempts >= 2 "
                         "AND handed_out <= ?", (t - s.redeliver_after_s,)).fetchall()
    stuck = []
    for d in pj.db.execute("SELECT * FROM deliveries WHERE kind = 'command' AND state = 'pending'").fetchall():
        a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (d["agent_id"],)).fetchone()
        if a is None or not (presence.is_online(pj.slug, a, pj.db) and presence.via_computer(pj.slug, a, pj.db)):
            stuck.append(d)
    for d, result in [(d, "no_answer") for d in late] + [(d, "offline") for d in stuck]:
        with pj.db:
            pj.db.execute("UPDATE deliveries SET state = 'dropped', done = ? WHERE id = ?", (t, d["id"]))
        tell(pj, d["message_id"], result, None)


def next_due(pj: Any) -> list[float]:
    s = config.get()
    return [r[0] + s.redeliver_after_s for r in pj.db.execute(
        "SELECT handed_out FROM deliveries WHERE kind = 'command' AND state = 'out' AND attempts >= 2")]
