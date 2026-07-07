"""serve.lean_eval — the reader's Lean scratch pipeline.

One staged-elaborate endpoint, two surfaces (charter: the New page's
authoring check and the Library chapter's probe blocks). The browser
sends ordered code parts; we stage ONE throwaway .lean under
`.asterism/eval/`, run it through the warm gateway, and map the
diagnostics back to per-part local line numbers. `#check` / `#print
axioms` output arrives as severity-'information' diagnostics — the
frontend renders those as results, not errors.

Display-side only, by construction: `write_olean=False`, the staged
file is unlinked in `finally`, and nothing here touches proofs/ or the
DB — the same throwaway standing as the Gate B probe. `#eval` can run
arbitrary IO, which on this localhost solo surface is the same trust
level as the engine compiling agent code all day.

Gateway coupling is soft: if the gateway is not ready we kick ONE
background warm-up thread and return {"status": "warming"} immediately
— the frontend retries. Library-module imports get an incremental
`lake build` first (the gateway imports on-disk oleans as-is and does
NOT rebuild stale deps; the librarian rewrites Library files, so a
chapter probe can otherwise race a run's mid-chain state).
"""
from __future__ import annotations

import re
import tempfile
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

_MAX_CODE = 200_000  # chars, all parts combined — scratch, not upload
_IMPORT_LINE = re.compile(r"^\s*(?:public\s+|private\s+)?import\s+", re.M)

_warm_lock = threading.Lock()
_warm_started = False


class EvalPart(BaseModel):
    id: str
    code: str


class EvalBody(BaseModel):
    parts: list[EvalPart]
    imports: list[str] | None = None


_IMPORT_CAPTURE = re.compile(
    r"^\s*(?:public\s+|private\s+)?import\s+([\w.]+)\s*$", re.M)


def _assemble(parts: "list[tuple[str, str]]",
              imports: "list[str]") -> "tuple[str, int, list[tuple[str, int, int]]]":
    """Concatenate parts after an import preamble.

    Returns (text, preamble_lines, spans) where spans is
    [(part_id, first_global_line, last_global_line)] (1-indexed,
    inclusive). Import handling mirrors how the parts land on disk as
    ONE file: the first part may open with its own header; later parts'
    import lines are BLANKED in place (line counts must not shift — the
    New page's Root imports `Problems.<name>.Defs`, whose content is
    the part right above) and any non-`Problems.*` module they name is
    hoisted into the preamble. When nothing supplies an import,
    `import Mathlib` is prepended."""
    seen: "set[str]" = set(imports)
    for m in _IMPORT_CAPTURE.finditer(parts[0][1]) if parts else ():
        seen.add(m.group(1))
    hoisted: "list[str]" = []
    cleaned: "list[tuple[str, list[str]]]" = []
    for i, (pid, code) in enumerate(parts):
        body = code.splitlines() or [""]
        if i > 0:
            for j, ln in enumerate(body):
                im = _IMPORT_CAPTURE.match(ln)
                if im:
                    name = im.group(1)
                    if not name.startswith("Problems.") and name not in seen:
                        hoisted.append(name)
                        seen.add(name)
                    body[j] = ""  # keep the line, drop the mid-file import
        cleaned.append((pid, body))
    preamble = [f"import {m}" for m in list(imports) + hoisted]
    if not preamble and not (parts and _IMPORT_LINE.match(parts[0][1])):
        preamble = ["import Mathlib"]
    lines: "list[str]" = list(preamble)
    spans: "list[tuple[str, int, int]]" = []
    for pid, body in cleaned:
        start = len(lines) + 1
        lines.extend(body)
        spans.append((pid, start, len(lines)))
    return "\n".join(lines) + "\n", len(preamble), spans


