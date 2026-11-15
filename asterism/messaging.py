"""Messages: places, sending, the level of each message for each reader, delivery records, reading and unread.

A place is a channel ('#name') or a private conversation between two members. Every message gets, when it is
sent, one row per reader with its level for that reader; nothing recomputes it later. An agent that should
hear a message (level important or normal) gets a delivery record; a poll (its session's or its computer's)
hands deliveries out and they are acknowledged. An important message handed over to an agent starts a follow-up that the background
task (upkeep) turns into reminders until the agent answers it. The system posts notices in #general when an
agent goes online or offline, and messages when somebody else changes an agent's task (tasks.py). A schedule's
run (schedules.py) goes through the same path as a person's message, with its own level for every reader.
Everything lives in the project's database; memory only holds what wakes a
waiting request (an open poll or wait).
"""
from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from . import config, presence, projects, util
from .errors import ApiError, bad_request, conflict, forbidden, not_found
from .projects import Actor, Project

CHANNEL_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
MENTION_RE = re.compile(r"(?<![A-Za-z0-9._-])@([A-Za-z0-9._-]+)")
TEXT_MAX = 4_000
LIST_DEFAULT, LIST_MAX = 50, 200
WAIT_MAX_S = 100.0
CHAIN_REMINDER = ("This thread of replies between agents is already {n} messages long. If another reply is really "
                  "needed, send it again; otherwise leave it here.")
LEVELS = ("important", "normal", "muted")
REMINDER = "You have not answered message {id} from {sender}. Answer with send, reply_to={id}."
NOTICE = {True: "{name} is online.", False: "{name} is offline."}
NO_ANSWER = "(Asterism message. No answer needed.)"
# The last line of a notice that reaches an agent at level normal: it may move the work around.
RECOORDINATE = ("(Asterism notice. No answer needed. If this changes who should do which task, settle it with the agents "
                "you work with and update the task table.)")
# The last line of the last message handed over to an agent that is back, when more is unread than it was handed.
MISSED = "(While you were offline other messages arrived: {n} unread. messages with all=true reads them in one call.)"


# --------------------------------------------------------------------------- members and places

@dataclass(frozen=True)
class Member:
    kind: str                 # person, agent
    id: int                   # person id or agent id
    person_id: int            # the person behind it (itself for a person)
    name: str

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.id}"


def person_member(pj: Project, person_id: int) -> Member:
    return Member("person", person_id, person_id, projects.person_name(pj, person_id))


def agent_member(a: sqlite3.Row) -> Member:
    return Member("agent", a["id"], a["person_id"], a["name"])


def _member_by_key(pj: Project, key: str) -> Member | None:
    kind, _, raw = key.partition(":")
    if kind == "person":
        r = pj.db.execute("SELECT * FROM people WHERE person_id = ?", (int(raw),)).fetchone()
        return Member("person", r["person_id"], r["person_id"], r["name"]) if r else None
    a = pj.db.execute("SELECT * FROM agents WHERE id = ?", (int(raw),)).fetchone()
    return agent_member(a) if a else None


def member_by_name(pj: Project, name: str) -> Member | None:
    r = pj.db.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone()
    if r:
        return Member("person", r["person_id"], r["person_id"], r["name"])
    a = pj.db.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
    return agent_member(a) if a else None


def private_place(a: Member, b: Member) -> str:
    return "p:" + "|".join(sorted((a.key, b.key)))


def _private_keys(place: str) -> list[str]:
    return place[2:].split("|")


def _other_key(place: str, me: Member) -> str | None:
    """The other member of a private place `me` is part of; None if `me` is not part of it."""
    keys = _private_keys(place)
    if me.key not in keys:
        return None
    rest = [k for k in keys if k != me.key]
    return rest[0] if rest else me.key


def may_talk_privately(a: Member, b: Member) -> bool:
    """Two people; a person and an agent of theirs; two agents of the same person."""
    if a.kind == "person" and b.kind == "person":
        return True
    return a.person_id == b.person_id


def _private_refusal(pj: Project, me: Member, other: Member) -> str:
    if me.kind == "agent" and other.kind == "person":
        return (f"An agent writes privately only to its own person and that person's agents; {other.name} is not "
                f"yours. Mention @{other.name} in a channel instead.")
    return (f"{other.name} is an agent of {projects.person_name(pj, other.person_id)}; only that person and their "
            f"agents write to it privately. Mention @{other.name} in a channel instead.")


def channel_names(pj: Project) -> list[str]:
    return [r["name"] for r in pj.db.execute("SELECT name FROM channels ORDER BY id")]


def _no_channel(pj: Project, place: str) -> ApiError:
    return not_found(f"There is no channel '{place}'. The channels are: "
                     + ", ".join("#" + n for n in channel_names(pj)) + ".")


def resolve_place(pj: Project, me: Member, where: Any) -> tuple[str, Member | None]:
    """The place `where` names for `me`: '#name' is a channel, anything else a member for a private
    conversation. Returns (place key, the other member or None)."""
    if not isinstance(where, str) or not where:
        raise bad_request("bad_request", "Name the place: a channel as #name, or a member's name for a private conversation.")
    if where.startswith("#"):
        if not pj.db.execute("SELECT 1 FROM channels WHERE name = ?", (where[1:],)).fetchone():
            raise _no_channel(pj, where)
        return where, None
    other = member_by_name(pj, where)
    if other is None:
        if projects.group_by_name(pj, where):
            raise not_found(f"'{where}' is a group, not a member. Mention @{where} in a channel instead.")
        raise not_found(f"There is no member '{where}'. Channels are written #name.")
    if other == me:
        raise bad_request("bad_request", "That is you. Write in a channel, or to another member.")
    if not may_talk_privately(me, other):
        raise forbidden(_private_refusal(pj, me, other))
    return private_place(me, other), other


def _visible(row: sqlite3.Row | None, me: Member) -> bool:
    return bool(row) and (row["place"].startswith("#") or _other_key(row["place"], me) is not None)


def _message(pj: Project, me: Member, mid: Any, what: str) -> sqlite3.Row:
    row = pj.db.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
    if not _visible(row, me):
        raise not_found(f"There is no message {mid} you can read{what}.")
    return row


