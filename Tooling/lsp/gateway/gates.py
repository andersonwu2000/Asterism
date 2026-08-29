"""The commit-time gates, mirrored pre-commit — `validate_file`'s
`submission` block.

Split out of `gateway.py` 2026-08-29 (A1-4b) unchanged: the five `_GW_*`
aliases onto the `state.assemble` SoT, the leading-comment reader, and
the eight submission mirrors — citation, annotation, locked signature,
stale olean, slug collision, decl head, namespace, axioms.

A leaf like `leantext`: it imports the `state.assemble` / `state.db` /
`state.transitions` primitives and `.state`'s `SessionMetadata`, and
nothing else from this package. That is what closes A1-4a's last
call-time reach-back — `rpc.apply_edit` imported `_citation_submission`
and `_locked_signature_submission` from the FACADE because they had not
moved yet; it imports them from HERE at module level now, so their
tool-side patch target is `gateway.rpc`'s own copied binding.

`_gw_leading_comments` and `_AXIOM_PROBE_DECL_CAP` do not re-export:
their only consumers are in this file, so a facade patch would go
vacuous and an AttributeError is the better answer. Everything else has
readers outside the package (`test_assemble_sot` asserts the five
`_GW_*` aliases ARE the assemble objects; the mirrors are called
directly), so the facade keeps them.
"""
from __future__ import annotations

import re
from pathlib import Path

from ...state import assemble, db, transitions
from .state import SessionMetadata


# ── validate_file submission mirror (#8 / P2) ────────────────────────
# The commit-time gates an agent's patch must also pass, surfaced pre-commit
# so a validate≠commit disagreement no longer costs a whole retry round.
# Returned in a `submission` block kept SEPARATE from Lean `diagnostics`
# (elaboration result vs framework policy — the user's separation instinct,
# in one tool call so the agent's existing validate_file loop catches it).

# Formerly hand-maintained `_GW_*` copies of the pipeline regexes ("kept
# local so the gateway does not import the heavy pipeline package") — now
# the SAME objects via the state-layer leaf `state.assemble` (task #5 Step
# A): the pipeline re-exports these under its historical names, so the two
# sides structurally cannot drift. The citability VERDICT stays with the
# shared SoT `db.classify_cited_slug`.
_GW_PROBLEM_IMPORT_RE = assemble.PROBLEM_IMPORT_RE
_GW_THEOREM_RE = assemble.THEOREM_LINE_RE
_GW_SORRY_STUB_RE = assemble.SORRY_STUB_RE
_GW_SLUG_RE = assemble.SLUG_RE
_GW_DECL_HEAD_RE = assemble.DECL_HEAD_RE


def _gw_leading_comments(text: str) -> str:
    """`--` comment lines before the first declaration head (ANY kind — a
    data goal's patch is a `def`) — presence-mirror of
    `pipeline._extract_leading_comments` (commit's annotation source)."""
    m = _GW_DECL_HEAD_RE.search(text)
    region = text[:m.start()] if m else text
    return "".join(ln for ln in region.splitlines(keepends=True)
                   if ln.strip().startswith("--"))


