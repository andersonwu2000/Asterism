"""Moving ONE problem's complete state between workspaces — the DB half.

The shuttle between the flagship, the local box and the SP7 node was
done by hand four times, and twice it leaked orphan rows. Both leaks
were the same shape: a table with no `problem` column, pruned by a
hand-written list that could not see it (`strategies` keys on
`goal_id`; `strategy_subgoals` on `strategy_id`; `dead_attempts` on a
polymorphic `target_kind`/`target_id`). So nothing here is hand-listed
that the schema can answer:

  * `classify` puts EVERY table in one of four buckets, derived from
    `satellites.classify_tables` (the same derivation `asterism reset`'s
    auditor reads). A table it cannot place is `REFUSED`, and carry
    refuses to run — a new table must be placed deliberately, not
    dropped silently.
  * `belongs_to` turns a bucket into the SQL that selects one problem's
    rows, id sets and all.
  * `references` enumerates every place an id is repeated, so a remap
    can follow it: the FK edges `PRAGMA foreign_key_list` declares, plus
    the four kinds of reference SQLite cannot declare — polymorphic
    `target_kind`/`target_id`, ids embedded in payload JSON, ids
    embedded in a path column, and the strategy id baked into a Lean
    filename and its own declaration (that last one is the caller's to
    apply on disk; `LEAN_ID_FORMS` says where).

Everything here operates on a DETACHED snapshot (`carry.db`) or on a
scratch copy of one. Nothing in this module writes the live workspace;
`core/cli/carry.py` owns that, and owns the backups it takes first.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field

from . import satellites

# ─────────────────────────── the four buckets ───────────────────────────

#: Rows selected by the problem NAME — a `problem` column, the
#: `problems` row itself, or a declared predicate that decodes one.
PROBLEM_KEYED = "problem-keyed"
#: Rows with no `problem` column at all: selected through the problem's
#: derived id sets (goals / strategies / groups / pipelines). The bucket
#: both by-hand leaks came out of.
GOAL_KEYED = "goal-keyed"
#: Above or beside the problem. Carried whole, merged never replaced —
#: an empty Project legally outlives every problem that named it.
GLOBAL = "global"
#: Unplaceable. Carry refuses rather than guess.
REFUSED = "refused"

#: The polymorphic tables' buckets. `satellites.POLYMORPHIC_TABLES`
#: already declares HOW to ask each one; this says which bucket the
#: answer lands in. `librarian_fail_counts` decodes a problem name out
#: of its key, so it is problem-keyed even with no such column;
#: `pipelines`/`dead_attempts` reach the problem only through ids.
_POLYMORPHIC_BUCKET: "dict[str, str]" = {
    "pipelines": GOAL_KEYED,
    "dead_attempts": GOAL_KEYED,
    "librarian_fail_counts": PROBLEM_KEYED,
}

#: Tables the export snapshot does NOT prune. They are global assets:
#: `projects` sits above the problem, and the Library is a workspace's
#: shared product, not one problem's. Orthogonal to the bucket above —
#: `library_decls` travels whole yet is still problem-keyed on import,
#: where only P's rows are replaced. The consequence is deliberate and
#: has one consumer: a `library_decls` row of ANOTHER problem left in
#: carry.db dangles against the pruned `problems` table, which is the
#: one `foreign_key_check` finding an export is allowed to have.
def exports_whole(table: str) -> bool:
    return table == "projects" or table.startswith("library_")


def classify(conn: sqlite3.Connection) -> "dict[str, str]":
    """Every table -> its carry bucket. Derived; `REFUSED` is the
    failure `assert_classified` exists to turn into a refusal."""
    out: "dict[str, str]" = {}
    for table, kind in satellites.classify_tables(conn).items():
        if kind in ("anchor", "problem-column"):
            out[table] = PROBLEM_KEYED
        elif kind == "owner":
            out[table] = GLOBAL
        elif kind == "fk-transitive":
            out[table] = GOAL_KEYED
        elif kind == "polymorphic":
            out[table] = _POLYMORPHIC_BUCKET.get(table, REFUSED)
        else:
            out[table] = REFUSED
    return out


def assert_classified(conn: sqlite3.Connection) -> "dict[str, str]":
    """The classification, or `ValueError` naming what carry cannot
    place. Called before every export and every import: a table added
    without a bucket must stop the tool, because the alternative is the
    silent partial move the by-hand shuttle kept producing."""
    kinds = classify(conn)
    refused = sorted(t for t, k in kinds.items() if k == REFUSED)
    if refused:
        raise ValueError(
            "carry cannot place these tables: " + ", ".join(refused)
            + " — classify them in Tooling/state/carry.py "
              "(_POLYMORPHIC_BUCKET) or give them a `problem` column")
    return kinds


# ──────────────────────── the problem's id sets ─────────────────────────

@dataclass(frozen=True)
class Scope:
    """One problem's identity in a DB: its name and every id set the
    goal-keyed tables are reached through."""
    problem: str
    goals: "tuple[int, ...]" = ()
    strategies: "tuple[int, ...]" = ()
    groups: "tuple[int, ...]" = ()
    pipelines: "tuple[str, ...]" = ()


def scope_of(conn: sqlite3.Connection, problem: str) -> Scope:
    def ints(sql: str, args: tuple = ()) -> "tuple[int, ...]":
        return tuple(int(r[0]) for r in conn.execute(sql, args))

    goals = ints("SELECT id FROM goals WHERE problem = ?", (problem,))
    groups = ints("SELECT id FROM groups WHERE problem = ?", (problem,))
    strategies: "tuple[int, ...]" = ()
    if goals:
        ph = ",".join("?" * len(goals))
        strategies = ints(
            f"SELECT id FROM strategies WHERE goal_id IN ({ph})", goals)
    part = Scope(problem, goals, strategies, groups)
    where, args = belongs_to("pipelines", part)
    pipes = tuple(str(r[0]) for r in conn.execute(
        f"SELECT id FROM pipelines WHERE {where}", args))
    return Scope(problem, goals, strategies, groups, pipes)


def _in(column: str, values, *, as_text: bool = False) -> "tuple[str, list]":
    if not values:
        return "0", []
    ph = ",".join("?" * len(values))
    vals = [str(v) for v in values] if as_text else list(values)
    return f"{column} IN ({ph})", vals


def belongs_to(table: str, scope: Scope) -> "tuple[str, list]":
    """`(predicate, params)` selecting `table`'s rows that belong to the
    problem. The ONE spelling of "belongs to": the export prunes with
    its negation and the import selects with it, so the two cannot
    disagree about which rows are the problem's (they did, by hand,
    twice)."""
    tgt = satellites.PROBLEM_OF_TARGET
    if table == "problems":
        return "name = ?", [scope.problem]
    if table == "projects":
        return ("name IN (SELECT project FROM problems WHERE name = ?)",
                [scope.problem])
    if table == "strategies":
        return _in("goal_id", scope.goals)
    if table == "strategy_subgoals":
        return _in("strategy_id", scope.strategies)
    if table == "librarian_fail_counts":
        pred = satellites.POLYMORPHIC_TABLES[table][0] or "0"
        return (pred.replace(":p", "?"), [scope.problem, scope.problem])
    if table in ("pipelines", "queue", "dead_attempts"):
        arms, args = [], []
        for kind, ids in (("Goal", scope.goals),
                          ("Strategy", scope.strategies),
                          ("Group", scope.groups)):
            # `pipelines`/`queue` hold the id stringified; `dead_attempts`
            # declares the column INTEGER. Same polymorphism, two storage
            # classes — comparing the wrong one silently matches nothing.
            pred, vals = _in("target_id", ids,
                             as_text=(table != "dead_attempts"))
            arms.append(f"(target_kind = '{kind}' AND {pred})")
            args += vals
        if table == "dead_attempts":
            # A Forward/Librarian failure hangs off a Problem-target
            # pipeline, not off a goal — `wipe_problem_rows` learned this
            # the same way, on a reset that died on the FK.
            pred, vals = _in("pipeline_id", scope.pipelines, as_text=True)
            arms.append(f"({pred})")
            args += vals
        else:
            arms.append(f"(target_kind = 'Problem' AND {tgt} = ?)")
            args.append(scope.problem)
            if table == "queue":
                # v17 gave every queue row an explicit `problem` scope;
                # rows predating it are only reachable by target.
                arms.append("(problem = ?)")
                args.append(scope.problem)
        return " OR ".join(arms), args
    return "problem = ?", [scope.problem]


# ───────────────────────────── the id spaces ────────────────────────────

def pk_column(conn: sqlite3.Connection, table: str) -> "str | None":
    """The single-column primary key, or None (composite / rowid-only)."""
    pks = [r for r in conn.execute(f"PRAGMA table_info({table})") if r[5]]
    return str(pks[0][1]) if len(pks) == 1 else None


#: Single-column TEXT PKs are natural keys — a problem's name, a
#: project's name, the librarian's composed unit key — EXCEPT this one,
#: which is a machine-minted opaque id and so the only text id a remap
#: may re-mint. Renaming a problem is a different tool.
TEXT_ID_SPACES: "frozenset[str]" = frozenset({"pipelines"})


def id_spaces(conn: sqlite3.Connection) -> "dict[str, str]":
    """Table -> PK column, for every id a remap may have to re-mint."""
    out: "dict[str, str]" = {}
    for table in classify(conn):
        col = pk_column(conn, table)
        if col is None:
            continue
        info = {r[1]: (r[2] or "").upper()
                for r in conn.execute(f"PRAGMA table_info({table})")}
        if info.get(col) == "INTEGER" or table in TEXT_ID_SPACES:
            out[table] = col
    return out


# ─────────────────────────── the reference map ──────────────────────────

@dataclass(frozen=True)
class Ref:
    """One place an id from `target`'s space is repeated."""
    table: str
    column: str
    target: str
    #: polymorphic guard — the reference counts only for this kind
    kind_column: "str | None" = None
    kind_value: "str | None" = None
    #: the column holds JSON; this key inside it carries the id
    json_key: "str | None" = None
    #: the id is stored stringified
    as_text: bool = False

    def label(self) -> str:
        bits = f"{self.table}.{self.column}"
        if self.kind_value:
            bits += f"[{self.kind_value}]"
        if self.json_key:
            bits += f":{self.json_key}"
        return bits