def _int(v: Any, name: str, required: bool = False) -> int | None:
    """An integer from JSON or a query string."""
    if v is None or v == "":
        if required:
            raise bad_request("bad_request", f"{name} is required.")
        return None
    if isinstance(v, bool):
        raise bad_request("bad_request", f"{name} must be a whole number.")
    if isinstance(v, int):
        return v
    if isinstance(v, str) and re.fullmatch(r"-?\d{1,18}", v.strip()):
        return int(v)
    raise bad_request("bad_request", f"{name} must be a whole number.")


def _limit(v: Any) -> int:
    n = _int(v, "limit")
    return LIST_DEFAULT if n is None else max(1, min(n, LIST_MAX))


# --------------------------------------------------------------------------- what a reader sees

def relation(me: Member, row: sqlite3.Row) -> str:
    if row["sender_kind"] == "system":
        return "system"
    own = row["sender_person"] == me.person_id
    if row["sender_kind"] == "person":
        return "your own user" if own else "another collaborator"
    return "agent of your own user" if own else "agent of another collaborator"


def _place_for(pj: Project, place: str, me: Member, names: dict[str, str]) -> str:
    if place.startswith("#"):
        return place
    other = _other_key(place, me) or ""
    if other not in names:
        m = _member_by_key(pj, other)
        names[other] = m.name if m else "a former member"
    return names[other]


def views(pj: Project, rows: Iterable[sqlite3.Row], me: Member) -> list[dict[str, Any]]:
    """Message objects as `me` gets them."""
    rows = list(rows)
    if not rows:
        return []
    marks = ",".join("?" * len(rows))
    levels = {r["message_id"]: r["level"] for r in pj.db.execute(
        f"SELECT message_id, level FROM levels WHERE reader_kind = ? AND reader_id = ? AND message_id IN ({marks})",
        (me.kind, me.id, *[r["id"] for r in rows]))}
    names: dict[str, str] = {}
    out = []
    for r in rows:
        own = r["sender_kind"] == me.kind and r["sender_id"] == me.id
        # Members who joined after a message was sent have no level for it.
        level = levels.get(r["id"]) or ("normal" if own or me.kind == "person" else "muted")
        m: dict[str, Any] = {"id": r["id"], "in": _place_for(pj, r["place"], me, names), "from": r["sender_name"],
                             "from_kind": r["sender_kind"], "relation": relation(me, r), "level": level,
                             "reply_to": r["reply_to"], "text": r["text"], "sent_at": util.iso(r["sent"]),
                             "mentions": json.loads(r["mentions"])}
        if not r["place"].startswith("#"):
            m["private"] = True
        if r["schedule_id"] is not None:
            m["scheduled"] = True
        out.append(m)
    return out


def _attr(v: Any) -> str:
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


_CLOSER_RE = re.compile(r"<(?=/asterism-message)", re.IGNORECASE)


def frame(m: dict[str, Any], notice: bool = False) -> str:
    """The full text put in front of an agent for the message object `m`. A notice never asks for an answer; one
    at level normal asks the agent to settle the tasks again if they need it."""
    place = "private" if m.get("private") else m["in"]
    reply = f' reply-to="{_attr(m["reply_to"])}"' if m.get("reply_to") else ""
    if notice:
        last = RECOORDINATE if m["level"] == "normal" else NO_ANSWER
    else:
        last = f"(Asterism message. To answer: send with reply_to={m['id']}.)" if m["level"] == "important" else NO_ANSWER
    return (f'<asterism-message id="{m["id"]}" in="{_attr(place)}" from="{_attr(m["from"])}" '
            f'relation="{_attr(m["relation"])}" level="{_attr(m["level"])}"{reply}>\n'
            f'{_CLOSER_RE.sub("&lt;", m["text"])}\n</asterism-message>\n{last}')


# --------------------------------------------------------------------------- mentions

def _lookup_mention(pj: Project, name: str) -> tuple[str, Any] | None:
    m = member_by_name(pj, name)
    if m:
        return "member", m
    g = projects.group_by_name(pj, name)
    return ("group", g) if g else None


def parse_mentions(pj: Project, text: str) -> tuple[list[tuple[str, str, Any]], list[str]]:
    """([(name, 'member' | 'group', Member | group row)], [unknown names]), each name once, in order."""
    found: list[tuple[str, str, Any]] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for match in MENTION_RE.finditer(text):
        cand = match.group(1)
        hit = _lookup_mention(pj, cand)
        while hit is None and cand and cand[-1] in "._-":
            cand = cand[:-1]
            hit = _lookup_mention(pj, cand) if cand else None
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if hit:
            found.append((cand, hit[0], hit[1]))
        else:
            unknown.append(cand)
    return found, unknown


def _group_member_keys(pj: Project, group_ids: Iterable[int]) -> set[str]:
    ids = list(group_ids)
    if not ids:
        return set()
    marks = ",".join("?" * len(ids))
    return {f"{r['member_kind']}:{r['member_id']}" for r in pj.db.execute(
        f"SELECT member_kind, member_id FROM group_members WHERE group_id IN ({marks})", ids)}


def _asked(pj: Project, orig: sqlite3.Row, who: Member) -> bool:
    """Whether the message `orig` mentioned `who`, by name or through a group `who` is in."""
    names = json.loads(orig["mentions"])
    if who.name in names:
        return True
    groups = [g["id"] for g in projects.groups_of(pj, who.kind, who.id) if g["name"] in names]
    return bool(groups)


# --------------------------------------------------------------------------- sending

def check_text(text: Any) -> str:
    if not isinstance(text, str) or not text:
        raise bad_request("bad_request", "text must be the message: 1 to 4,000 characters.")
    if len(text) > TEXT_MAX:
        raise bad_request("too_long", f"The text is {len(text):,} characters; the most is 4,000. "
                                      f"Split it into several messages, or put it in a file in the repository.")
    return text