def _citation_submission(content: str, problem: str, workspace: "Path",
                         declared: "set[str]",
                         kind: "str | None" = None) -> "dict | None":
    """Classify each `import Problems.<problem>.proofs.L_<slug>` in `content`
    via the shared `db.classify_cited_slug` SoT so validate_file predicts the
    commit citation gate. `declared` = sibling stubs inlined this call (legit
    — skip). Best-effort: any DB failure → None (must never break validate).

    `kind` (the session's pipeline) sharpens the non-proved verdict: a
    Backward / Formalizer commit auto-links a cited open sibling as a
    strategy sub-goal; Builder/Forward commits have no
    auto-link — the citation dies at their axiom gate (transitive sorryAx),
    so for those pipelines the mirror reports it as the ERROR it is instead
    of the historical one-size warn (feedback family: agents trusted the
    warn, burned the round trip).

    Task #123 retired the stub-count sharpening: commit auto-links a cited
    unproved sibling whether or not the patch declares stubs (the wait edge,
    not the stub, is what defers verification), so a stub-less Backward /
    Formalizer patch now gets the same auto-link warn as a decomposition."""
    try:
        conn = db.connect(workspace / "asterism.db")
    except Exception:
        return None
    issues: "list[dict]" = []
    try:
        seen: "set[str]" = set()
        for m in _GW_PROBLEM_IMPORT_RE.finditer(content):
            if m.group(1) != problem:
                continue
            slug = m.group(2)
            if slug in seen or slug in declared:
                continue
            seen.add(slug)
            try:
                _gid, status, orphan = db.classify_cited_slug(
                    conn, problem=problem, slug=slug, workspace=workspace)
            except Exception:
                continue
            if status == "proved":
                continue
            if status is None:
                if orphan:
                    issues.append({
                        "slug": slug, "status": "orphan", "severity": "error",
                        "hint": "stub on disk with no tracked goal — citing it "
                                "imports a sorry; declare your own "
                                "new_<slug>.lean sub-goal instead"})
                # else: typo / cross-problem — lake's unknown-identifier covers it
                continue
            if status in transitions.GOAL_FAILED_TERMINALS:
                issues.append({
                    "slug": slug, "status": status, "severity": "error",
                    "hint": "hard-terminal; re-declare its statement as your "
                            "own new_<slug>.lean sub-goal stub"})
            else:  # open / attempting / pending_strategist_review / shelved
                if (kind or "").lower() in ("builder", "forward"):
                    issues.append({
                        "slug": slug, "status": status, "severity": "error",
                        "hint": f"non-proved: a {kind} commit has no "
                                "auto-link — the citation imports a sorry "
                                "and dies at the axiom gate; cite proved "
                                "siblings only, or (forward) declare the "
                                "fact as your own lemma"})
                else:
                    issues.append({
                        "slug": slug, "status": status, "severity": "warn",
                        "hint": "non-proved: commit auto-links it as a "
                                "dependency and your strategy waits until "
                                "it proves — legitimate, but rejected if it "
                                "is an ancestor of your goal or restates it"})
    finally:
        conn.close()
    return {"ok": not any(i["severity"] == "error" for i in issues),
            "issues": issues}


def _annotation_submission(content: str, is_mint: bool = False) -> "dict":
    """Mirror commit's `agent_no_annotation` gate: a final patch needs a
    leading `--` comment block. Applies only when `content` is a real
    submission (declares SOMETHING — any decl kind, a data goal's patch
    is a `def`/`structure` — with a non-sorry body); probing a
    `:= by sorry` stub is not a submission, so skip (`checked: False`).
    Historically theorem-only, so a def patch validated with
    `checked: false` and no explanation (feedback family: the agent
    couldn't tell whether the gate applied).

    The mint arm has no such gate since the Forward-rationale comment
    was retired (07-29) — nagging for it there is a false requirement."""
    if is_mint:
        return {"checked": False,
                "note": "mint commits need no annotation"}
    if (not _GW_DECL_HEAD_RE.search(content)
            or _GW_SORRY_STUB_RE.search(content)):
        # Explain the skip (07-19 ×2: agents read a bare
        # `checked: false` on a stub as "annotation maybe required").
        # The forward warning is deliberate (autopsy 2026-08-24): a
        # silent skip here let a WIP patch sail to commit and only
        # then learn the annotation was due.
        return {"checked": False,
                "note": "no annotation needed while the body is sorry "
                        "(a sub-goal stub never needs one) — the FINAL "
                        "patch will: replace the `-- STRATEGY:` "
                        "placeholder when the proof closes"}
    ok = bool(assemble.strip_annotation_placeholder(
        _gw_leading_comments(content)).strip())
    return {"checked": True, "ok": ok,
            "note": "" if ok else
            "FINAL patch only: replace the `-- STRATEGY:` placeholder "
            "with a leading -- comment before commit "
            "(agent_no_annotation; the unreplaced placeholder does not "
            "count). Ignore on exploratory probes."}


