"""The dedupe kernel probes — cold `lake env lean` batches that ask Lean
whether a candidate statement is provable from / definitionally equal to
a canonical one — housed so that ONE bad module can never refuse a whole
batch (owner ruling 2026-08-29).

Before 2026-08-29 both probes imported every canonical module into one
environment. Two shelved leftovers each carrying a private copy of the
same helper (`four_packet_valid`) made Lean stop at the import line with
`environment already contains`, and — because an error outside every
pair's line range means "Lean may not have reached the pairs" — the
probe refused all pairs. Eight of ten batches that run, silently, until
the degraded ledger showed it.

The shape now:

1. a header-only file (`import Mathlib` + the modules) is elaborated
   first; its errors are attributed per import line —
   * `object file … does not exist` / any other error on an import line
     → that module is DROPPED (recorded per module), its pairs are False;
   * `import M failed, environment already contains` → M is DEFERRED to
     the next batch: nothing is wrong with M, it just cannot share a room;
2. the pairs are judged per batch, in the batch that holds their own
   canonical, with the same per-pair line attribution as before;
3. the partition is cached per (workspace, module set, file mtimes) so
   the header round costs one cold elaboration per change, not per call.

"Which of the two colliders is the bad one" is not a question the probe
can answer, and it does not need to — every pair is judged in a room it
can load.
"""
from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path
from typing import Callable

from ..core import degraded as _degraded
from ..core.process_group import no_window_creationflags
from ..state import db, metaprog
from . import names as _names

# Lake/Lean error line: `<path>:<line>:<col>: error: ...`. Lazy `.+?` for
# the path part so a Windows drive-letter colon (`D:\...`) doesn't abort
# the match; the `\d+:\d+` line-col anchor identifies the boundary.
_LAKE_ERR_RE = re.compile(r"^.+?:(\d+):\d+:\s*error", re.MULTILINE)
# Lean stops elaborating at `maxErrors` and exits mid-file; every pair
# AFTER that point emits nothing, and the attribution loop would read
# the silence as success (b6 2026-07-12: 184-pair batch, 98 failing
# pairs hit the default cap of 100, the first post-cutoff pair became a
# fake alias that shadowed the true twin). The probes raise the option
# in-file; this marker is the backstop should the raised cap ever be
# hit again — pairs at/after the marker line are UNKNOWN, not clean.
_MAX_ERRORS_RE = re.compile(
    r"^.+?:(\d+):\d+:\s*error: maximum number of errors", re.MULTILINE)
_BATCH_TIMEOUT_SEC = 240

_ERR_LINE_RE = re.compile(r"^.+?:(\d+):\d+:\s*error:?\s*(.*)$", re.MULTILINE)
_IMPORT_COLLIDES_RE = re.compile(
    r"import (\S+) failed, environment already contains")
_OBJECT_FILE_RE = re.compile(r"object file '([^']+)'")
#: Header rounds per batch before giving up on housing the leftovers.
_MAX_ROUNDS = 4


def _max_errors_cutoff(output: str) -> "int | None":
    """Line number of Lean's `maxErrors ... exiting` marker, or None."""
    hits = [int(m.group(1)) for m in _MAX_ERRORS_RE.finditer(output)]
    return min(hits) if hits else None


# ───────────────────────────── header partition (pure) ─────────────────────

def _module_of_olean(path: str, modules: "set[str]") -> "str | None":
    norm = path.replace("\\", "/")
    stem = norm[:-len(".olean")] if norm.endswith(".olean") else norm
    for mod in modules:
        if stem.endswith(mod.replace(".", "/")):
            return mod
    return None