def send(pj: Project, sender: Member, to: Any, text: Any, reply_to: Any) -> dict[str, Any]:
    """Post a message. An agent's reply at hop 3, 5, 7... is held back once with the reply-chain reminder."""
    actor = Actor(sender.person_id, sender.id if sender.kind == "agent" else None)
    projects.require(pj, actor, "post", "Posting messages needs the post permission.")
    text = check_text(text)
    rid = _int(reply_to, "reply_to")
    orig = _message(pj, sender, rid, " to reply to") if rid is not None else None
    if to is None or to == "":
        if orig is None:
            raise bad_request("bad_request", "Say where: give `to` (a #channel or a member's name), or reply_to "
                                             "with the id of the message you are answering.")
        place = orig["place"]
        if not place.startswith("#"):
            other = _member_by_key(pj, _other_key(place, sender) or "")
            if other is None:
                raise not_found("The other member of that private conversation is no longer here.")
            if not may_talk_privately(sender, other):
                raise forbidden(_private_refusal(pj, sender, other))
    else:
        place, _ = resolve_place(pj, sender, to)
        if orig is not None and orig["place"] != place:
            raise bad_request("bad_request", f"Message {rid} is in another place. Leave out `to` to answer it "
                                             f"where it is.")
    hop = orig["hop"] + 1 if sender.kind == "agent" and orig is not None else 0
    if sender.kind == "agent" and hop >= 3 and hop % 2 == 1:
        with pj.db:
            first = pj.db.execute("INSERT OR IGNORE INTO chain_reminders (agent_id, reply_to) VALUES (?, ?)",
                                  (sender.id, rid)).rowcount
        if first:
            util.log("reply_chain_reminded", project=pj.slug, agent=sender.name, reply_to=rid, hop=hop)
            raise ApiError(409, "reply_chain", CHAIN_REMINDER.format(n=hop))
    found, unknown = parse_mentions(pj, text) if place.startswith("#") else ([], [])
    mid, results = _post(pj, sender, place, text, orig, hop, found)
    return {"id": mid, "hop": hop, "mentions": results + [{"name": n, "result": "unknown"} for n in unknown]}


def post_scheduled(pj: Project, sender: Member, place: str, text: str, level: str, schedule_id: int,
                   then: Callable[[int], None]) -> int:
    """A run of a schedule: a message from its creator (hop 0) whose text is not searched for mentions; every
    reader's level comes from the schedule's `level` (_distribute). `then(message id)` runs inside the same
    transaction (the schedule's own bookkeeping)."""
    return _post(pj, sender, place, text, None, 0, [], (level, schedule_id), then)[0]


def _post(pj: Project, sender: Member, place: str, text: str, orig: sqlite3.Row | None, hop: int,
          found: list[tuple[str, str, Any]], scheduled: tuple[str, int] | None = None,
          then: Callable[[int], None] | None = None) -> tuple[int, list[dict[str, Any]]]:
    """Write a message checked by the caller, each reader's level and the deliveries; wake the agents."""
    rid = orig["id"] if orig is not None else None
    t = util.now()
    with pj.db:
        mid = pj.db.execute("INSERT INTO messages (place, sender_kind, sender_id, sender_person, sender_name, text, "
                            "reply_to, hop, mentions, sent, schedule_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (place, sender.kind, sender.id, sender.person_id, sender.name, text, rid, hop,
                             json.dumps([n for n, _, _ in found]), t,
                             scheduled[1] if scheduled else None)).lastrowid
        results, woken = _distribute(pj, mid, place, sender, found, orig, t, scheduled[0] if scheduled else None)
        if scheduled:
            _unstack(pj, scheduled[1], mid, t)
        if sender.kind == "agent" and rid is not None:      # an answer ends the follow-up of what it answers
            pj.db.execute("UPDATE followups SET answered = ?, due = NULL WHERE agent_id = ? AND message_id = ? "
                          "AND answered IS NULL", (t, sender.id, rid))
        if then is not None:
            then(mid)
    util.log("message_sent", project=pj.slug, id=mid, **_log_place(pj, place, sender), hop=hop)
    for aid in woken:
        notify(pj.slug, aid)
    return mid, results


def _unstack(pj: Project, schedule_id: int, mid: int, t: float) -> None:
    """One schedule never stacks answers owed (inside the caller's transaction). For each agent the new message
    `mid` is important for, an earlier message of the same schedule that was important for it and that it has
    not answered becomes muted for it and counts as handed over (`seen`: it is no longer unread); its waiting
    delivery is dropped, and its follow-up (and a reminder about it not handed over yet) moves to the new
    message with its clock as it stands."""
    agents = [r[0] for r in pj.db.execute("SELECT reader_id FROM levels WHERE message_id = ? AND reader_kind = 'agent' "
                                          "AND level = 'important'", (mid,))]
    for aid in agents:
        earlier = [r[0] for r in pj.db.execute(
            "SELECT m.id FROM messages m JOIN levels l ON l.message_id = m.id AND l.reader_kind = 'agent' "
            "AND l.reader_id = ? WHERE m.schedule_id = ? AND m.id < ? AND l.level = 'important' "
            "AND NOT EXISTS (SELECT 1 FROM messages r WHERE r.sender_kind = 'agent' AND r.sender_id = ? "
            "AND r.reply_to = m.id) ORDER BY m.id", (aid, schedule_id, mid, aid))]
        for e in earlier:
            pj.db.execute("UPDATE levels SET level = 'muted', seen = coalesce(seen, ?) WHERE message_id = ? "
                          "AND reader_kind = 'agent' AND reader_id = ?", (t, e, aid))
            pj.db.execute("UPDATE deliveries SET state = 'dropped', done = ? WHERE agent_id = ? AND message_id = ? "
                          "AND kind = 'message' AND state IN ('pending', 'out')", (t, aid, e))
            pj.db.execute("UPDATE deliveries SET message_id = ? WHERE agent_id = ? AND message_id = ? "
                          "AND kind = 'reminder' AND state = 'pending'", (mid, aid, e))
            # The oldest clock wins if, against the rule, more than one was running.
            pj.db.execute("UPDATE OR IGNORE followups SET message_id = ? WHERE agent_id = ? AND message_id = ? "
                          "AND answered IS NULL", (mid, aid, e))
            pj.db.execute("DELETE FROM followups WHERE agent_id = ? AND message_id = ? AND answered IS NULL", (aid, e))