#: References the schema CANNOT declare. Everything else is read off
#: `PRAGMA foreign_key_list`; these four kinds are what is left over,
#: and each one was found by grepping the writers, not by guessing:
#:
#:  * polymorphic target_kind/target_id  (`pipelines`, `queue`,
#:    `dead_attempts` — the dispatch contract, db/core.py §pipelines)
#:  * an FK the table simply never declared (`routine_verdicts.group_id`
#:    is `INTEGER NOT NULL` with no REFERENCES; the two `pipeline_id`
#:    columns likewise)
#:  * ids inside payload JSON (`state/commands.target_of` reads
#:    `target_goal_id`/`target_id`/`group_id` back out; a routine
#:    verdict's findings name `goal_id`)
#:  * an id inside a path column (`strategies.scratch_path` ends in
#:    `_strategy_s<its own id>.lean`, db/core.py:272)
_POLY_KINDS = (("Goal", "goals"), ("Strategy", "strategies"),
               ("Group", "groups"))

DECLARED_REFS: "tuple[Ref, ...]" = tuple(
    [Ref(t, "target_id", tgt, "target_kind", kind,
         as_text=(t != "dead_attempts"))
     for t in ("pipelines", "queue", "dead_attempts")
     for kind, tgt in _POLY_KINDS]
    + [
        Ref("routine_verdicts", "group_id", "groups"),
        Ref("routine_verdicts", "pipeline_id", "pipelines", as_text=True),
        Ref("spawn_usage", "pipeline_id", "pipelines", as_text=True),
        Ref("strategist_decisions", "payload", "goals",
            json_key="target_goal_id"),
        Ref("strategist_decisions", "payload", "groups",
            json_key="group_id"),
        Ref("human_commands", "payload", "goals", json_key="target_goal_id"),
        Ref("human_commands", "payload", "goals", json_key="target_id"),
        Ref("human_commands", "payload", "groups", json_key="group_id"),
        Ref("human_commands", "payload", "pipelines",
            json_key="pipeline_id", as_text=True),
        Ref("routine_verdicts", "fired_json", "goals", json_key="goal_id"),
        Ref("routine_verdicts", "unaudited_json", "goals",
            json_key="goal_id"),
        Ref("routine_verdicts", "verdict_json", "goals", json_key="goal_id"),
    ])