def partition_header_errors(output: str, module_at_line: "dict[int, str]",
                            closure: "Callable[[str], set[str]] | None" = None,
                            ) -> "tuple[dict[str, str], list[str]]":
    """Attribute a header run's errors: `(dropped {module: reason},
    deferred [module])`. A module that cannot load at all is dropped; a
    module Lean refused only because the environment already holds one
    of its names is deferred to another batch.

    Lean names the module that FAILED to import, which is the
    transitive one when a header module pulls it in (measured
    2026-08-30: `import L_four_packet_mask_certificate failed …` for a
    header that listed only its importer). `closure(header_module)` —
    its transitive in-workspace imports — turns that name back into
    the header module(s) to defer; without it the name matches
    nothing and the whole room used to go out as a global error."""
    dropped: dict[str, str] = {}
    deferred: list[str] = []
    modules = set(module_at_line.values())
    for m in _ERR_LINE_RE.finditer(output):
        line, msg = int(m.group(1)), m.group(2).strip()
        cm = _IMPORT_COLLIDES_RE.search(msg)
        if cm:
            mod = cm.group(1)
            owners = [mod] if mod in modules else (
                [h for h in module_at_line.values() if mod in closure(h)]
                if closure is not None else [])
            for h in owners:
                if h not in deferred and h not in dropped:
                    deferred.append(h)
            continue
        om = _OBJECT_FILE_RE.search(msg)
        if om:
            mod = (_module_of_olean(om.group(1), modules)
                   or module_at_line.get(line))
            if mod and mod not in dropped:
                dropped[mod] = f"olean missing: {om.group(1)}"[:200]
            continue
        mod = module_at_line.get(line)
        if mod and mod not in dropped:
            dropped[mod] = msg[:200]
    return dropped, deferred


def header_content(modules: "list[str]") -> "tuple[str, dict[int, str]]":
    lines = ["import Mathlib"]
    at: dict[int, str] = {}
    for mod in modules:
        lines.append(f"import {mod}")
        at[len(lines)] = mod
    return "\n".join(lines) + "\n", at


_IMPORT_LINE_RE = re.compile(r"^import\s+(\S+)", re.MULTILINE)
#: (path, mtime_ns, size) -> (in-workspace direct imports, top-level names)
_FILE_CACHE: "dict[tuple, tuple[list[str], list[str]]]" = {}


def _module_file(workspace: Path, mod: str) -> Path:
    return workspace / (mod.replace(".", "/") + ".lean")


def _read_module(workspace: Path, mod: str) -> "tuple[list[str], list[str]]":
    """A module's in-workspace direct imports and its top-level names
    (`quality.names`), cached on the file's identity."""
    path = _module_file(workspace, mod)
    try:
        st = path.stat()
    except OSError:
        return [], []
    key = (str(path), st.st_mtime_ns, st.st_size)
    hit = _FILE_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], []
    imports = [m for m in _IMPORT_LINE_RE.findall(text)
               if _module_file(workspace, m).exists()]
    names = [q for q, _kind, _line in _names.top_level_names(text)]
    _FILE_CACHE[key] = (imports, names)
    return imports, names


def import_closure(workspace: Path, mod: str) -> "set[str]":
    """Every in-workspace module `mod` imports, transitively (not itself)."""
    seen: set[str] = set()
    stack = list(_read_module(workspace, mod)[0])
    while stack:
        m = stack.pop()
        if m in seen or m == mod:
            continue
        seen.add(m)
        stack.extend(_read_module(workspace, m)[0])
    return seen


def closure_defs(workspace: Path, mod: str) -> "dict[str, str]":
    """`{top-level name: defining module}` over `mod` and its closure —
    the environment `import mod` would bring in."""
    defs: dict[str, str] = {}
    for m in [mod, *sorted(import_closure(workspace, mod))]:
        for name in _read_module(workspace, m)[1]:
            defs.setdefault(name, m)
    return defs


def pre_house(workspace: Path, modules: "list[str]") -> "list[list[str]]":
    """Rooms in which no two modules bring the same name from different
    modules — decided from the files, before any cold Lean round. Lean
    reports only the FIRST collision per run, so a room with k
    colliders would otherwise cost k rounds (`_MAX_ROUNDS` = 4 — a
    room with more went out unhoused). The Lean rounds stay as the
    safety net for what the source scan cannot see."""
    rooms: list[tuple[list[str], dict[str, str]]] = []
    for mod in modules:
        defs = closure_defs(workspace, mod)
        for members, held in rooms:
            if all(held.get(n, m) == m for n, m in defs.items()):
                members.append(mod)
                held.update(defs)
                break
        else:
            rooms.append(([mod], dict(defs)))
    return [members for members, _held in rooms]


_BATCH_CACHE: "dict[tuple, tuple[list[list[str]], dict[str, str]]]" = {}