def _log_place(pj: Project, place: str, sender: Member) -> dict[str, Any]:
    if place.startswith("#"):
        return {"in": place, "from": sender.name}
    other = _member_by_key(pj, _other_key(place, sender) or "")
    return {"in": "private", "to": other.name if other else None, "from": sender.name}


def _distribute(pj: Project, mid: int, place: str, sender: Member, found: list[tuple[str, str, Any]],
                orig: sqlite3.Row | None, t: float, fixed: str | None = None) -> tuple[list[dict[str, Any]], list[int]]:
    """Write each reader's level and the agents' deliveries (inside the caller's transaction). Returns the
    answer's mention results and the agents to wake. `fixed`: the level of a schedule's run, which takes the
    place of mentions and of what the agent is doing (_scheduled_level)."""
    s = config.get()
    channel = place.startswith("#")
    if channel:
        readers = [Member("person", r["person_id"], r["person_id"], r["name"])
                   for r in pj.db.execute("SELECT * FROM people ORDER BY person_id")]
        agent_rows = {a["id"]: a for a in pj.db.execute("SELECT * FROM agents ORDER BY id")}
        readers += [agent_member(a) for a in agent_rows.values()]
        readers = [r for r in readers if r != sender]
    else:
        other = _member_by_key(pj, _other_key(place, sender) or "")
        readers = [other] if other else []
        agent_rows = {other.id: pj.db.execute("SELECT * FROM agents WHERE id = ?", (other.id,)).fetchone()} \
            if other and other.kind == "agent" else {}
    direct = {m.key for _, kind, m in found if kind == "member"}
    via_group = _group_member_keys(pj, [g["id"] for _, kind, g in found if kind == "group"])
    muted = {f"{r['member_kind']}:{r['member_id']}" for r in pj.db.execute(
        "SELECT member_kind, member_id FROM mutes WHERE channel = ?", (place[1:],))} if channel else set()
    recent = {r["sender_id"] for r in pj.db.execute(
        "SELECT DISTINCT sender_id FROM messages WHERE sender_kind = 'agent' AND place = ? AND sent >= ? AND id != ?",
        (place, t - s.recent_speaker_s, mid))} if channel else set()
    asker = orig["sender_id"] if orig is not None and orig["sender_kind"] == "agent" and _asked(pj, orig, sender) else None
    switches: dict[int, sqlite3.Row] = {}
    online: dict[int, bool] = {}
    levels: dict[str, str] = {}
    woken: list[int] = []
    for r in readers:
        mentioned = r.key in direct or r.key in via_group
        if r.kind == "person":
            if fixed is not None:
                level = _scheduled_level(fixed, r.key in muted, True, False, False)
            else:
                level = ("important" if not channel or mentioned else "muted" if r.key in muted else "normal")
        else:
            a = agent_rows[r.id]
            online[r.id] = presence.is_online(pj.slug, a, pj.db)
            if r.person_id not in switches:
                switches[r.person_id] = projects.ownership_group(pj, r.person_id)
            sw = switches[r.person_id]
            own = sender.kind != "system" and sender.person_id == r.person_id
            heard = channel and not mentioned and r.key not in muted and online[r.id] and r.id in recent \
                and not presence.busy(pj.db, a)
            if fixed is not None:
                level = _scheduled_level(fixed, r.key in muted, own, bool(sw is not None and sw["others_mention"]),
                                         bool(sw is not None and sw["others_channel"]))
            elif own and (mentioned or not channel):
                level = "important"
            elif not own and mentioned and sw is not None and sw["others_mention"]:
                level = "important"
            elif asker == r.id:
                level = "normal"
            elif heard and (own or (sw is not None and sw["others_channel"])):
                level = "normal"
            else:
                level = "muted"
            if level == "important" or (level == "normal" and online[r.id]):
                pj.db.execute("INSERT INTO deliveries (agent_id, kind, message_id, state, how, created) "
                              "VALUES (?, 'message', ?, 'pending', ?, ?)",
                              (r.id, mid, "push" if online[r.id] else "return", t))
                woken.append(r.id)
        levels[r.key] = level
    pj.db.executemany("INSERT INTO levels (message_id, reader_kind, reader_id, level) VALUES (?, ?, ?, ?)",
                      [(mid, r.kind, r.id, levels[r.key]) for r in readers])

    def outcome(key: str) -> str:
        kind, _, raw = key.partition(":")
        if kind == "person":
            return "notified"
        if levels.get(key) != "important":
            return "closed"
        return "woken" if online.get(int(raw)) else "offline"

    results: list[dict[str, Any]] = []
    for name, kind, target in found:
        if kind == "member":
            if target.key in levels:             # the sender mentioning itself gets no entry
                results.append({"name": name, "result": outcome(target.key)})
        else:
            counts = {"woken": 0, "offline": 0, "closed": 0, "notified": 0}
            for key in _group_member_keys(pj, [target["id"]]):
                if key in levels:
                    counts[outcome(key)] += 1
            results.append({"name": name, "group": True, **counts})
    return results, woken


def _scheduled_level(level: str, muted: bool, own: bool, others_mention: bool, others_channel: bool) -> str:
    """A reader's level for a run of a schedule at `level`. A person counts as on the creator's side.
    - important: important for a person and for an agent of the creator's side; another person's agent only
      with its others_mention switch on (as if it had been mentioned);
    - normal: normal for a person and for an agent of the creator's side or with others_channel on, whatever the
      agent is doing; muted where the reader muted the channel;
    - muted: muted."""
    if level == "important":
        return "important" if own or others_mention else "muted"
    if level == "normal":
        return "normal" if not muted and (own or others_channel) else "muted"
    return "muted"


# --------------------------------------------------------------------------- notices

