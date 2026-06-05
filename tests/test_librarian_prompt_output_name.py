"""Invariant: each Librarian prompt must name the exact output file the
pipeline reads back. A drift here is silent — the agent does real work but
writes to a filename the framework never reads, surfacing only as a runtime
`agent_no_output` failure (caught live on the first SG dedup run, 2026-05-31).

The mapping is the contract between `Tooling/pipeline/librarian.py` (which
reads the file) and `Tooling/prompts/librarian/<kind>.md` (which tells the
agent where to write it). Both ends are asserted against each other.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "Tooling" / "prompts" / "librarian"
PIPELINE = ROOT / "Tooling" / "pipeline" / "librarian.py"

# work_kind -> the output filename the agent must produce.
# (dedup is mechanical keep-all — no prompt/agent; bridge is agentless.)
OUTPUT_FILE = {
    "classify": "plan.json",
    "migrate": "patch.lean",
}


@pytest.mark.parametrize("work_kind,filename", sorted(OUTPUT_FILE.items()))
def test_prompt_names_its_output_file(work_kind, filename):
    """The prompt the agent reads must mention the filename it should write."""
    prompt = (PROMPTS / f"{work_kind}.md").read_text(encoding="utf-8")
    assert filename in prompt, (
        f"prompts/librarian/{work_kind}.md never names its output file "
        f"{filename!r}; the agent will guess a name and the pipeline will "
        f"fail with agent_no_output"
    )


@pytest.mark.parametrize("filename", sorted(set(OUTPUT_FILE.values())))
def test_pipeline_reads_the_expected_file(filename):
    """The pipeline source must actually read each filename the prompts name —
    guards the other direction of the contract."""
    src = PIPELINE.read_text(encoding="utf-8")
    assert f'"{filename}"' in src, (
        f"{PIPELINE.name} does not read {filename!r}; prompt/code filename "
        f"contract drifted"
    )