#: The problem's ROOT is `goals.origin = 'root'`, not a column on
#: `problems` — there is no root pointer to follow. Recorded here so the
#: next reader does not go looking for one.
ROOT_POINTER = None

#: Where a strategy id is baked into Lean, exactly as the framework
#: composes it (`_skeleton.build_strategy_skeleton` / `promote_to_alias`,
#: `prune._canonical_alias_content`). A bare `s<id>` token is NOT here on
#: purpose: `intro s1` is ordinary Lean, and a remap that rewrote it
#: would corrupt proofs. Only these four fully-anchored forms are.
LEAN_ID_FORMS: "tuple[str, ...]" = (
    "proofs._strategy_s{id}",     # import line / module name
    "_strategy_s{id}.lean",       # the file name itself
    "@{ns}.s{id}",                # def <slug> := @Problems.<p>.s<id>
    "theorem s{id}",              # the strategy file's own declaration
)


def references(conn: sqlite3.Connection) -> "list[Ref]":
    """Every reference a remap must follow: the FK edges the schema
    declares, plus `DECLARED_REFS`."""
    spaces = id_spaces(conn)
    out: "list[Ref]" = []
    for table in sorted(classify(conn)):
        for r in conn.execute(f"PRAGMA foreign_key_list({table})"):
            ref_table, from_col, to_col = r[2], r[3], r[4]
            if ref_table in spaces and to_col == spaces[ref_table]:
                out.append(Ref(table, from_col, ref_table))
    known = {(r.table, r.column, r.target, r.kind_value, r.json_key)
             for r in out}
    for r in DECLARED_REFS:
        if r.table not in spaces and r.table not in classify(conn):
            continue
        if (r.table, r.column, r.target, r.kind_value, r.json_key) in known:
            continue
        out.append(r)
    return out