def _close_to(pj: Project, a: sqlite3.Row) -> set[str]:
    """Who hears an agent's notices at level normal: its person, that person's agents, and the members of the
    custom groups the agent is in (the default groups do not count)."""
    keys = {f"person:{a['person_id']}"}
    keys |= {f"agent:{r['id']}" for r in pj.db.execute("SELECT id FROM agents WHERE person_id = ?", (a["person_id"],))}
    keys |= {f"{r['member_kind']}:{r['member_id']}" for r in pj.db.execute(
        "SELECT DISTINCT o.member_kind, o.member_id FROM group_members m JOIN groups g ON g.id = m.group_id "
        "JOIN group_members o ON o.group_id = g.id WHERE g.kind = 'custom' AND m.member_kind = 'agent' "
        "AND m.member_id = ?", (a["id"],))}
    return keys


def _waiting_for(pj: Project, a: sqlite3.Row) -> set[str]:
    """The senders of the important messages (mentions, private messages) to this agent that it has not
    answered: handed over and followed up, or not handed over yet."""
    return {f"{r['sender_kind']}:{r['sender_id']}" for r in pj.db.execute(
        "SELECT DISTINCT m.sender_kind, m.sender_id FROM messages m WHERE m.sender_kind != 'system' AND m.id IN ("
        "SELECT message_id FROM followups WHERE agent_id = ? AND answered IS NULL UNION "
        "SELECT d.message_id FROM deliveries d JOIN levels l ON l.message_id = d.message_id "
        "AND l.reader_kind = 'agent' AND l.reader_id = d.agent_id WHERE d.agent_id = ? AND d.kind = 'message' "
        "AND d.state IN ('pending', 'out') AND l.level = 'important')", (a["id"], a["id"]))}


def post_notice(pj: Project, a: sqlite3.Row, online: bool, text: str, assigners: set[int]) -> int:
    """The notice of a change of the agent's presence, from the system in #general; `text` lists its tasks and
    `assigners` are the people who locked one of them. The changes that may move the work around are an agent
    that is responsible for a task going offline and one that is responsible for none coming online. Levels:
    - important: whoever waits for the agent's answer, and the people in `assigners`, when it goes offline;
    - normal, for a change that may move the work around: those close to it (_close_to) who have not muted
      #general, an agent only while it is busy itself (presence.busy);
    - muted: everyone else, and every other change.
    Agents that are online get it as a delivery of kind notice; the agent itself gets nothing. Hop 0 and no
    mentions: it never counts as speaking."""
    close = _close_to(pj, a)
    waiting = set() if online else _waiting_for(pj, a) | {f"person:{p}" for p in assigners}
    moves = online != presence.busy(pj.db, a)
    muted = {f"{r['member_kind']}:{r['member_id']}" for r in pj.db.execute(
        "SELECT member_kind, member_id FROM mutes WHERE channel = 'general'")}

    def level(r: Member, row: sqlite3.Row | None) -> str:
        if r.key in waiting:
            return "important"
        near = moves and r.key in close and r.key not in muted and (row is None or presence.busy(pj.db, row))
        return "normal" if near else "muted"
    return _post_system(pj, text, level, notice=True, without=a["id"])


def post_from_system(pj: Project, text: str, agents: dict[int, str]) -> int:
    """An ordinary message from the system in #general (hop 0, no mentions) to the agents in `agents` (agent id
    -> level, important or normal); muted for every other reader. It is delivered like any message: an
    important one is kept for an agent that is offline and followed up until it is answered."""
    return _post_system(pj, text, lambda r, row: agents.get(r.id, "muted") if r.kind == "agent" else "muted",
                        notice=False)


def _post_system(pj: Project, text: str, level_of: Any, notice: bool, without: int | None = None) -> int:
    """Write a message from the system in #general with each reader's level, level_of(member, agent row or None),
    and the agents' deliveries: a notice only to agents that are online, a message as _distribute does."""
    t = util.now()
    readers: list[tuple[Member, sqlite3.Row | None]] = [
        (Member("person", r["person_id"], r["person_id"], r["name"]), None)
        for r in pj.db.execute("SELECT * FROM people ORDER BY person_id")]
    readers += [(agent_member(x), x) for x in pj.db.execute("SELECT * FROM agents WHERE id != ? ORDER BY id",
                                                             (-1 if without is None else without,))]
    woken: list[int] = []
    with pj.db:
        mid = pj.db.execute("INSERT INTO messages (place, sender_kind, sender_id, sender_person, sender_name, text, "
                            "reply_to, hop, mentions, sent, notice) VALUES ('#general', 'system', NULL, NULL, 'system', "
                            "?, NULL, 0, '[]', ?, ?)", (text, t, 1 if notice else None)).lastrowid
        levels = []
        for r, row in readers:
            level = level_of(r, row)
            levels.append((mid, r.kind, r.id, level))
            if row is None or level == "muted":
                continue
            online = presence.is_online(pj.slug, row, pj.db)
            if notice and online:
                pj.db.execute("INSERT INTO deliveries (agent_id, kind, message_id, state, how, created) "
                              "VALUES (?, 'notice', ?, 'pending', 'push', ?)", (r.id, mid, t))
                woken.append(r.id)
            elif not notice and (level == "important" or online):
                pj.db.execute("INSERT INTO deliveries (agent_id, kind, message_id, state, how, created) "
                              "VALUES (?, 'message', ?, 'pending', ?, ?)", (r.id, mid, "push" if online else "return", t))
                woken.append(r.id)
        pj.db.executemany("INSERT INTO levels (message_id, reader_kind, reader_id, level) VALUES (?, ?, ?, ?)", levels)
    util.log("message_sent", project=pj.slug, id=mid, **{"in": "#general"}, **{"from": "system"}, hop=0)
    for aid in woken:
        notify(pj.slug, aid)
    return mid


# --------------------------------------------------------------------------- waking waiting requests (memory only)

_news: dict[tuple[str, int], set[asyncio.Event]] = defaultdict(set)
_waits: dict[tuple[str, int], int] = defaultdict(int)


def notify(slug: str, agent_id: int) -> None:
    for ev in list(_news.get((slug, agent_id), ())):
        ev.set()
    presence.kick()                     # a connector agent's deliveries go out from the background task


def listen(slug: str, agent_id: int) -> asyncio.Event:
    ev = asyncio.Event()
    _news[(slug, agent_id)].add(ev)
    return ev