def _locked_signature_submission(content: str,
                                 attempts_dir: "Path") -> "dict | None":
    """D-lite mirror of the Backward commit signature gate: the strategy
    skeleton's `<kind> s<sid> <binders> : <type>` is LOCKED — commit
    byte-compares it (whitespace-normalized) and rejects any edit, even a
    mathematically equivalent rewrite that elaborates fine. Backward seeds
    the normalized signature into `_locked_signature.txt`; compare the
    content's current signature against it via the SAME shared helpers.
    None when there is no seed file (non-Backward session) or `content`
    doesn't mention the locked name (probing a sub-goal stub, not the
    patch)."""
    f = attempts_dir / "_locked_signature.txt"
    try:
        if not f.is_file():
            return None
        locked = f.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    parts = locked.split()
    name = parts[1] if len(parts) >= 2 else ""
    if not name or not re.search(rf"\b{re.escape(name)}\b", content):
        return None
    agent_sig = assemble.normalize_signature(
        assemble.signature_prefix(content, name))
    if agent_sig == locked:
        return {"checked": True, "ok": True}
    return {
        "checked": True, "ok": False,
        "hint": (f"the `{name}` signature is LOCKED — commit rejects ANY "
                 "edit to it (even an equivalent rewrite that elaborates "
                 "fine); restore it exactly and make changes after `:= by` "
                 "only"),
        "locked": locked,
        "current": agent_sig or "(declaration head not parseable)",
    }


def _stale_olean_submission(content: str, problem: str,
                            workspace: "Path") -> "dict | None":
    """D-lite staleness warning: this probe resolves committed siblings via
    their on-disk build products; if a cited `L_<slug>`'s source is newer
    than its .olean (or the .olean is missing), the probe's verdict for
    that citation is based on a stale world — commit's real build will
    recompile. Detection only (whether the recompile changes the verdict
    needs the real build); None when content cites nothing."""
    cites = [m.group(2) for m in _GW_PROBLEM_IMPORT_RE.finditer(content)
             if m.group(1) == problem]
    if not cites:
        return None
    prel = Path(*problem.split(".")) if "." in problem else Path(problem)
    issues: "list[dict]" = []
    for slug in cites:
        src = (workspace / "Problems" / prel / "proofs" / f"L_{slug}.lean")
        if not src.exists():
            continue                    # citation gate reports missing goals
        rel = Path("Problems") / prel / "proofs" / f"L_{slug}.olean"
        oleans = [workspace / ".lake" / "build" / "lib" / "lean" / rel,
                  workspace / ".lake" / "build" / "lib" / rel]
        try:
            fresh = any(o.exists() and o.stat().st_mtime >= src.stat().st_mtime
                        for o in oleans)
        except OSError:
            continue
        if not fresh:
            issues.append({
                "slug": slug,
                "note": (f"L_{slug}.lean is newer than its .olean (or the "
                         ".olean is missing) — this probe's verdict for the "
                         "citation is based on a stale build; commit will "
                         "recompile it"),
            })
    return {"ok": not issues, "issues": issues}