def _map_diags(diags: "list[dict]", preamble_lines: int,
               spans: "list[tuple[str, int, int]]") -> "dict[str, list[dict]]":
    """Global diagnostic lines → {part_id: [diag with part-local line]}.
    Preamble hits (bad import) land under '_preamble'."""
    out: "dict[str, list[dict]]" = {}
    for d in diags:
        line = d.get("line")
        entry = {"line": None, "col": d.get("col"),
                 "severity": str(d.get("severity") or "error"),
                 "message": str(d.get("message") or "")}
        target = "_preamble"
        if isinstance(line, int) and line > preamble_lines:
            for pid, start, end in spans:
                if start <= line <= end:
                    target = pid
                    entry["line"] = line - start + 1
                    break
            else:
                target = spans[-1][0] if spans else "_preamble"
                if spans:
                    entry["line"] = max(1, line - spans[-1][1] + 1)
        out.setdefault(target, []).append(entry)
    return out


def register(app: FastAPI, workspace: Path) -> None:

    def _ensure_gateway() -> "str | None":
        """'ready' → proceed; otherwise kick ONE warm-up thread and
        report the phase for the frontend's retry loop."""
        from ..lsp import lifecycle as gw
        phase = gw.gateway_phase(workspace)
        if phase == "ready":
            return None
        global _warm_started
        with _warm_lock:
            if not _warm_started:
                _warm_started = True

                def _warm() -> None:
                    global _warm_started
                    try:
                        gw.start_gateway(workspace)
                    except Exception:  # noqa: BLE001 — retried on next eval
                        pass
                    finally:
                        _warm_started = False

                threading.Thread(target=_warm, name="serve-gateway-warm",
                                 daemon=True).start()
        return phase or "starting"

    @app.post("/api/lean/eval")
    def lean_eval(body: EvalBody) -> dict:
        """Stage the parts, elaborate on the warm gateway, return
        per-part diagnostics. {"status": "warming"} means retry."""
        parts = [(p.id, p.code) for p in body.parts if p.code.strip()]
        if not parts:
            raise HTTPException(status_code=400, detail="no code")
        if sum(len(c) for _, c in parts) > _MAX_CODE:
            raise HTTPException(status_code=413, detail="code too large")
        imports = list(body.imports or [])

        phase = _ensure_gateway()
        if phase is not None:
            return {"status": "warming", "phase": phase}

        # Chapter probes import Library modules; rebuild them
        # incrementally first (no-op seconds when fresh) so the probe
        # sees the text the page shows, not a stale olean.
        lib_mods = [m for m in imports if m.startswith("Library.")]
        if lib_mods:
            from ..pipeline._lake import lake_build_modules
            ok, detail = lake_build_modules(workspace, lib_mods)
            if not ok:
                return {"status": "ok", "ok": False, "wall_sec": 0.0,
                        "parts": {}, "preamble": [{
                            "line": None, "col": None, "severity": "error",
                            "message": "module rebuild failed: "
                                       + (detail or "")[:800]}]}

        text, n_pre, spans = _assemble(parts, imports)
        evdir = workspace / ".asterism" / "eval"
        evdir.mkdir(parents=True, exist_ok=True)
        from ..lsp import lifecycle as gw
        t0 = time.monotonic()
        fd, tmp = tempfile.mkstemp(suffix=".lean", prefix="probe_",
                                   dir=str(evdir))
        tmp_path = Path(tmp)
        try:
            import os
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            v = gw.verify_file(tmp_path, write_olean=False,
                               workspace=workspace, _retry_delays=())
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass
        if v.get("error"):
            code = 503 if v.get("transient") else 500
            raise HTTPException(status_code=code,
                                detail=f"EVAL_INFRA: {v['error']}")
        mapped = _map_diags(list(v.get("diagnostics") or []), n_pre, spans)
        return {
            "status": "ok",
            "ok": bool(v.get("ok")),
            "wall_sec": round(time.monotonic() - t0, 2),
            "parts": {pid: mapped.get(pid, []) for pid, _, _ in spans},
            "preamble": mapped.get("_preamble", []),
        }