def unlisten(slug: str, agent_id: int, ev: asyncio.Event) -> None:
    s = _news.get((slug, agent_id))
    if s is not None:
        s.discard(ev)
        if not s:
            del _news[(slug, agent_id)]


def waiting(slug: str, agent_id: int) -> bool:
    return _waits.get((slug, agent_id), 0) > 0


def wait_opened(slug: str, agent_id: int) -> None:
    _waits[(slug, agent_id)] += 1


def wait_closed(slug: str, agent_id: int) -> None:
    """The poll may now hand out what it held back."""
    key = (slug, agent_id)
    _waits[key] -= 1
    if _waits[key] <= 0:
        del _waits[key]
    notify(slug, agent_id)


# --------------------------------------------------------------------------- deliveries

def reminder_text(pj: Project, about: int) -> str:
    row = pj.db.execute("SELECT sender_name FROM messages WHERE id = ?", (about,)).fetchone()
    return REMINDER.format(id=about, sender=row["sender_name"] if row else "a former member")


def delivery_view(pj: Project, d: sqlite3.Row, me: Member) -> dict[str, Any]:
    if d["kind"] == "reminder":
        return {"delivery": d["id"], "kind": "reminder", "frame": reminder_text(pj, d["message_id"]),
                "about": d["message_id"]}
    row = pj.db.execute("SELECT * FROM messages WHERE id = ?", (d["message_id"],)).fetchone()
    m = views(pj, [row], me)[0]
    return {"delivery": d["id"], "kind": d["kind"], "message": m, "frame": frame(m, d["kind"] == "notice")}


def hand_out(pj: Project, me: Member) -> list[dict[str, Any]]:
    """What a poll (its session's or its computer's) hands out now: new deliveries, and those handed out once
    and not acknowledged in time (same id). They stay open until acknowledged. One handed out twice is left to
    the background task, which makes the agent offline (`unanswered`). When it holds messages kept while the
    agent was offline (`how` return) and more is unread than it carries, the last of them says how much."""
    t = util.now()
    rows = pj.db.execute("SELECT * FROM deliveries WHERE agent_id = ? AND (state = 'pending' OR "
                         "(state = 'out' AND attempts < 2 AND handed_out <= ?)) ORDER BY id",
                         (me.id, t - config.get().redeliver_after_s)).fetchall()
    if not rows:
        return []
    with pj.db:
        pj.db.executemany("UPDATE deliveries SET state = 'out', handed_out = ?, attempts = attempts + 1 WHERE id = ?",
                          [(t, d["id"]) for d in rows])
    out = [delivery_view(pj, d, me) for d in rows]
    back = [i for i, d in enumerate(rows) if d["kind"] == "message" and d["how"] == "return"]
    if back:
        # What this hand-out carries is handed out now, so it no longer counts as unread.
        n = sum(k for k, _ in _counts(pj, me).values())
        if n:
            out[back[-1]]["frame"] += "\n" + MISSED.format(n=n)
    return out


def next_due(pj: Project, me: Member) -> float | None:
    """When the earliest delivery handed out once and not acknowledged falls due again."""
    r = pj.db.execute("SELECT min(handed_out) FROM deliveries WHERE agent_id = ? AND state = 'out' AND attempts < 2",
                      (me.id,)).fetchone()
    return r[0] + config.get().redeliver_after_s if r and r[0] is not None else None


def drop_unheard(pj: Project, me: Member) -> None:
    """An agent coming back online gets its important messages; normal ones that were waiting stay unread."""
    with pj.db:
        pj.db.execute("UPDATE deliveries SET state = 'dropped', done = ? WHERE agent_id = ? AND kind = 'message' "
                      "AND state IN ('pending', 'out') AND message_id IN (SELECT message_id FROM levels "
                      "WHERE reader_kind = 'agent' AND reader_id = ? AND level = 'normal')",
                      (util.now(), me.id, me.id))


def _follow(pj: Project, me: Member, mids: list[int], t: float) -> None:
    """Important messages (never notices of presence) handed over to an agent and not answered yet start their reminder
    clock (inside the caller's transaction). People are never reminded."""
    if me.kind != "agent" or not mids:
        return
    marks = ",".join("?" * len(mids))
    pj.db.execute(f"INSERT OR IGNORE INTO followups (agent_id, message_id, handed, period, due) "
                  f"SELECT ?, l.message_id, ?, ?, ? FROM levels l JOIN messages m ON m.id = l.message_id "
                  f"WHERE l.reader_kind = 'agent' AND l.reader_id = ? AND l.level = 'important' "
                  f"AND m.notice IS NULL AND l.message_id IN ({marks}) "
                  f"AND NOT EXISTS (SELECT 1 FROM messages r WHERE r.sender_kind = 'agent' AND r.sender_id = ? "
                  f"AND r.reply_to = l.message_id)",
                  (me.id, t, t, t + config.get().remind_after_s, me.id, *mids, me.id))


def finish(pj: Project, me: Member, rows: list[sqlite3.Row], how: str | None) -> None:
    """Mark deliveries handed over; `how` None keeps the one each was created with."""
    if not rows:
        return
    t = util.now()
    with pj.db:
        pj.db.executemany("UPDATE deliveries SET state = 'done', done = ? WHERE id = ?", [(t, d["id"]) for d in rows])
        _follow(pj, me, [d["message_id"] for d in rows if d["kind"] == "message"], t)
    for d in rows:
        if d["kind"] != "reminder":
            util.log("delivered", project=pj.slug, message=d["message_id"], to=me.name, how=how or d["how"])


def ack(pj: Project, me: Member, ids: Any) -> dict[str, Any]:
    if not isinstance(ids, list):
        raise bad_request("bad_request", "deliveries must be a list of delivery ids.")
    ids = [i for i in ids if isinstance(i, int) and not isinstance(i, bool)]
    if ids:
        marks = ",".join("?" * len(ids))
        rows = pj.db.execute(f"SELECT * FROM deliveries WHERE agent_id = ? AND state = 'out' AND id IN ({marks})",
                             (me.id, *ids)).fetchall()
        finish(pj, me, rows, None)
    return {}