def _slug_collision_submission(stub_map: "dict[str, str]", problem: str,
                               workspace: "Path") -> "dict | None":
    """Predict the commit-only slug fate for BATCH STUBS (agent_feedback
    #4b: LSP all-green, bounced at commit): a `new_<slug>.lean` whose
    slug already exists as a goal in this problem either auto-suffixes
    to `_2` at commit (breaking the decl-name match every citation in
    the batch relies on) or — when the twin is a strict ancestor with an
    identical head — dies as `circular_decomposition`.

    FORK (agent_feedback 2026-07-11, 12 contradiction reports): when the
    colliding twin is SHELVED and the stub's statement is byte-identical
    (normalized signature match — display heuristic only; the commit
    authority is the kernel defeq/reuse path), the SANCTIONED move is to
    keep the name and let commit dedupe-link to the twin — so the entry
    downgrades to `info` instead of scaring the agent into a rename that
    mints yet another fresh-slug twin. Scoped to stubs only: a patch
    legitimately declares its own goal's slug. Best-effort: DB failure →
    None."""
    if not stub_map:
        return None
    try:
        conn = db.connect(workspace / "asterism.db")
    except Exception:
        return None
    try:
        issues: "list[dict]" = []
        all_ok = True
        for slug in sorted(stub_map):
            row = conn.execute(
                "SELECT id, status, lean_path FROM goals WHERE problem = ?"
                "  AND slug = ? AND alias_target_id IS NULL LIMIT 1",
                (problem, slug),
            ).fetchone()
            if row is None:
                continue
            same_stmt = False
            if str(row["status"]) == "shelved":
                try:
                    twin_text = (workspace / str(row["lean_path"])
                                 ).read_text(encoding="utf-8")
                    twin_sig = assemble.signature_prefix(twin_text, slug)
                    cand_sig = assemble.signature_prefix(
                        stub_map[slug], slug)
                    same_stmt = (bool(twin_sig) and bool(cand_sig)
                                 and assemble.normalize_signature(twin_sig)
                                 == assemble.normalize_signature(cand_sig))
                except OSError:
                    same_stmt = False
            if same_stmt:
                issues.append({
                    "slug": slug, "existing_goal": int(row["id"]),
                    "status": str(row["status"]),
                    "severity": "info",
                    "hint": (f"`{slug}` is statement-identical to the "
                             f"existing SHELVED goal {int(row['id'])} — "
                             f"this is the sanctioned dedupe path: KEEP "
                             f"this name; at commit the stub links to "
                             f"that twin (link-and-wait, no new goal). "
                             f"Do NOT rename — a fresh slug just mints "
                             f"another twin."),
                })
                continue
            all_ok = False
            issues.append({
                "slug": slug, "existing_goal": int(row["id"]),
                "status": str(row["status"]),
                "severity": "warn",
                "hint": (f"a goal named `{slug}` already exists "
                         f"(status={row['status']}). At commit this stub "
                         f"auto-suffixes to `{slug}_2`, breaking every "
                         f"decl-name reference to it in this batch; if the "
                         f"twin is an ancestor on your chain with the same "
                         f"statement, commit rejects the whole strategy as "
                         f"circular_decomposition. Rename the sub-goal, or "
                         f"cite the existing goal instead of re-declaring "
                         f"it."),
            })
        if not issues:
            return {"checked": True, "ok": True}
        return {"checked": True, "ok": all_ok, "issues": issues}
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _declhead_submission(content: str) -> "dict":
    """Mirror commit's slug gate: every top-level `<kind> <name>` declaration's
    name must be snake_case (`^[a-z][a-z0-9_]*$`). A camelCase def/theorem name
    elaborates clean but the Forward/Backward commit parser bounces it AFTER a
    full lake build — surface it pre-commit so the agent renames in-loop
    (agent_feedback green_theorem #69/#107). `checked: False` when the content
    declares nothing to slug (e.g. a pure import/open probe)."""
    bad: "list[str]" = []
    for m in _GW_DECL_HEAD_RE.finditer(content):
        name = m.group(2)
        if not _GW_SLUG_RE.match(name):
            bad.append(name)
    if not bad:
        return {"checked": _GW_DECL_HEAD_RE.search(content) is not None,
                "ok": True}
    return {"checked": True, "ok": False, "bad_slugs": sorted(set(bad)),
            "note": "declaration name(s) must be snake_case "
                    "(^[a-z][a-z0-9_]*$); commit rejects a camelCase slug after "
                    "a full lake build — rename now"}


#: Decline placeholder marker — kept in lockstep with
#: `pipeline.forward._DECLINE_RE` (the gateway subprocess stays free of
#: pipeline imports; a source pin in tests holds the two together).
_GW_DECLINE_RE = re.compile(r"^\s*--\s*decline\s*:\s*([a-z_]+)\b",
                            re.MULTILINE | re.IGNORECASE)


def _namespace_submission(content: str, problem: str) -> "dict | None":
    """Mirror the forward namespace-fidelity gate (forward.py): the file
    elaborates clean under ANY `namespace` wrapper, but commit resolves
    the declaration under the canonical `Problems.<problem>` — a
    respelled wrapper passed validate_file and only bounced at commit
    (Test.provider_probe, 2026-08-24 feedback: `Problems.provider_probe`
    vs `Problems.Test.provider_probe`). None when there is no namespace
    line, it already matches, or the file is a decline placeholder."""
    m = re.search(r"^namespace\s+(\S+)", content, re.M)
    if not m or _GW_DECLINE_RE.search(content):
        return None
    want = f"Problems.{problem}"
    if m.group(1) == want:
        return None
    return {"ok": False, "got": m.group(1), "want": want,
            "note": (f"commit resolves your declaration under the canonical "
                     f"`namespace {want}` (case included) — keep the seed's "
                     f"namespace/end lines exactly as seeded")}


