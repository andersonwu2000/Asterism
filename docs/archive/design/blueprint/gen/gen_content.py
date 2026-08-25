#!/usr/bin/env python3
"""
Generate blueprint/src/content.tex for the Residue Theorem from:
  * blueprint/gen/residue_deps.json  — per-declaration FQN / kind / docstring,
    extracted from the Lean *environment* by DumpResidueDeps.lean.
  * Library/Analysis/ResidueTheorem/*.lean — scanned textually for the actual
    citation edges (which declaration names each file references).

Why two sources: `lake env lean` does NOT load imported theorem proof bodies,
so the proof-level dependency edges are not available from the environment
(`value?` is none for imported theorems). We therefore recover the edges from
the source text. This generator does NOT read Library/INDEX.md (machine-only,
may be retired); all data comes from the Lean env + the .lean sources.

Run from the repo root:
    blueprint/.venv/Scripts/python.exe blueprint/gen/gen_content.py
"""
import json, re, sys
from collections import defaultdict
from pathlib import Path

BP   = Path(__file__).resolve().parent.parent          # blueprint/
REPO = BP.parent
LIB  = REPO / "Library" / "Analysis" / "ResidueTheorem"
DATA = BP / "gen" / "residue_deps.json"
OUT  = BP / "src" / "content.tex"

NS_PREFIX = "Library.Analysis.ResidueTheorem"
DEF_NODES = ["Complex.windingNumber", "Complex.residue"]   # always their own nodes
ROOT_SHORT = "residue_theorem"

decls = json.loads(DATA.read_text(encoding="utf-8"))
by_name = {d["name"]: d for d in decls}
short = lambda fqn: fqn.rsplit(".", 1)[-1]

DECL_RE = re.compile(
    r'^(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+|protected\s+|private\s+)*'
    r'(theorem|lemma|def)\s+([A-Za-z_][A-Za-z0-9_\']*)', re.M)

# ---- per-file: text, declared decls (resolved to FQN), principal theorem ----
files = {}   # stem -> dict(module, text, decls=[fqn...], principal=fqn|None)
for path in sorted(LIB.glob("*.lean")):
    stem = path.stem
    module = f"{NS_PREFIX}.{stem}"
    text = path.read_text(encoding="utf-8")
    decl_fqns, principal = [], None
    for kind, nm in DECL_RE.findall(text):
        # resolve to an in-scope FQN (Library module ns, or the Complex defs)
        for cand in (f"{module}.{nm}", f"Complex.{nm}"):
            if cand in by_name:
                decl_fqns.append(cand)
                if kind in ("theorem", "lemma"):
                    principal = cand          # last theorem wins
                break
    if principal is None and decl_fqns:
        principal = decl_fqns[-1]
    files[stem] = dict(module=module, text=text, decls=decl_fqns, principal=principal)

# ---- nodes: the two defs + one principal theorem per file ----
nodes = {}   # fqn -> dict(fqn, kind, title, doc, file_stem, tokens)
def humanize(fqn):
    s = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', short(fqn)).replace('_', ' ')
    return s[:1].upper() + s[1:]

def add_node(fqn, file_stem, tokens):
    d = by_name.get(fqn, {})
    nodes[fqn] = dict(fqn=fqn, kind=d.get("kind", "theorem"), title=humanize(fqn),
                      doc=d.get("doc", "").strip(), file_stem=file_stem, tokens=set(tokens))

# def nodes: token = their own short name; file = whichever file defines them
for dn in DEF_NODES:
    fstem = next((s for s, f in files.items() if dn in f["decls"]), None)
    add_node(dn, fstem, [short(dn)])
# file-principal nodes: tokens = all decl short names declared in that file
for stem, f in files.items():
    p = f["principal"]
    if p and p not in nodes:
        add_node(p, stem, [short(x) for x in f["decls"]])

# ---- edges A -> B  (A uses B) via whole-word token match in A's source file ----
def file_text(stem): return files[stem]["text"] if stem in files else ""
tok_res = {fqn: [re.compile(r'\b' + re.escape(t) + r'\b') for t in n["tokens"]]
           for fqn, n in nodes.items()}
edges = defaultdict(set)
for a, na in nodes.items():
    if na["kind"] == "def":
        continue                       # definitions are foundational sinks
    atext = file_text(na["file_stem"])
    for b, nb in nodes.items():
        if a == b:
            continue
        if any(rx.search(atext) for rx in tok_res[b]):
            edges[a].add(b)