def take_for_wait(pj: Project, me: Member) -> list[dict[str, Any]]:
    rows = pj.db.execute("SELECT * FROM deliveries WHERE agent_id = ? AND kind = 'message' AND state IN ('pending', 'out') "
                         "ORDER BY message_id", (me.id,)).fetchall()
    if not rows:
        return []
    finish(pj, me, rows, "wait")
    msgs = pj.db.execute(f"SELECT * FROM messages WHERE id IN ({','.join('?' * len(rows))}) ORDER BY id",
                         [d["message_id"] for d in rows]).fetchall()
    return views(pj, msgs, me)


def _handed_by_reading(pj: Project, me: Member, mids: list[int]) -> None:
    """An agent read these messages in full with `messages` (marked `seen`)."""
    if not mids:
        return
    marks = ",".join("?" * len(mids))
    t = util.now()
    with pj.db:
        pj.db.execute(f"UPDATE levels SET seen = ? WHERE reader_kind = 'agent' AND reader_id = ? AND seen IS NULL "
                      f"AND message_id IN ({marks})", (t, me.id, *mids))
        _follow(pj, me, mids, t)
    rows = pj.db.execute(f"SELECT * FROM deliveries WHERE agent_id = ? AND state IN ('pending', 'out') "
                         f"AND kind != 'reminder' AND message_id IN ({marks})", (me.id, *mids)).fetchall()
    finish(pj, me, rows, "read")


# --------------------------------------------------------------------------- reading and unread

# An agent's message is unread while it is after the read position and was not handed over in full: not `seen`
# (read with `messages`, or a run of a schedule superseded for it), and no delivery of it was handed out (a
# handed-out one is acknowledged or handed out again).
_NOT_HANDED = ("l.seen IS NULL AND NOT EXISTS (SELECT 1 FROM deliveries d WHERE d.agent_id = l.reader_id "
               "AND d.message_id = l.message_id AND d.state IN ('out', 'done'))")


def _unread_rows(pj: Project, me: Member, place: str | None = None, limit: int | None = None,
                 important: bool = False) -> list[sqlite3.Row]:
    sql = ("SELECT m.* FROM levels l JOIN messages m ON m.id = l.message_id "
           "LEFT JOIN reads r ON r.reader_kind = l.reader_kind AND r.reader_id = l.reader_id AND r.place = m.place "
           "WHERE l.reader_kind = ? AND l.reader_id = ? AND l.message_id > coalesce(r.upto, 0)")
    args: list[Any] = [me.kind, me.id]
    if me.kind == "agent":
        sql += " AND " + _NOT_HANDED
    if important:
        sql += " AND l.level = 'important'"
    if place is not None:
        sql += " AND m.place = ?"
        args.append(place)
    sql += " ORDER BY m.id"
    if limit is not None:
        sql += " LIMIT ?"
        args.append(limit)
    return pj.db.execute(sql, args).fetchall()


def _counts(pj: Project, me: Member) -> dict[str, tuple[int, int]]:
    """place -> (unread, of which important)."""
    sql = ("SELECT m.place AS place, count(*) AS n, sum(l.level = 'important') AS k FROM levels l "
           "JOIN messages m ON m.id = l.message_id "
           "LEFT JOIN reads r ON r.reader_kind = l.reader_kind AND r.reader_id = l.reader_id AND r.place = m.place "
           "WHERE l.reader_kind = ? AND l.reader_id = ? AND l.message_id > coalesce(r.upto, 0)")
    if me.kind == "agent":
        sql += " AND " + _NOT_HANDED
    return {r["place"]: (r["n"], r["k"] or 0) for r in pj.db.execute(sql + " GROUP BY m.place", (me.kind, me.id))}


def unread(pj: Project, me: Member) -> list[dict[str, Any]]:
    """[{in, count, important}] for the places with unread messages."""
    names: dict[str, str] = {}
    out = [{"in": _place_for(pj, place, me, names), "count": n, "important": k}
           for place, (n, k) in _counts(pj, me).items() if n]
    return sorted(out, key=lambda u: (not u["in"].startswith("#"), u["in"]))


def _move_read(pj: Project, me: Member, place: str, upto: int) -> None:
    with pj.db:
        pj.db.execute("INSERT INTO reads (reader_kind, reader_id, place, upto) VALUES (?, ?, ?, ?) "
                      "ON CONFLICT (reader_kind, reader_id, place) DO UPDATE SET upto = max(upto, excluded.upto)",
                      (me.kind, me.id, place, upto))


def _read_position(pj: Project, me: Member, place: str) -> int:
    r = pj.db.execute("SELECT upto FROM reads WHERE reader_kind = ? AND reader_id = ? AND place = ?",
                      (me.kind, me.id, place)).fetchone()
    return r["upto"] if r else 0


def _flag(v: Any, name: str) -> bool:
    """A boolean from JSON or a query string."""
    if v is None or v is False or v in ("", "false"):
        return False
    if v is True or v == "true":
        return True
    raise bad_request("bad_request", f"{name} must be true or false.")