def _mtime_key(workspace: Path, modules: "list[str]") -> frozenset:
    keys = []
    for mod in modules:
        p = workspace / (mod.replace(".", "/") + ".lean")
        try:
            st = p.stat()
            keys.append((mod, st.st_mtime_ns, st.st_size))
        except OSError:
            keys.append((mod, None, None))
    return frozenset(keys)


def import_batches(workspace: Path, modules: "list[str]",
                   run: "Callable[[str], tuple[int, str]]",
                   ) -> "tuple[list[list[str]], dict[str, str]]":
    """House `modules` in batches that each load cleanly together.
    `run(header_content) -> (rc, output)` is one cold elaboration.
    Returns `(batches, dropped)`; every module ends up in exactly one
    batch or in `dropped` with its reason."""
    key = (str(workspace), _mtime_key(workspace, modules))
    hit = _BATCH_CACHE.get(key)
    if hit is not None:
        return [list(b) for b in hit[0]], dict(hit[1])
    dropped_all: dict[str, str] = {}
    batches: list[list[str]] = []

    def closure(mod: str) -> "set[str]":
        return import_closure(workspace, mod)

    for room in pre_house(workspace, list(dict.fromkeys(modules))):
        todo = room
        depth = 0
        while todo and depth < _MAX_ROUNDS:
            depth += 1
            cur = list(todo)
            deferred_next: list[str] = []
            for _round in range(_MAX_ROUNDS):
                content, at = header_content(cur)
                rc, out = run(content)
                dropped, deferred = partition_header_errors(
                    out, at, closure=closure)
                if rc != 0 and not dropped and not deferred:
                    # an unattributable header failure: nothing in this
                    # room can be trusted to have loaded
                    for mod in cur:
                        dropped_all.setdefault(
                            mod, f"header rc={rc}: {out[:120]}")
                    cur = []
                    break
                dropped_all.update(dropped)
                cur = [m for m in cur
                       if m not in dropped and m not in deferred]
                for mod in deferred:
                    if mod not in deferred_next:
                        deferred_next.append(mod)
                if not dropped and not deferred:
                    break
            if cur:
                batches.append(cur)
            todo = deferred_next
        for mod in todo:
            dropped_all.setdefault(
                mod, "could not be housed within the round budget")
    _BATCH_CACHE[key] = ([list(b) for b in batches], dict(dropped_all))
    return batches, dict(dropped_all)


import_batches.cache_clear = _BATCH_CACHE.clear  # type: ignore[attr-defined]


# ───────────────────────────────── running Lean ────────────────────────────

def _run_lean(workspace: Path, content: str) -> "tuple[int, str]":
    """One cold `lake env lean` over a throwaway file. Raises
    `subprocess.TimeoutExpired` / `OSError` to the caller."""
    tmp_dir = workspace / ".attempts"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / f"_dedupe_probe_{uuid.uuid4().hex}.lean"
    tmp_file.write_text(content, encoding="utf-8")
    try:
        r = subprocess.run(
            ["lake", "env", "lean", "-DmaxErrors=10000", str(tmp_file)],
            cwd=str(workspace),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=_BATCH_TIMEOUT_SEC,
            creationflags=no_window_creationflags(),
        )
        return r.returncode, r.stdout + r.stderr
    finally:
        try:
            tmp_file.unlink()
        except OSError:
            pass


def _preflight_build(workspace: Path, modules: "list[str]") -> None:
    if not modules:
        return
    from ..pipeline._lake import lake_build_modules as _lake_build_modules
    try:
        _lake_build_modules(workspace, sorted(modules))
    except Exception as exc:  # noqa: BLE001 — best-effort
        print(f"[dedupe] pre-flight lake build failed (non-fatal): {exc}",
              flush=True)
        _degraded.record(workspace, "dedupe_preflight_build", str(exc))


