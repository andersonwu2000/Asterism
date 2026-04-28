"""
spike-004 extended: test claude --add-dir with legitimate write + path traversal
"""

import subprocess
import sys
import tempfile
from pathlib import Path

FIXTURES = Path(__file__).parent


def run_test(name: str, prompt_file: Path, staging_dir: Path, outside_dir: Path):
    prompt = prompt_file.read_text(encoding="utf-8")
    cmd = [
        "claude", "-p",
        "--add-dir", str(staging_dir),
        "--output-format", "text",
        prompt,
    ]
    print(f"\n=== {name} ===")
    print(f"  staging_dir: {staging_dir}")
    print(f"  prompt: {prompt_file.name}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        encoding="utf-8",
        errors="replace",
    )

    print(f"  rc={result.returncode}")
    print(f"  STDOUT (first 500):\n{result.stdout[:500] if result.stdout else '(empty)'}")
    print()

    staging_files = [f.relative_to(staging_dir) for f in staging_dir.rglob("*") if f.is_file()]
    outside_files = [f.relative_to(outside_dir) for f in outside_dir.rglob("*") if f.is_file()]
    print(f"  Files in staging: {staging_files}")
    print(f"  Files in outside: {outside_files}")

    return {"staging_files": staging_files, "outside_files": outside_files, "rc": result.returncode}


def main():
    print("spike-004 extended: --add-dir write permissions test")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        staging = tmp_path / "staging"
        outside = tmp_path / "outside"
        staging.mkdir()
        outside.mkdir()

        # Test 1: legitimate write to staging
        r1 = run_test(
            "Test 1: Legitimate write to staging",
            FIXTURES / "spike004_legitimate_prompt.txt",
            staging,
            outside,
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        staging = tmp_path / "staging"
        outside = tmp_path / "outside"
        staging.mkdir()
        outside.mkdir()

        # Test 2: path traversal attempt
        r2 = run_test(
            "Test 2: Path traversal (../escape.txt)",
            FIXTURES / "spike004_traversal_prompt.txt",
            staging,
            outside,
        )

    print("\n=== SUMMARY ===")
    print(f"Test 1 (legitimate write): staging files={r1['staging_files']}, outside={r1['outside_files']}")
    print(f"Test 2 (path traversal):   staging files={r2['staging_files']}, outside={r2['outside_files']}")

    staging_write_works = len(r1["staging_files"]) > 0
    traversal_blocked = len(r2["outside_files"]) == 0
    print(f"\n  Staging write works: {staging_write_works}")
    print(f"  Path traversal blocked: {traversal_blocked}")


if __name__ == "__main__":
    main()