# ---- closure of the root theorem, following A->B (A uses B) ----
root = next((fqn for fqn in nodes if short(fqn) == ROOT_SHORT), None)
if root is None:
    sys.exit("no residue_theorem node found")
closure, stack = set(), [root]
while stack:
    x = stack.pop()
    if x in closure:
        continue
    closure.add(x)
    stack.extend(edges[x])

# ---- DFS post-order so dependencies are emitted before dependents ----
order, seen = [], set()
def dfs(x):
    seen.add(x)
    for y in sorted(edges[x]):
        if y in closure and y not in seen:
            dfs(y)
    order.append(x)
dfs(root)

# ---- LaTeX emission ----
def esc(s):
    s = s.replace('\\', '\x00')          # placeholder: escape braces first
    for a, b in [('{', r'\{'), ('}', r'\}'), ('#', r'\#'), ('$', r'\$'),
                 ('%', r'\%'), ('&', r'\&'), ('_', r'\_'),
                 ('^', r'\textasciicircum{}'), ('~', r'\textasciitilde{}')]:
        s = s.replace(a, b)
    return s.replace('\x00', r'\textbackslash{}')

def render_inline(s):
    # Keep `$...$` math and `` `code` `` intact, turn **bold** into \textbf,
    # escape only the remaining prose.
    out = []
    for seg in re.split(r'(\$\$.*?\$\$|\$[^$]*\$|`[^`]*`|\*\*[^*]+\*\*)', s):
        if len(seg) >= 4 and seg[:2] == '$$' and seg[-2:] == '$$':
            out.append(seg)                              # display math, verbatim
        elif len(seg) >= 2 and seg[0] == '$' and seg[-1] == '$':
            out.append(seg)                              # inline math, verbatim
        elif len(seg) >= 2 and seg[0] == '`' and seg[-1] == '`':
            out.append(r'\texttt{' + esc(seg[1:-1]) + '}')
        elif len(seg) >= 4 and seg[:2] == '**' and seg[-2:] == '**':
            out.append(r'\textbf{' + esc(seg[2:-2]) + '}')
        else:
            out.append(esc(seg))
    return "".join(out)

def body(doc):
    if not doc:
        return "% (no docstring)"
    paras = re.split(r'\n\s*\n', doc)
    return "\n\n".join(render_inline(" ".join(p.split())) for p in paras if p.strip())

# Short, readable, unique labels: plastexdepgraph shows id.split(':')[-1] on the
# graph node, so the segment after ':' must be the short declaration name.
_labels, _used = {}, set()
for _fqn in sorted(nodes):
    _base = "decl:" + (re.sub(r'[^a-z0-9]+', '_', short(_fqn).lower()).strip('_') or "x")
    _lab, _i = _base, 2
    while _lab in _used:
        _lab, _i = f"{_base}_{_i}", _i + 1
    _used.add(_lab)
    _labels[_fqn] = _lab

def label(fqn):
    return _labels[fqn]

def env_of(node):
    if node["kind"] == "def":
        return "definition"
    return "theorem" if node["fqn"] == root else "lemma"

lines = [
    "% AUTO-GENERATED by blueprint/gen/gen_content.py — do not edit by hand.",
    "% Metadata (\\lean, \\leanok, docstrings) from the Lean environment via",
    "% DumpResidueDeps.lean; \\uses edges from scanning the .lean sources.",
    "% NOTE: does not use Library/INDEX.md (machine-only, may be retired).",
    "",
    "\\section{The Residue Theorem}",
    "",
    "Generated from \\texttt{Library/Analysis/ResidueTheorem/}. Each node links to its",
    "Lean declaration (all proven), with edges taken from the declaration citations in the",
    "sources. Click a node for its statement and links.",
    "",
]
for fqn in order:
    n = nodes[fqn]
    env = env_of(n)
    uses = sorted(label(b) for b in edges[fqn] if b in closure)
    lines.append(f"\\begin{{{env}}}[{esc(n['title'])}]")
    lines.append(f"  \\label{{{label(fqn)}}}")
    lines.append(f"  \\lean{{{fqn}}}")
    lines.append("  \\leanok")
    if uses:
        lines.append(f"  \\uses{{{','.join(uses)}}}")
    lines.append(f"  {body(n['doc'])}")
    lines.append(f"\\end{{{env}}}")
    lines.append("")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"nodes in closure: {len(closure)} / {len(nodes)} total")
print(f"edges (within closure): {sum(1 for a in closure for b in edges[a] if b in closure)}")
print(f"wrote {OUT}")