# ──────────────────────────────── pruning ───────────────────────────────

def prune_to_problem(conn: sqlite3.Connection,
                     problem: str) -> "dict[str, int]":
    """Delete everything in this (detached) snapshot that is not the
    problem's. Returns the surviving row count per table.

    Runs with FKs off and re-checks with `PRAGMA foreign_key_check`
    afterwards: a delete order that is right for every schema shape
    does not exist (`groups` and `strategist_decisions` point at each
    other), and the whole-file check is stronger than the incremental
    one anyway."""
    kinds = assert_classified(conn)
    conn.execute("PRAGMA foreign_keys = OFF")
    scope = scope_of(conn, problem)
    kept: "dict[str, int]" = {}
    for table in sorted(kinds):
        if exports_whole(table):
            kept[table] = int(conn.execute(
                f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            continue
        where, args = belongs_to(table, scope)
        conn.execute(f"DELETE FROM {table} WHERE NOT ({where})", args)
        kept[table] = int(conn.execute(
            f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    conn.commit()
    return kept


def orphans(conn: sqlite3.Connection) -> "dict[str, int]":
    """Goal-keyed rows whose referent this snapshot does not hold — the
    leak the by-hand shuttle produced twice, asked of the snapshot
    itself. `satellites.orphan_rows` asks the same question of a live
    workspace; the floor is zero in both."""
    return satellites.orphan_rows(conn)


def foreign_key_findings(conn: sqlite3.Connection) -> "list[tuple]":
    """`PRAGMA foreign_key_check`, minus the one declared exception:
    `library_decls` rows of OTHER problems, which an export deliberately
    carries whole against a pruned `problems` table."""
    return [tuple(r) for r in conn.execute("PRAGMA foreign_key_check")
            if r[0] != "library_decls"]


# ──────────────────────────────── remapping ─────────────────────────────

@dataclass
class Remap:
    """Per-table `old id -> fresh id`, and the collisions that forced
    each one."""
    maps: "dict[str, dict]" = field(default_factory=dict)
    collisions: "dict[str, int]" = field(default_factory=dict)
    considered: "dict[str, int]" = field(default_factory=dict)

    def of(self, table: str, value):
        return self.maps.get(table, {}).get(value, value)

    def any(self) -> bool:
        return any(self.maps.values())


def plan_remap(src: sqlite3.Connection, target: sqlite3.Connection,
               problem: str) -> Remap:
    """Which imported ids collide with rows the target already holds for
    ANOTHER problem, and what fresh id each gets.

    The target's own rows for THIS problem are not collisions — the
    import deletes them first. Fresh ids start above every id either
    side has ever used in that space, so they can collide with neither
    set nor with an AUTOINCREMENT sequence that has run ahead."""
    remap = Remap()
    src_scope = scope_of(src, problem)
    tgt_scope = scope_of(target, problem)
    for table, pk in sorted(id_spaces(src).items()):
        where, args = belongs_to(table, src_scope)
        incoming = [r[0] for r in src.execute(
            f"SELECT {pk} FROM {table} WHERE {where}", args)]
        remap.considered[table] = len(incoming)
        if not incoming:
            continue
        mine, mine_args = belongs_to(table, tgt_scope)
        occupied = {r[0] for r in target.execute(
            f"SELECT {pk} FROM {table} WHERE NOT ({mine})", mine_args)}
        clash = [i for i in incoming if i in occupied]
        if not clash:
            continue
        remap.collisions[table] = len(clash)
        if table in TEXT_ID_SPACES:
            remap.maps[table] = {old: str(uuid.uuid4()) for old in clash}
            continue
        seq = target.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = ?",
            (table,)).fetchone()
        ceiling = max(
            [int(i) for i in incoming] + [int(i) for i in occupied]
            + [int(seq[0]) if seq else 0])
        remap.maps[table] = {
            old: ceiling + n for n, old in enumerate(sorted(clash), start=1)}
    return remap


def apply_remap(conn: sqlite3.Connection, remap: Remap) -> "list[str]":
    """Rewrite a SNAPSHOT's ids in place — primary keys first, then
    every reference `references()` knows. Returns the reference labels
    actually touched, for the summary.

    Safe in any order because every fresh id is above every old one, so
    no update can land on an id another row still holds."""
    if not remap.any():
        return []
    conn.execute("PRAGMA foreign_keys = OFF")
    spaces = id_spaces(conn)
    for table, mapping in remap.maps.items():
        pk = spaces[table]
        for old, new in sorted(mapping.items(), key=lambda kv: str(kv[0])):
            conn.execute(f"UPDATE {table} SET {pk} = ? WHERE {pk} = ?",
                         (new, old))
    touched: "list[str]" = []
    for ref in references(conn):
        mapping = remap.maps.get(ref.target)
        if not mapping:
            continue
        if ref.json_key:
            if _remap_json(conn, ref, mapping):
                touched.append(ref.label())
            continue
        guard, gargs = "", []
        if ref.kind_column:
            guard = f" AND {ref.kind_column} = ?"
            gargs = [ref.kind_value]
        hits = 0
        for old, new in mapping.items():
            o = str(old) if ref.as_text else old
            n = str(new) if ref.as_text else new
            cur = conn.execute(
                f"UPDATE {ref.table} SET {ref.column} = ?"
                f" WHERE {ref.column} = ?{guard}", [n, o] + gargs)
            hits += cur.rowcount or 0
        if hits:
            touched.append(ref.label())
    if _remap_scratch_paths(conn, remap):
        touched.append("strategies.scratch_path")
    conn.commit()
    return sorted(set(touched))


def _remap_json(conn: sqlite3.Connection, ref: Ref, mapping: dict) -> bool:
    """Rewrite one id key inside a JSON column. Walks nested lists and
    dicts: a routine verdict's findings are a LIST of `{goal_id: ...}`,
    not a flat payload."""
    pk = pk_column(conn, ref.table)
    if pk is None:
        return False
    hit = False
    rows = conn.execute(
        f"SELECT {pk}, {ref.column} FROM {ref.table}"
        f" WHERE {ref.column} IS NOT NULL").fetchall()
    for row_id, blob in rows:
        try:
            doc = json.loads(blob)
        except (TypeError, ValueError):
            continue
        changed = _walk_json(doc, ref.json_key, mapping, ref.as_text)
        if changed:
            hit = True
            conn.execute(
                f"UPDATE {ref.table} SET {ref.column} = ? WHERE {pk} = ?",
                (json.dumps(doc), row_id))
    return hit


def _walk_json(node, key: str, mapping: dict, as_text: bool) -> bool:
    changed = False
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if k == key and v is not None:
                probe = v
                if not as_text:
                    try:
                        probe = int(v)
                    except (TypeError, ValueError):
                        probe = v
                if probe in mapping:
                    new = mapping[probe]
                    node[k] = str(new) if isinstance(v, str) else new
                    changed = True
                    continue
            if _walk_json(v, key, mapping, as_text):
                changed = True
    elif isinstance(node, list):
        for item in node:
            if _walk_json(item, key, mapping, as_text):
                changed = True
    return changed


def _remap_scratch_paths(conn: sqlite3.Connection, remap: Remap) -> bool:
    """`strategies.scratch_path` ends in `_strategy_s<its own id>.lean`
    (db/core.py:272). A remapped strategy whose path still names the old
    id is the worst outcome available: `recovery.sweep_orphan_proof_files`
    deletes the untracked file with no matching row at the next daemon
    start, and `prune.reconcile_proved_goals` rewrites the alias from
    the DB — so a half-remap loses the proof."""
    mapping = remap.maps.get("strategies")
    if not mapping:
        return False
    hit = False
    for old, new in mapping.items():
        cur = conn.execute(
            "UPDATE strategies SET scratch_path ="
            " replace(scratch_path, ?, ?) WHERE id = ? AND scratch_path <> ''",
            (f"_strategy_s{old}.lean", f"_strategy_s{new}.lean", new))
        hit = hit or bool(cur.rowcount)
    return hit