def _attribute(workspace: Path, output: str, rc: int,
               pair_start_lines: "list[int]", total_lines: int,
               ) -> "list[bool]":
    """Per-pair verdicts from one pair file's output (the 2026-05-29 and
    2026-07-12 rules: the error-line scan is the truth, never rc alone;
    an error outside every pair range refuses the batch; pairs at or
    after a `maxErrors` cutoff are unknown, not clean)."""
    n = len(pair_start_lines)
    error_lines: set[int] = set()
    for m in _LAKE_ERR_RE.finditer(output):
        error_lines.add(int(m.group(1)))
    if not error_lines:
        if rc == 0:
            return [True] * n
        _degraded.record(workspace, "dedupe_probe_global_error",
                         f"rc={rc} without error lines: {output[:200]}")
        return [False] * n

    def _end(i: int) -> int:
        return (pair_start_lines[i + 1] - 1
                if i + 1 < n else total_lines)
    in_any_pair = set()
    for el in error_lines:
        for i, start in enumerate(pair_start_lines):
            if start <= el <= _end(i):
                in_any_pair.add(el)
                break
    if error_lines - in_any_pair:
        print(f"[dedupe] probe global error — this batch's pairs refused; "
              f"first output: {output[:200]!r}", flush=True)
        _degraded.record(workspace, "dedupe_probe_global_error", output[:200])
        return [False] * n
    cutoff = _max_errors_cutoff(output)
    results: list[bool] = []
    for i, start in enumerate(pair_start_lines):
        has_error = any(start <= el <= _end(i) for el in error_lines)
        results.append(not has_error
                       and (cutoff is None or _end(i) < cutoff))
    return results


def _run_partitioned(workspace: Path, problem: str,
                     pair_modules: "list[str]",
                     build_pair: "Callable[[int], list[str]]",
                     *, skip_value: "bool | None",
                     ) -> "list[bool | None]":
    """The shared probe body: pre-flight build, partition, one pair file
    per batch, verdicts back in the caller's pair order. `pair_modules[i]`
    is pair i's canonical module ('' = none). `skip_value` is what a
    metaprogramming-skipped batch reports (None = unchecked)."""
    n = len(pair_modules)
    results: "list[bool | None]" = [None] * n
    mods = list(dict.fromkeys(m for m in pair_modules if m))
    _preflight_build(workspace, mods)
    defs_mod = (f"Problems.{problem}.Defs"
                if (db.problem_dir(workspace, problem) / "Defs.lean").exists()
                else None)
    header_mods = ([defs_mod] if defs_mod else []) + mods
    try:
        batches, dropped = import_batches(
            workspace, header_mods, lambda c: _run_lean(workspace, c))
    except subprocess.TimeoutExpired:
        print(f"[dedupe] probe header TIMED OUT after {_BATCH_TIMEOUT_SEC:.0f}s "
              f"— {n} pair(s) UNCHECKED (not 'no duplicate')", flush=True)
        _degraded.record(workspace, "dedupe_probe_timeout",
                         f"{n} pair(s) unchecked after "
                         f"{_BATCH_TIMEOUT_SEC:.0f}s (header)")
        return results
    except OSError as e:
        print(f"[dedupe] probe could not run ({e}) — {n} pair(s) "
              f"UNCHECKED (not 'no duplicate')", flush=True)
        _degraded.record(workspace, "dedupe_probe_unavailable", str(e))
        return results
    header_failures = {m: w for m, w in dropped.items()
                       if w.startswith("header rc=")}
    if header_failures:
        # nothing could be attributed to a module: the header itself did
        # not run — that is the probe's global error, not N bad modules
        why = next(iter(header_failures.values()))
        print(f"[dedupe] probe global error — header refused "
              f"({len(header_failures)} module(s)): {why[:200]!r}", flush=True)
        _degraded.record(workspace, "dedupe_probe_global_error", why[:200])
    for mod, why in dropped.items():
        if mod in header_failures:
            continue
        print(f"[dedupe] probe dropped module {mod}: {why}", flush=True)
        _degraded.record(workspace, "dedupe_probe_module_dropped",
                         f"{mod}: {why}")
    for i, mod in enumerate(pair_modules):
        if mod and mod in dropped:
            results[i] = False
    housed = {m for b in batches for m in b}
    for bi, batch in enumerate(batches):
        idxs = [i for i, mod in enumerate(pair_modules)
                if results[i] is None
                and ((mod in batch) if mod in housed else bi == 0)]
        if not idxs:
            continue
        lines: list[str] = ["import Mathlib"]
        lines.extend(f"import {m}" for m in batch)
        lines += ["", "namespace dedupe_check", ""]
        pair_start_lines: list[int] = []
        for i in idxs:
            pair_start_lines.append(len(lines) + 1)
            lines.extend(build_pair(i))
        lines.append("end dedupe_check")
        content = "\n".join(lines)
        if metaprog.scan_metaprogramming(content) is not None:
            print("[dedupe] probe batch skipped — a candidate carries a "
                  "metaprogramming entry", flush=True)
            for i in idxs:
                results[i] = skip_value
            continue
        try:
            rc, out = _run_lean(workspace, content)
        except subprocess.TimeoutExpired:
            print(f"[dedupe] probe TIMED OUT after {_BATCH_TIMEOUT_SEC:.0f}s "
                  f"— {len(idxs)} pair(s) UNCHECKED (not 'no duplicate')",
                  flush=True)
            _degraded.record(workspace, "dedupe_probe_timeout",
                             f"{len(idxs)} pair(s) unchecked after "
                             f"{_BATCH_TIMEOUT_SEC:.0f}s")
            continue
        except OSError as e:
            print(f"[dedupe] probe could not run ({e}) — {len(idxs)} pair(s) "
                  f"UNCHECKED (not 'no duplicate')", flush=True)
            _degraded.record(workspace, "dedupe_probe_unavailable", str(e))
            continue
        verdicts = _attribute(workspace, out, rc, pair_start_lines, len(lines))
        for i, v in zip(idxs, verdicts):
            results[i] = v
        if not all(verdicts):
            first = next((ln for ln in out.splitlines() if "error" in ln), "")
            print(f"[dedupe] probe: {sum(1 for x in verdicts if not x)}/"
                  f"{len(idxs)} pair(s) refused in this batch; first error: "
                  f"{first[:200]}", flush=True)
    return results