def agent_messages(pj: Project, me: Member, where: Any, mid: Any, before: Any, limit: Any,
                   every: Any = None) -> dict[str, Any]:
    """`id`: one message again. `before`: older ones. `every` (all=true, alone): the unread messages of every
    place and level, oldest first, and the read position of each place moves to the last one returned from it.
    No place: the unread important messages of every place, and no read position moves (the normal ones between
    them stay unread). Otherwise the unread messages of the place, and the read position moves to the last one
    returned. Whatever is returned counts as handed over in full."""
    if _flag(every, "all"):
        if any(v is not None and v != "" for v in (where, mid, before)):
            raise bad_request("bad_request", "all goes alone: leave out `in`, `id` and `before` to read every unread "
                                             "message, or leave out `all`.")
        rows = _unread_rows(pj, me, None, _limit(limit))
        last: dict[str, int] = {}
        for r in rows:
            last[r["place"]] = r["id"]
        for place, upto in last.items():
            _move_read(pj, me, place, upto)
        out = views(pj, rows, me)
        _handed_by_reading(pj, me, [r["id"] for r in rows])
        return {"messages": out}
    one = _int(mid, "id")
    older = _int(before, "before")
    n = _limit(limit)
    if one is not None:
        rows = [_message(pj, me, one, "")]
    elif (where is None or where == "") and older is None:
        rows = _unread_rows(pj, me, None, n, important=True)
    else:
        if where is None or where == "":
            raise bad_request("bad_request", "Say which place to read: `in` is a #channel or a member's name; "
                                             "or pass `id` to read one message.")
        place, _ = resolve_place(pj, me, where)
        if older is not None:
            rows = list(reversed(pj.db.execute("SELECT * FROM messages WHERE place = ? AND id < ? ORDER BY id DESC "
                                               "LIMIT ?", (place, older, n)).fetchall()))
        else:
            rows = _unread_rows(pj, me, place, n)
            if rows:
                _move_read(pj, me, place, rows[-1]["id"])
    out = views(pj, rows, me)
    _handed_by_reading(pj, me, [r["id"] for r in rows])
    return {"messages": out}


# --------------------------------------------------------------------------- people

def channels_view(pj: Project, me: Member) -> dict[str, Any]:
    counts = _counts(pj, me)
    muted = {r["channel"] for r in pj.db.execute("SELECT channel FROM mutes WHERE member_kind = ? AND member_id = ?",
                                                  (me.kind, me.id))}
    from . import pins                  # pins builds on this module
    pinned = pins.by_channel(pj)
    channels = [{"name": n, "unread": counts.get("#" + n, (0, 0))[0], "important": counts.get("#" + n, (0, 0))[1],
                 "muted": n in muted, "pins": pinned.get(n, [])} for n in channel_names(pj)]
    mine = [r["place"] for r in pj.db.execute(
        "SELECT place FROM messages WHERE place LIKE 'p:%' AND (place LIKE ? OR place LIKE ?) "
        "GROUP BY place ORDER BY max(id) DESC", (f"p:{me.key}|%", f"p:%|{me.key}"))]
    names: dict[str, str] = {}
    private = [{"with": _place_for(pj, p, me, names), "unread": counts.get(p, (0, 0))[0],
                "important": counts.get(p, (0, 0))[1]} for p in mine]
    return {"channels": channels, "private": private}


def person_messages(pj: Project, me: Member, where: Any, before: Any, after: Any, limit: Any) -> dict[str, Any]:
    place, _ = resolve_place(pj, me, where)
    b, a, n = _int(before, "before"), _int(after, "after"), _limit(limit)
    if a is not None:
        sql, args = "SELECT * FROM messages WHERE place = ? AND id > ?", [place, a]
        if b is not None:
            sql, args = sql + " AND id < ?", args + [b]
        rows = pj.db.execute(sql + " ORDER BY id LIMIT ?", (*args, n)).fetchall()
    else:
        sql, args = "SELECT * FROM messages WHERE place = ?", [place]
        if b is not None:
            sql, args = sql + " AND id < ?", args + [b]
        rows = list(reversed(pj.db.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, n)).fetchall()))
    return {"messages": views(pj, rows, me), "read": _read_position(pj, me, place)}


def mark_read(pj: Project, me: Member, where: Any, upto: Any) -> dict[str, Any]:
    place, _ = resolve_place(pj, me, where)
    n = _int(upto, "upto", required=True)
    _move_read(pj, me, place, n)
    return {"read": _read_position(pj, me, place)}


def create_channel(pj: Project, actor: Actor, name: Any) -> dict[str, Any]:
    projects.require(pj, actor, "create_channel", "Creating channels needs the create_channel permission.")
    if isinstance(name, str) and name.startswith("#"):
        name = name[1:]
    if not isinstance(name, str) or not CHANNEL_RE.fullmatch(name):
        raise bad_request("bad_request", "A channel name is 1 to 40 lower-case letters, digits or '-', starting "
                                         "with a letter or digit.")
    try:
        with pj.db:
            pj.db.execute("INSERT INTO channels (name, created_by, created) VALUES (?, ?, ?)",
                          (name, actor.person_id, util.now()))
    except sqlite3.IntegrityError:
        raise conflict(f"The channel #{name} exists already.") from None
    util.log("channel_created", project=pj.slug, channel=name, by=actor.person_id)
    return {"name": name}


def agent_mutes(pj: Project, person_id: int) -> dict[str, list[str]]:
    """channel -> the person's agents that muted it."""
    out: dict[str, list[str]] = {}
    for r in pj.db.execute("SELECT m.channel, a.name FROM mutes m JOIN agents a ON a.id = m.member_id "
                           "WHERE m.member_kind = 'agent' AND a.person_id = ? ORDER BY a.name", (person_id,)):
        out.setdefault(r["channel"], []).append(r["name"])
    return out


def set_mute(pj: Project, actor: Actor, channel: str, muted: Any, agent: Any) -> dict[str, Any]:
    if not pj.db.execute("SELECT 1 FROM channels WHERE name = ?", (channel,)).fetchone():
        raise _no_channel(pj, "#" + channel)
    if not isinstance(muted, bool):
        raise bad_request("bad_request", "muted must be true or false.")
    kind, mid = "person", actor.person_id
    if agent not in (None, ""):
        a = pj.db.execute("SELECT * FROM agents WHERE name = ?", (agent,)).fetchone() if isinstance(agent, str) else None
        if a is None:
            raise not_found(f"There is no agent '{agent}'.")
        if a["person_id"] != actor.person_id:
            raise forbidden(f"'{agent}' is not your agent; only its own person mutes channels for it.")
        kind, mid = "agent", a["id"]
    with pj.db:
        if muted:
            pj.db.execute("INSERT OR IGNORE INTO mutes (member_kind, member_id, channel) VALUES (?, ?, ?)",
                          (kind, mid, channel))
        else:
            pj.db.execute("DELETE FROM mutes WHERE member_kind = ? AND member_id = ? AND channel = ?", (kind, mid, channel))
    return {"channel": channel, "muted": muted, **({"agent": agent} if kind == "agent" else {})}