#: Cap on decls probed per validate — a patch carries one theorem, a
#: batch stub file one decl; anything past this is pathological input.
_AXIOM_PROBE_DECL_CAP = 8


def _axioms_submission(backend, slot, content: str,
                       meta: "SessionMetadata") -> "dict | None":
    """The commit axiom gate, mirrored pre-commit (2026-08-18). g7941:
    a `native_decide` proof validated green here, built for 51 minutes,
    and died at the commit gate — a verdict knowable at this probe for
    one warm RPC per decl. Returns a failing submission entry when a
    decl's axioms exceed the problem whitelist, None when clean /
    unknowable (the commit gate stays the authority; this only warns).

    `sorryAx` is deliberately NOT flagged here: `:= by sorry` stubs are
    the legal decomposition currency pre-commit, and the commit gate's
    own tripwire handles the illegal cases."""
    try:
        from ...state import intent as _intent
        conn = db.connect_readonly(Path(meta.workspace) / "asterism.db")
        try:
            pintent = _intent.read(conn, meta.problem)
        finally:
            conn.close()
        if pintent is None:
            return None
        wl = set(_intent.effective_axioms(pintent, problem=meta.problem))
    except Exception:  # noqa: BLE001 — no intent, no verdict
        return None
    wl.add("sorryAx")
    names: "list[str]" = []
    for m in _GW_DECL_HEAD_RE.finditer(content):
        if m.group(2) not in names:
            names.append(m.group(2))
    rogue: "set[str]" = set()
    for name in names[:_AXIOM_PROBE_DECL_CAP]:
        try:
            r = backend.rpc_call(
                slot.slot_uri, "Asterism.printAxioms",
                {"fqName": f"Problems.{meta.problem}.{name}"},
                timeout=30)
        except Exception:  # noqa: BLE001 — probe is best-effort
            continue
        if r.get("found"):
            rogue |= set(r.get("axioms") or []) - wl
    if not rogue:
        return None
    from ...state.failures import rogue_axioms_message
    return {"ok": False, "rogue": sorted(rogue),
            "note": rogue_axioms_message(rogue)}


def _ancestor_cycle(content: str, meta) -> "dict | None":
    """Owner ruling 2026-08-30: a file that names one of its own STRICT
    ANCESTORS is refused at the editing tools, not at commit. Citing an
    ancestor closes a dependency cycle (the ancestor's proof contains
    this goal); five spawns died at commit for it in one afternoon,
    ~16 minutes each. The predicate is the graph's own
    (`db.strict_ancestor_slugs`, the walk commit uses), the scan is over
    identifiers with comments stripped. Siblings, proved cross-branch
    bricks and the file's own name are not ancestors."""
    import re as _re

    from ...quality.names import _strip_comments
    from ...state import db as _db
    goal_id = getattr(meta, "goal_id", None)
    workspace = getattr(meta, "workspace", None)
    if goal_id is None or workspace is None:
        return None
    try:
        conn = _db.connect(workspace / "asterism.db")
        try:
            ancestors = _db.strict_ancestor_slugs(conn, int(goal_id))
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — no DB at hand: the commit gate still owns it
        return None
    if not ancestors:
        return None
    code = "\n".join(_strip_comments(content))
    hits = sorted(slug for slug in ancestors
                  if _re.search(r"(?<![\w.'])" + _re.escape(slug) + r"(?![\w'])",
                                code))
    if not hits:
        return None
    return {
        "ok": False,
        "ancestors": hits,
        "teaching": (
            "This file cites " + ", ".join(f"`{h}`" for h in hits) +
            " — an ANCESTOR of your goal on its own chain: this goal is "
            "part of that proof, so it cannot also prove itself with it "
            "(a dependency cycle; commit would reject it as "
            "circular_decomposition). Cite a sibling or a proved brick "
            "instead, prove the step here, or — if the sub-goal really "
            "needs the ancestor — this sub-goal is mis-cut: return it to "
            "NL (decline with this reason) so the Strategist re-plans."),
    }