# ─────────────────────────────────── the probes ────────────────────────────

def _batch_provable_via_apply(
    workspace: Path,
    problem: str,
    pairs: "list[tuple[str, str, str]]",
) -> "list[bool | None]":
    """For each (cand_signature, canonical_module, canonical_fqn) pair,
    check if `apply @canonical_fqn <;> assumption` proves
    `<cand_signature>`. `canonical_fqn` is built by the caller (in-problem
    `Problems.<problem>.<thm>`, or `Library.<...>.<decl>`). Returns a list
    aligned with `pairs`; None = unchecked (timeout, no lake, a
    metaprogramming entry in the batch)."""
    if not pairs:
        return []

    def build_pair(i: int) -> "list[str]":
        cand_sig, _mod, canonical_fqn = pairs[i]
        if not canonical_fqn:
            # No fqn resolved — pair is unusable; a syntactically-broken
            # stub attributes the error to this pair alone.
            return [f"-- pair {i} (no canonical fqn)",
                    f"theorem _dc_{i} : True := by trivial_unknown_tac_force_fail",
                    ""]
        # one file line per statement: the attribution counts lines
        cand_sig_flat = " ".join(cand_sig.split())
        return [f"-- pair {i}",
                f"theorem _dc_{i} {cand_sig_flat} := by",
                f"  apply @{canonical_fqn} <;> assumption",
                ""]
    return _run_partitioned(workspace, problem, [m for _, m, _ in pairs],
                            build_pair, skip_value=None)


def _batch_statement_defeq(
    workspace: Path,
    problem: str,
    pairs: "list[tuple[str, str, str]]",
) -> "list[bool | None]":
    """For each (cand_forall, twin_forall, twin_module) pair, check the
    two statement TYPES are definitionally equal via an `rfl` probe:
        theorem _dceq_i : (<cand_forall>) = (<twin_forall>) := rfl
    Failure direction: NOT-linking (candidate mints as novel)."""
    if not pairs:
        return []

    def build_pair(i: int) -> "list[str]":
        cand_forall, twin_forall, _mod = pairs[i]
        cand_flat = " ".join(cand_forall.split())
        twin_flat = " ".join(twin_forall.split())
        return [f"-- defeq pair {i}",
                f"theorem _dceq_{i} : ({cand_flat}) = ({twin_flat}) := rfl",
                ""]
    return _run_partitioned(workspace, problem, [m for _, _, m in pairs],
                            build_pair, skip_value=False)
